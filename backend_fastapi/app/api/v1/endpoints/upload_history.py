from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, user_has_permission
from app.api.params import Bulan, Limit, Page, Tahun
from app.schemas.common import PaginatedResponse
from app.schemas.upload_history import UploadHistoryDetail
from app.services import upload_history_service as service

router = APIRouter()


def _own_only(db, user) -> UUID | None:
    """Pemilik upload:geojson melihat semua riwayat; user lain hanya upload miliknya sendiri."""
    return None if user_has_permission(db, user, "upload:geojson") else user.id


@router.get("/", response_model=PaginatedResponse)
def list_upload_history(
    db: DbSession,
    current_user: CurrentUser,
    search: str | None = Query(None, description="Cari di nama file, tabel tujuan, atau nama/username pengunggah"),
    status_filter: str | None = Query(None, alias="status", description="IN_PROGRESS, SUCCESS, PARTIAL_SUCCESS, FAILED, ABANDONED"),
    source_type: str | None = Query(None, description="GEOJSON_UPLOAD atau EXCEL_UPLOAD"),
    target_table: str | None = Query(None, description="Contoh: spatial.block_boundaries"),
    layer: str | None = Query(None, description="Kode layer, contoh: blok, sawit, jalan"),
    uploaded_by: UUID | None = Query(None, description="ID user pengunggah (diabaikan untuk user non-pengelola)"),
    bulan: Bulan = None,
    tahun: Tahun = None,
    tanggal_dari: date | None = Query(None, description="Tanggal upload mulai (YYYY-MM-DD)"),
    tanggal_sampai: date | None = Query(None, description="Tanggal upload sampai (YYYY-MM-DD, inklusif)"),
    page: Page = 1,
    limit: Limit = 10,
):
    """Riwayat upload GeoJSON & Excel, terbaru di atas. `bulan`/`tahun` memfilter periode data."""
    return service.list_uploads(
        db, own_only_user_id=_own_only(db, current_user), search=search, status=status_filter,
        source_type=source_type, target_table=target_table, layer=layer, uploaded_by=uploaded_by,
        bulan=bulan, tahun=tahun, tanggal_dari=tanggal_dari, tanggal_sampai=tanggal_sampai, page=page, limit=limit,
    )


@router.get("/{batch_id}", response_model=UploadHistoryDetail)
def get_upload_history(batch_id: UUID, db: DbSession, current_user: CurrentUser):
    """Detail satu upload termasuk metadata (statistik/laporan proses)."""
    return service.get_upload(db, batch_id, own_only_user_id=_own_only(db, current_user))
