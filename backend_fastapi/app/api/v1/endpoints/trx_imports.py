"""Impor transaksi dari Excel atau JSON. Path Excel dipertahankan dari API lama."""
from fastapi import APIRouter, Body

from app.api.deps import CurrentUser, DbSession
from app.api.params import UploadedFile, read_upload
from app.schemas.trx_import import TrxJsonImport
from app.services import trx_import_service
from app.services.trx_import_service import AREA_STATEMENT, PRODUCTION, ROTATION

areal_statement_router = APIRouter()
production_router = APIRouter()
rotation_router = APIRouter()

_JSON_DOC = "Nama kolom tiap baris sama dengan header Excel; validasi & upsert per blok & bulan juga sama."


@areal_statement_router.post("/import-excel", summary="Import Areal Statement dari Excel (upsert per blok & bulan)")
def import_area_statements(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_area_statements(db, file.filename, read_upload(file), user.id)


@areal_statement_router.post("/import-json", summary="Import Areal Statement dari JSON (upsert per blok & bulan)",
                             description=_JSON_DOC)
def import_area_statements_json(db: DbSession, user: CurrentUser, payload: TrxJsonImport = Body(openapi_examples={
    "contoh": {"value": {"sumber": "SAP", "data": [{
        "UnitCode": "BEKE", "DivisionCode": "AFDI01", "KodeBlok": "A001", "Bulan": 12, "Tahun": 2025,
        "AreaCode": "BERAU", "StatusTanam": "TM", "TahunTanam": 2006, "BulanTanam": "Mar", "LuasTanam": 25.5,
        "LuasTanah": 26, "TotalPokok": 3500, "SPH": 137, "JenisBibit": "Socfindo", "TipeBlok": "Inti"}]}},
})):
    return trx_import_service.import_json(db, AREA_STATEMENT, payload.data, payload.sumber, user.id)


@production_router.post("/import-produksi-tbs", summary="Import Produksi TBS dari Excel (upsert per blok & bulan)")
def import_productions(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_productions(db, file.filename, read_upload(file), user.id)


@production_router.post("/import-json", summary="Import Produksi TBS dari JSON (upsert per blok & bulan)",
                        description=_JSON_DOC)
def import_productions_json(db: DbSession, user: CurrentUser, payload: TrxJsonImport = Body(openapi_examples={
    "contoh": {"value": {"sumber": "SAP", "data": [{
        "UnitCode": "BEKE", "DivisionCode": "AFDI01", "KodeBlok": "A001", "Bulan": 12, "Tahun": 2025,
        "TbsAktual": 12000, "TbsBudget": 10000, "TbsSensus": 11000, "JanjangAktual": 600, "BjrAktual": 20}]}},
})):
    return trx_import_service.import_json(db, PRODUCTION, payload.data, payload.sumber, user.id)


@rotation_router.post("/import-rotasi-pusingan", summary="Import Rotasi & Pusingan dari Excel (upsert per blok & bulan)")
def import_rotations(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_rotations(db, file.filename, read_upload(file), user.id)


@rotation_router.post("/import-json", summary="Import Rotasi & Pusingan dari JSON (upsert per blok & bulan)",
                      description=_JSON_DOC)
def import_rotations_json(db: DbSession, user: CurrentUser, payload: TrxJsonImport = Body(openapi_examples={
    "contoh": {"value": {"sumber": "SAP", "data": [{
        "UnitCode": "BEKE", "DivisionCode": "AFDI01", "KodeBlok": "A001", "Bulan": 12, "Tahun": 2025,
        "Rotasi": 3, "Pusingan": 9, "Status Pusingan": "Normal", "Luas": 25, "Pokok": 3400}]}},
})):
    return trx_import_service.import_json(db, ROTATION, payload.data, payload.sumber, user.id)
