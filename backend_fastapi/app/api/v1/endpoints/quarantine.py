from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.params import Limit, Page
from app.api.v1.endpoints.upload_history import _own_only
from app.schemas.common import PaginatedResponse
from app.services import quarantine_service as service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
def list_quarantine(
    db: DbSession,
    current_user: CurrentUser,
    upload_batch_id: UUID | None = Query(None, description="ID riwayat upload (batch_id hasil import)"),
    target_table: str | None = Query(None, description="Contoh: trx.block_productions, spatial.block_boundaries"),
    reason_code: str | None = Query(
        None, description="Mis. BLOK_TIDAK_DITEMUKAN, NILAI_TIDAK_VALID, KODE_BLOK_KOSONG, DUPLIKAT_BERTENTANGAN, "
                          "ATRIBUT_BLOK_KOSONG, GEOMETRI_TIDAK_VALID, OBJECTID_GANDA, GAGAL_DISIMPAN"),
    search: str | None = Query(None, description="Cari di alasan, isi data, atau nama file"),
    page: Page = 1,
    limit: Limit = 10,
):
    """Baris/fitur upload yang tidak lolos validasi, terbaru di atas. Fitur GeoJSON hanya menampilkan properti."""
    return service.list_rows(
        db, own_only_user_id=_own_only(db, current_user), upload_batch_id=upload_batch_id, target_table=target_table,
        reason_code=reason_code, search=search, page=page, limit=limit,
    )


@router.get("/{row_id}")
def get_quarantine(row_id: int, db: DbSession, current_user: CurrentUser):
    """Detail satu data karantina, termasuk data asli utuh (fitur GeoJSON beserta geometrinya)."""
    return service.get_row(db, row_id, own_only_user_id=_own_only(db, current_user))
