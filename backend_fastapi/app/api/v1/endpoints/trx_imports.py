"""Impor Excel transaksi. Path dipertahankan dari API lama."""
from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.params import UploadedFile, read_upload
from app.services import trx_import_service

areal_statement_router = APIRouter()
production_router = APIRouter()
rotation_router = APIRouter()


@areal_statement_router.post("/import-excel", summary="Import Areal Statement dari Excel (upsert per blok & bulan)")
def import_area_statements(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_area_statements(db, file.filename, read_upload(file), user.id)


@production_router.post("/import-produksi-tbs", summary="Import Produksi TBS dari Excel (upsert per blok & bulan)")
def import_productions(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_productions(db, file.filename, read_upload(file), user.id)


@rotation_router.post("/import-rotasi-pusingan", summary="Import Rotasi & Pusingan dari Excel (upsert per blok & bulan)")
def import_rotations(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_rotations(db, file.filename, read_upload(file), user.id)
