"""
Koneksi Redis async bersama (cache peta + sesi auth jti).

- Cache peta: fail-open — jika Redis mati, API tetap baca DB.
- Auth sesi: fail-closed di lapisan `auth_session` bila REDIS_AUTH_ENABLED=true.
- REDIS_CACHE_URL (opsional): cache peta & ubin Foto Udara di Redis terpisah (allkeys-lru) sehingga
  tidak bisa menggusur kunci sesi auth di REDIS_URL (noeviction + AOF). Kosong = satu Redis (perilaku lama).
"""
import logging
import time
from urllib.parse import urlparse, urlunparse

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None          # klien Redis utama (REDIS_URL): auth, dan cache bila REDIS_CACHE_URL kosong
_cache_client = None    # klien Redis cache terpisah (REDIS_CACHE_URL)
_override = None
_down_until = 0.0
_cache_down_until = 0.0
_RETRY_SECONDS = 30.0
# Lama menunggu koneksi bebas di pool sebelum satu permintaan dilewati tanpa cache.
_POOL_WAIT_SECONDS = 2
# Pesan redis-py saat pool penuh: pool biasa ("Too many connections") / BlockingConnectionPool (timeout).
_POOL_BUSY_MESSAGES = ("Too many connections", "No connection available.")


def set_client_override(client) -> None:
    """Pakai klien palsu di tes. `None` mengembalikan ke klien sungguhan."""
    global _override
    _override = client


def _redact(url: str) -> str:
    parts = urlparse(url)
    if not parts.password:
        return url
    hostname = parts.hostname or ""
    auth = "***@"
    if parts.username:
        auth = f"{parts.username}:***@"
    port = f":{parts.port}" if parts.port else ""
    return urlunparse(parts._replace(netloc=f"{auth}{hostname}{port}"))


def redis_url_configured() -> bool:
    return bool((settings.REDIS_URL or "").strip())


def cache_url() -> str:
    """URL Redis untuk cache peta/ubin. Fallback ke REDIS_URL bila REDIS_CACHE_URL kosong."""
    return (getattr(settings, "REDIS_CACHE_URL", "") or "").strip() or (settings.REDIS_URL or "").strip()


def cache_is_separate() -> bool:
    separate = (getattr(settings, "REDIS_CACHE_URL", "") or "").strip()
    return bool(separate) and separate != (settings.REDIS_URL or "").strip()


def map_enabled() -> bool:
    return bool(settings.REDIS_MAP_ENABLED and cache_url())


def auth_enabled() -> bool:
    return bool(getattr(settings, "REDIS_AUTH_ENABLED", False) and redis_url_configured())


def _want_connection() -> bool:
    return map_enabled() or auth_enabled()


async def _open(url: str):
    from redis.asyncio import BlockingConnectionPool, Redis

    # Pool yang MENUNGGU koneksi bebas (bukan langsung error "Too many connections"). Satu layar peta meminta
    # ~30 ubin foto udara serentak; dengan pool biasa max 20, permintaan ke-21 gagal, Redis dianggap mati
    # 30 dtk dan seluruh cache (ubin & JSON peta) terlewati (terlihat di produksi, 2 Nov 2026).
    pool = BlockingConnectionPool.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=1,
        socket_timeout=5,
        health_check_interval=30,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        timeout=_POOL_WAIT_SECONDS,
    )
    client = Redis.from_pool(pool)
    await client.ping()
    return client


async def _ensure_client():
    """Klien Redis utama (REDIS_URL) — dipakai auth, dan cache bila tidak ada REDIS_CACHE_URL."""
    global _client, _down_until
    if _override is not None:
        return _override
    if not _want_connection():
        return None
    if _client is not None:
        return _client
    if time.monotonic() < _down_until:
        return None
    try:
        client = await _open(settings.REDIS_URL)
    except Exception as exc:
        _down_until = time.monotonic() + _RETRY_SECONDS
        logger.warning("Redis tidak tersedia (%s): %s", _redact(settings.REDIS_URL), exc)
        return None
    _client = client
    logger.info("Redis terhubung ke %s", _redact(settings.REDIS_URL))
    return _client


async def _ensure_cache_client():
    """Klien Redis cache terpisah (REDIS_CACHE_URL). Mati -> None (cache fail-open), tidak memengaruhi auth."""
    global _cache_client, _cache_down_until
    if _cache_client is not None:
        return _cache_client
    if time.monotonic() < _cache_down_until:
        return None
    url = cache_url()
    try:
        client = await _open(url)
    except Exception as exc:
        _cache_down_until = time.monotonic() + _RETRY_SECONDS
        logger.warning("Redis cache tidak tersedia (%s): %s", _redact(url), exc)
        return None
    _cache_client = client
    logger.info("Redis cache terhubung ke %s", _redact(url))
    return _cache_client


async def get_client():
    """Klien untuk cache peta/ubin. None bila REDIS_MAP_ENABLED=false (kecuali override tes)."""
    if _override is not None:
        return _override
    if not map_enabled():
        return None
    if cache_is_separate():
        return await _ensure_cache_client()
    return await _ensure_client()


async def get_auth_redis():
    """Klien untuk sesi auth (selalu REDIS_URL). None bila REDIS_AUTH_ENABLED=false (kecuali override tes)."""
    if _override is not None:
        return _override
    if not auth_enabled():
        return None
    return await _ensure_client()


def is_pool_busy(exc: BaseException | None) -> bool:
    """Pool sedang penuh (menunggu koneksi kelamaan) -> Redis sendiri sehat, jangan dianggap mati."""
    if exc is None:
        return False
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError
    except ImportError:
        return False
    return isinstance(exc, RedisConnectionError) and str(exc) in _POOL_BUSY_MESSAGES


async def mark_down(client, exc: BaseException | None = None) -> None:
    """Tutup klien yang putus dan coba lagi setelah jeda. Pool yang hanya sedang penuh tidak mematikan cache."""
    global _client, _down_until, _cache_client, _cache_down_until
    if client is None or client is _override:
        return
    if is_pool_busy(exc):
        logger.info("Pool Redis penuh, satu permintaan dilewati tanpa cache")
        return
    if client is _cache_client:
        _cache_client = None
        _cache_down_until = time.monotonic() + _RETRY_SECONDS
        message = "Redis cache terputus; API peta lanjut tanpa cache (auth tidak terpengaruh)"
    else:
        _down_until = time.monotonic() + _RETRY_SECONDS
        if _client is client:
            _client = None
        message = "Redis terputus; cache peta fail-open, auth fail-closed bila diaktifkan"
    try:
        await client.aclose()
    except Exception:
        pass
    logger.warning(message)


async def startup() -> None:
    if not _want_connection():
        logger.info("Redis dimatikan (map & auth)")
        return
    roles = []
    if map_enabled():
        roles.append("map-cache" + (" (REDIS_CACHE_URL terpisah)" if cache_is_separate() else ""))
    if auth_enabled():
        roles.append("auth-session")
    logger.info("Redis diaktifkan untuk: %s", ", ".join(roles) or "none")
    if auth_enabled() or not cache_is_separate():
        await _ensure_client()
    if map_enabled() and cache_is_separate():
        await _ensure_cache_client()


async def shutdown() -> None:
    global _client, _cache_client
    clients = [c for c in (_client, _cache_client) if c is not None]
    _client = None
    _cache_client = None
    for client in clients:
        try:
            await client.aclose()
        except Exception:
            pass


# Kompatibilitas nama lama
def _enabled() -> bool:
    return map_enabled()
