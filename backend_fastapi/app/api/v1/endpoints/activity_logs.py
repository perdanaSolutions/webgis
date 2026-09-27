from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.params import Limit, Page
from app.schemas.common import PaginatedResponse
from app.services import activity_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse, summary="Log aktivitas user (audit.user_activities)")
def list_logs(
    db: DbSession,
    _: CurrentUser,
    search: str | None = Query(None, description="Cari aksi, resource, atau nama user"),
    status_filter: str | None = Query(None, description="SUCCESS atau FAILED"),
    page: Page = 1,
    limit: Limit = 10,
):
    return activity_service.list_logs(db, search, status_filter, page, limit)
