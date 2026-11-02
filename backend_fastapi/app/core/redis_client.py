"""
Koneksi Redis async untuk cache API peta.

Kalau Redis mati atau belum di-set, pemanggil mendapat None dan API
tetap menjawab dari database.
"""
import logging
import time
from urllib.parse import urlparse, urlunparse

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None
_override = None
_down_until = 0.0
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


def _enabled() -> bool:
    return bool(settings.REDIS_MAP_ENABLED and (settings.REDIS_URL or "").strip())


async def get_client():
    """Klien Redis yang sudah terhubung, atau None bila cache tidak dipakai."""
    global _client, _down_until
    if _override is not None:
        return _override
    if not _enabled():
        return None
    if _client is not None:
        return _client
    if time.monotonic() < _down_until:
        return None

    try:
        from redis.asyncio import BlockingConnectionPool, Redis

        # Pool yang MENUNGGU koneksi bebas (bukan langsung error "Too many connections"). Satu layar peta meminta
        # ~30 ubin foto udara serentak; dengan pool biasa max 20, permintaan ke-21 gagal, Redis dianggap mati
        # 30 dtk dan seluruh cache (ubin & JSON peta) terlewati (terlihat di produksi, 2 Nov 2026).
        pool = BlockingConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=1,
            socket_timeout=5,
            health_check_interval=30,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            timeout=_POOL_WAIT_SECONDS,
        )
        client = Redis.from_pool(pool)
        await client.ping()
    except Exception as exc:
        _down_until = time.monotonic() + _RETRY_SECONDS
        logger.warning("Redis cache peta tidak tersedia (%s): %s", _redact(settings.REDIS_URL), exc)
        return None

    _client = client
    logger.info("Redis cache peta terhubung ke %s", _redact(settings.REDIS_URL))
    return _client


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
    global _client, _down_until
    if client is None or client is _override:
        return
    if is_pool_busy(exc):
        logger.info("Pool Redis penuh, satu permintaan dilewati tanpa cache")
        return
    _down_until = time.monotonic() + _RETRY_SECONDS
    if _client is client:
        _client = None
    try:
        await client.aclose()
    except Exception:
        pass
    logger.warning("Redis cache peta terputus, API peta lanjut tanpa cache")


async def startup() -> None:
    if not _enabled():
        logger.info("Redis cache peta dimatikan")
        return
    await get_client()


async def shutdown() -> None:
    global _client
    client = _client
    _client = None
    if client is None:
        return
    try:
        await client.aclose()
    except Exception:
        pass
