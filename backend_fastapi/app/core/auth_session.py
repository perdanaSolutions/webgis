"""
Sesi JWT user di Redis (ADR-001 Horizontal Scaling).

Namespace `gis:auth:*` terpisah dari cache peta `gis:map:*`.
Bila REDIS_AUTH_ENABLED=false → no-op (perilaku JWT-only lama).
Bila true → fail-closed: Redis wajib untuk create/assert/revoke.
"""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from app.core import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

SESS_PREFIX = "gis:auth:sess:"
USER_PREFIX = "gis:auth:user:"
DENY_PREFIX = "gis:auth:deny:"


class AuthSessionUnavailable(Exception):
    """Redis auth diwajibkan tetapi tidak bisa dihubungi."""


class AuthSessionRevoked(Exception):
    """jti tidak aktif (logout, dicabut, atau tidak pernah terdaftar)."""


def auth_ttl_seconds() -> int:
    configured = getattr(settings, "REDIS_AUTH_TTL_SECONDS", None)
    if configured is not None and int(configured) > 0:
        return int(configured)
    return max(60, int(settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60)


def new_jti() -> str:
    return str(uuid4())


def _as_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else str(value).encode()


async def _require_client():
    """None jika auth Redis dimatikan; raise bila diaktifkan tapi Redis down."""
    if not redis_client.auth_enabled():
        return None
    client = await redis_client.get_auth_redis()
    if client is None:
        raise AuthSessionUnavailable("Redis auth tidak tersedia")
    return client


async def create_session(jti: str, user_id: str, *, ttl: int | None = None) -> None:
    """Daftarkan sesi aktif setelah login berhasil."""
    client = await _require_client()
    if client is None:
        return
    ttl_s = auth_ttl_seconds() if ttl is None else int(ttl)
    now = str(int(time.time())).encode()
    sess_key = f"{SESS_PREFIX}{jti}"
    user_key = f"{USER_PREFIX}{user_id}"
    try:
        await client.hset(
            sess_key,
            mapping={b"uid": _as_bytes(user_id), b"iat": now},
        )
        await client.expire(sess_key, ttl_s)
        await client.sadd(user_key, _as_bytes(jti))
        await client.expire(user_key, ttl_s)
    except AuthSessionUnavailable:
        raise
    except Exception as exc:
        await redis_client.mark_down(client)
        logger.warning("Gagal menulis sesi auth Redis: %s", exc)
        raise AuthSessionUnavailable("Redis auth tidak tersedia") from exc


async def assert_session(jti: str | None) -> None:
    """Tolak request bila jti hilang, di-deny, atau tidak ada di registry sesi."""
    if not redis_client.auth_enabled():
        return
    if not jti:
        raise AuthSessionRevoked("Token tanpa jti")
    client = await _require_client()
    try:
        if await client.exists(f"{DENY_PREFIX}{jti}"):
            raise AuthSessionRevoked("Sesi dicabut")
        if not await client.exists(f"{SESS_PREFIX}{jti}"):
            raise AuthSessionRevoked("Sesi tidak valid atau sudah logout")
    except AuthSessionRevoked:
        raise
    except AuthSessionUnavailable:
        raise
    except Exception as exc:
        await redis_client.mark_down(client)
        logger.warning("Gagal cek sesi auth Redis: %s", exc)
        raise AuthSessionUnavailable("Redis auth tidak tersedia") from exc


async def revoke_jti(
    jti: str | None,
    *,
    user_id: str | None = None,
    remaining_ttl: int | None = None,
) -> None:
    """Cabut satu jti (logout). Menulis deny + hapus sess."""
    if not jti:
        return
    client = await _require_client()
    if client is None:
        return
    sess_key = f"{SESS_PREFIX}{jti}"
    deny_key = f"{DENY_PREFIX}{jti}"
    try:
        uid = user_id
        if uid is None:
            raw = await client.hget(sess_key, b"uid")
            if raw is not None:
                uid = raw.decode() if isinstance(raw, bytes) else str(raw)
        ttl = remaining_ttl
        if ttl is None or ttl <= 0:
            ttl = await client.ttl(sess_key)
            if ttl is None or int(ttl) < 1:
                ttl = auth_ttl_seconds()
        await client.delete(sess_key)
        await client.set(deny_key, b"1", ex=int(ttl))
        if uid:
            await client.srem(f"{USER_PREFIX}{uid}", _as_bytes(jti))
    except AuthSessionUnavailable:
        raise
    except Exception as exc:
        await redis_client.mark_down(client)
        logger.warning("Gagal revoke jti Redis: %s", exc)
        raise AuthSessionUnavailable("Redis auth tidak tersedia") from exc


async def revoke_user(user_id: str) -> None:
    """Cabut semua jti aktif user (ganti password / kunci / nonaktif)."""
    client = await _require_client()
    if client is None:
        return
    user_key = f"{USER_PREFIX}{user_id}"
    try:
        members = await client.smembers(user_key)
        default_ttl = auth_ttl_seconds()
        for raw in members or []:
            jti = raw.decode() if isinstance(raw, bytes) else str(raw)
            sess_key = f"{SESS_PREFIX}{jti}"
            deny_key = f"{DENY_PREFIX}{jti}"
            ttl = await client.ttl(sess_key)
            if ttl is None or int(ttl) < 1:
                ttl = default_ttl
            await client.delete(sess_key)
            await client.set(deny_key, b"1", ex=int(ttl))
        await client.delete(user_key)
    except AuthSessionUnavailable:
        raise
    except Exception as exc:
        await redis_client.mark_down(client)
        logger.warning("Gagal revoke_user Redis: %s", exc)
        raise AuthSessionUnavailable("Redis auth tidak tersedia") from exc
