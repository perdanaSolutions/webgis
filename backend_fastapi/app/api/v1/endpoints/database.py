from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.services import access_service

router = APIRouter()


@router.get("/tables", response_model=list[str], summary="Tabel transaksi/spasial yang bisa dipilih sebagai hak akses transaksi")
def list_tables(db: DbSession, _: CurrentUser):
    return access_service.transaction_tables(db)
