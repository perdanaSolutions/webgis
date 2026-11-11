from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CanMonitorUsers, DbSession
from app.api.params import Limit, Page
from app.core.auth_session import AuthSessionUnavailable
from app.services import user_monitoring_service

router = APIRouter()


@router.get("/users", summary="Monitoring user: status online/offline berdasarkan sesi login")
async def monitoring_users(
    db: DbSession,
    _: CanMonitorUsers,
    search: str | None = Query(None, description="Cari username, nama, atau email"),
    status_filter: Literal["online", "offline"] | None = Query(None, alias="status"),
    page: Page = 1,
    limit: Limit = 10,
):
    """
    `online` = punya sesi login yang masih berlaku. `ringkasan` menghitung semua user yang cocok dengan
    `search` (tidak terpengaruh filter `status`). `sumber` menjelaskan asal status: `redis` (registry sesi)
    atau `log_aktivitas` (perkiraan dari log LOGIN/LOGOUT bila REDIS_AUTH_ENABLED=false).
    """
    try:
        return await user_monitoring_service.monitoring_users(
            db, search=search, status=status_filter, page=page, limit=limit)
    except AuthSessionUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"errors": [{"type": "auth_unavailable", "field": "auth",
                                "msg": "Layanan autentikasi sementara tidak tersedia", "input": None}]},
        )
