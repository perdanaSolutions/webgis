"""
Koneksi Redis async bersama (cache peta + sesi auth jti).

- Cache peta: fail-open — jika Redis mati, API tetap baca DB.
- Auth sesi: fail-closed di lapisan `auth_session` bila REDIS_AUTH_ENABLED=true.
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


def map_enabled() -> bool:
    return bool(settings.REDIS_MAP_ENABLED and redis_url_configured())


def auth_enabled() -> bool:
    return bool(getattr(settings, "REDIS_AUTH_ENABLED", False) and redis_url_configured())


def _want_connection() -> bool:
    return map_enabled() or auth_enabled()


async def _ensure_client():
    """Buka koneksi bersama bila map atau auth membutuhkan Redis."""
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
        from redis.asyncio import Redis

        client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=1,
            socket_timeout=5,
            health_check_interval=30,
            max_connections=20,
        )
        await client.ping()
    except Exception as exc:
        _down_until = time.monotonic() + _RETRY_SECONDS
        logger.warning("Redis tidak tersedia (%s): %s", _redact(settings.REDIS_URL), exc)
        return None

    _client = client
    logger.info("Redis terhubung ke %s", _redact(settings.REDIS_URL))
    return _client


async def get_client():
    """Klien untuk cache peta. None bila REDIS_MAP_ENABLED=false (kecuali override tes)."""
    if _override is not None:
        return _override
    if not map_enabled():
        return None
    return await _ensure_client()


async def get_auth_redis():
    """Klien untuk sesi auth. None bila REDIS_AUTH_ENABLED=false (kecuali override tes)."""
    if _override is not None:
        return _override
    if not auth_enabled():
        return None
    return await _ensure_client()


async def mark_down(client) -> None:
    """Tutup klien yang putus dan coba lagi setelah jeda."""
    global _client, _down_until
    if client is None or client is _override:
        return
    _down_until = time.monotonic() + _RETRY_SECONDS
    if _client is client:
        _client = None
    try:
        await client.aclose()
    except Exception:
        pass
    logger.warning("Redis terputus; cache peta fail-open, auth fail-closed bila diaktifkan")


async def startup() -> None:
    if not _want_connection():
        logger.info("Redis dimatikan (map & auth)")
        return
    roles = []
    if map_enabled():
        roles.append("map-cache")
    if auth_enabled():
        roles.append("auth-session")
    logger.info("Redis diaktifkan untuk: %s", ", ".join(roles) or "none")
    await _ensure_client()


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


# Kompatibilitas nama lama
def _enabled() -> bool:
    return map_enabled()
