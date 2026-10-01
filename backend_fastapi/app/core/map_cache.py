"""
Cache Redis untuk API baca halaman peta / blok profile.

Semua GET di bawah `/spatial` (hierarki, GeoJSON blok, detail blok, histori,
katalog, dan layer sawit/tph/jalan/jembatan/landuse/slope/drainase) disimpan
per user. Respons sudah difilter hak akses sebelum masuk cache, dan kunci
memuat id user dari JWT supaya data user lain tidak tercampur.

Cache dibuang (versi dinaikkan) setelah tulis yang mengubah data peta:
upload/hapus spasial, impor areal statement, produksi, rotasi, serta
perubahan user, role, dan hak akses wilayah.
"""
import gzip
import hashlib
import logging
from urllib.parse import parse_qsl, urlencode

from jwt import PyJWTError, decode
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.redis_client import get_client, mark_down

logger = logging.getLogger(__name__)

# Naikkan bila bentuk JSON API peta berubah, supaya deploy tidak mengembalikan payload lama.
MAP_CACHE_SCHEMA = "1"
_VERSION_KEY = "gis:map:version"
_RAW = b"\x00"
_GZIP = b"\x01"
_ANALYZE = {"upload-analyze", "analyze", "analyze-sample"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def map_prefix() -> str:
    return f"{settings.API_V1_STR}/spatial"


def _boundary(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def invalidation_prefixes() -> tuple[str, ...]:
    base = settings.API_V1_STR
    return (
        f"{base}/spatial",
        f"{base}/areal-statement",
        f"{base}/pokok-produksi",
        f"{base}/trx-rotasi-pusingan",
        f"{base}/akses-data",
        f"{base}/users",
        f"{base}/roles",
    )


def is_map_read(method: str, path: str) -> bool:
    return method == "GET" and _boundary(path, map_prefix())


def is_map_invalidation(method: str, path: str) -> bool:
    if method not in _WRITE_METHODS:
        return False
    if not any(_boundary(path, prefix) for prefix in invalidation_prefixes()):
        return False
    action = path.rstrip("/").rsplit("/", 1)[-1]
    return action not in _ANALYZE


def user_id_from_scope(scope: Scope) -> str | None:
    token = ""
    for key, value in scope.get("headers") or []:
        if key.lower() == b"authorization":
            raw = value.decode("latin-1").strip()
            if raw.lower().startswith("bearer "):
                token = raw[7:].strip()
            break
    if not token:
        return None
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except PyJWTError:
        return None
    subject = payload.get("sub")
    return str(subject) if subject else None


def cache_digest(user_id: str, path: str, query: bytes) -> str:
    pairs = parse_qsl(query.decode("latin-1"), keep_blank_values=False)
    pairs.sort()
    raw = f"{MAP_CACHE_SCHEMA}\n{user_id}\n{path}\n{urlencode(pairs)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def pack_body(body: bytes) -> bytes:
    if len(body) >= 1024:
        compressed = gzip.compress(body, compresslevel=1)
        if len(compressed) + 1 < len(body):
            return _GZIP + compressed
    return _RAW + body


def unpack_body(payload: bytes) -> bytes:
    flag, data = payload[:1], payload[1:]
    if flag == _GZIP:
        return gzip.decompress(data)
    if flag == _RAW:
        return data
    raise ValueError("payload cache tidak dikenal")


def _is_json(headers: list[tuple[bytes, bytes]]) -> bool:
    for key, value in headers:
        if key.lower() == b"content-type":
            return b"application/json" in value.lower()
    return False


def _with_cache_headers(headers: list[tuple[bytes, bytes]], status: bytes) -> list[tuple[bytes, bytes]]:
    drop = {b"x-cache", b"cache-control"}
    kept = [(key, value) for key, value in headers if key.lower() not in drop]
    kept.append((b"x-cache", status))
    kept.append((b"cache-control", b"private, no-store"))
    return kept


async def _read_version(client) -> int | None:
    try:
        raw = await client.get(_VERSION_KEY)
    except Exception:
        await mark_down(client)
        return None
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def lookup(user_id: str, path: str, query: bytes) -> tuple[int | None, bytes | None]:
    """`(versi, body)` bila hit, `(versi, None)` bila miss, `(None, None)` bila Redis tidak dipakai."""
    client = await get_client()
    if client is None:
        return None, None
    version = await _read_version(client)
    if version is None:
        return None, None
    key = f"gis:map:v{version}:{cache_digest(user_id, path, query)}"
    try:
        payload = await client.get(key)
    except Exception:
        await mark_down(client)
        return None, None
    if not payload:
        return version, None
    try:
        return version, unpack_body(payload)
    except Exception:
        logger.warning("Isi cache peta rusak, dibaca ulang dari database")
        return version, None


async def store(version: int, user_id: str, path: str, query: bytes, body: bytes) -> bool:
    ttl = int(settings.REDIS_MAP_TTL_SECONDS)
    if ttl <= 0 or len(body) > int(settings.REDIS_MAP_MAX_BYTES):
        return False
    client = await get_client()
    if client is None:
        return False
    key = f"gis:map:v{version}:{cache_digest(user_id, path, query)}"
    try:
        await client.set(key, pack_body(body), ex=ttl)
    except Exception:
        await mark_down(client)
        return False
    return True


async def bump_version() -> None:
    client = await get_client()
    if client is None:
        return
    try:
        await client.incr(_VERSION_KEY)
    except Exception:
        await mark_down(client)
        logger.warning("Gagal membatalkan cache peta")


class MapRedisCacheMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        path = scope.get("path") or ""
        if is_map_read(method, path):
            await self._read(scope, receive, send)
            return
        if is_map_invalidation(method, path):
            await self._write(scope, receive, send)
            return
        await self.app(scope, receive, send)

    async def _read(self, scope: Scope, receive: Receive, send: Send) -> None:
        user_id = user_id_from_scope(scope)
        path = scope.get("path") or ""
        query = scope.get("query_string") or b""
        if user_id is None:
            await self.app(scope, receive, send)
            return

        version, cached = await lookup(user_id, path, query)
        if cached is not None:
            response = Response(
                content=cached,
                media_type="application/json",
                headers={"X-Cache": "HIT", "Cache-Control": "private, no-store"},
            )
            await response(scope, receive, send)
            return
        if version is None:
            await self.app(scope, receive, send)
            return

        status = 500
        headers: list[tuple[bytes, bytes]] = []
        chunks: list[bytes] = []
        started = False
        flushed = False

        async def flush() -> None:
            nonlocal flushed
            if flushed:
                return
            flushed = True
            body = b"".join(chunks)
            out = headers
            if status == 200 and body and _is_json(headers):
                saved = await store(version, user_id, path, query, body)
                out = _with_cache_headers(headers, b"MISS" if saved else b"BYPASS")
            await send({"type": "http.response.start", "status": status, "headers": out})
            await send({"type": "http.response.body", "body": body, "more_body": False})

        async def send_wrapper(message: Message) -> None:
            nonlocal status, headers, started
            if message["type"] == "http.response.start":
                started = True
                status = int(message["status"])
                headers = list(message.get("headers") or [])
                return
            if message["type"] == "http.response.body":
                chunks.append(message.get("body") or b"")
                if not message.get("more_body", False):
                    await flush()
                return
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if started and not flushed:
                await flush()

    async def _write(self, scope: Scope, receive: Receive, send: Send) -> None:
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            if (
                message["type"] == "http.response.body"
                and not message.get("more_body", False)
                and 200 <= status < 300
            ):
                await bump_version()
            await send(message)

        await self.app(scope, receive, send_wrapper)
