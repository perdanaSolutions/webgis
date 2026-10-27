"""
Mode maintenance yang dikendalikan dari tabel master.app_settings.

Status dibaca dari database lalu disimpan di memori beberapa detik agar
tidak ada query per request. Kalau database gagal dibaca, anggap tidak
maintenance (fail open) dan catat warning.
"""
import json
import logging
import time

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

CACHE_SECONDS = 10.0
RETRY_AFTER_SECONDS = 60
DEFAULT_MESSAGE = (
    "Website sedang dalam perbaikan. Mohon coba beberapa saat lagi."
)
TRUE_VALUES = {"true", "1", "yes", "on", "ya"}

_cache: dict | None = None
_cache_at = 0.0
_override: dict | None = None


def set_status_override(status: dict | None) -> None:
    """Dipakai tes: paksa status tertentu. `None` kembali ke database."""
    global _override
    _override = status
    clear_cache()


def clear_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def _parse_bool(raw) -> bool:
    if raw is None:
        return False
    value = str(raw).strip().strip('"').lower()
    return value in TRUE_VALUES


def _read_from_db() -> dict:
    from app.core.database import engine

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT key, value FROM master.app_settings "
            "WHERE key IN ('maintenance_mode', 'maintenance_message')"
        )).all()
    values = {row[0]: row[1] for row in rows}
    message = (values.get("maintenance_message") or "").strip().strip('"')
    return {
        "maintenance": _parse_bool(values.get("maintenance_mode")),
        "message": message or DEFAULT_MESSAGE,
    }


def read_status_sync() -> dict:
    global _cache, _cache_at
    if _override is not None:
        return dict(_override)
    now = time.monotonic()
    if _cache is not None and now - _cache_at < CACHE_SECONDS:
        return _cache
    try:
        status = _read_from_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal membaca status maintenance, dianggap OFF: %s", exc.__class__.__name__)
        status = {"maintenance": False, "message": DEFAULT_MESSAGE}
    _cache, _cache_at = status, now
    return status


async def get_status() -> dict:
    if _override is not None:
        return dict(_override)
    if _cache is not None and time.monotonic() - _cache_at < CACHE_SECONDS:
        return _cache
    return await run_in_threadpool(read_status_sync)


def status_path() -> str:
    return f"{settings.API_V1_STR}/system/maintenance"


def is_exempt(method: str, path: str, has_auth: bool) -> bool:
    if method == "OPTIONS":
        return True
    api = settings.API_V1_STR
    if path in ("/health", "/", status_path(), f"{api}/openapi.json", "/docs", "/redoc"):
        return True
    if path.startswith("/docs/"):
        return True
    # Cek deploy-main.sh/deploy-uat.sh: GET pengumuman TANPA token harus tetap 401,
    # kalau tidak deploy dianggap gagal dan di-rollback. Tanpa token tetap tidak bisa dipakai.
    if not has_auth and method in ("GET", "HEAD") and path.rstrip("/") == f"{api}/pengumuman":
        return True
    return False


class MaintenanceMiddleware:
    """ASGI murni. Pasang DI DALAM CORSMiddleware agar 503 tetap membawa header CORS."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        has_auth = any(k.lower() == b"authorization" for k, _ in scope.get("headers") or [])
        if is_exempt(method, path, has_auth):
            await self.app(scope, receive, send)
            return
        status = await get_status()
        if not status.get("maintenance"):
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            status_code=503,
            content={
                "maintenance": True,
                "message": status.get("message") or DEFAULT_MESSAGE,
                "errors": [{
                    "type": "maintenance",
                    "field": "global",
                    "msg": status.get("message") or DEFAULT_MESSAGE,
                    "input": None,
                }],
            },
            headers={"Retry-After": str(RETRY_AFTER_SECONDS), "Cache-Control": "no-store"},
        )
        await response(scope, receive, send)
