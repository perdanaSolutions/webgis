"""Impor transaksi dari Excel atau JSON. Path Excel dipertahankan dari API lama."""
from typing import Annotated

from fastapi import APIRouter, Body, Query

from app.api.deps import CurrentUser, DbSession
from app.api.params import Bulan, Tahun, UploadedFile, read_upload
from app.core.exceptions import bad_request
from app.schemas.trx_import import TrxJsonImport
from app.services import trx_import_service
from app.services.trx_import_service import AREA_STATEMENT, PRODUCTION, ROTATION, ImportScope

areal_statement_router = APIRouter()
production_router = APIRouter()
rotation_router = APIRouter()

UnitCodeParam = Annotated[str | None, Query(max_length=50, description="Kode estate (UnitCode), mis. E005")]


def _production_scope(year: int | None, month: int | None, unit_code: str | None) -> ImportScope | None:
    """Parameter year + month + unit_code harus diisi bersamaan (atau tidak sama sekali)."""
    given = [v is not None and str(v).strip() != "" for v in (year, month, unit_code)]
    if not any(given):
        return None
    if not all(given):
        raise bad_request("Parameter year, month, dan unit_code harus diisi bersamaan.", "year")
    return ImportScope(year=year, month=month, unit_code=unit_code.strip())


_JSON_DOC = "Nama kolom tiap baris sama dengan header Excel; validasi & upsert per blok & bulan juga sama."

_AREA_JSON_DOC = (
    _JSON_DOC + "\n\n"
    "**Kolom areal statement (sama dengan 24 kolom Excel):** Year, Month, AreaCode, CompanyCode, Estate, UnitCode, "
    "EstateShortName, DivisionCode, KodeBlok, TipeBlok, StatusTanam, TahunTanam, BulanTanam, LuasTanam, LuasTanah, "
    "TotalPokok, SPH, JenisBibit, JenisTopografi, TanahDatar, Berbukit, Gelombang, Curam, JenisTanah. "
    "Contoh di bawah memuat seluruhnya.\n\n"
    "- **Wajib:** periode (Year + Month), AreaCode, StatusTanam, KodeBlok, DivisionCode, dan satu penanda estate "
    "(UnitCode, EstateShortName, atau Estate).\n"
    "- **Pencocokan blok:** estate + DivisionCode + KodeBlok harus persis ada di master; kalau tidak, baris ditolak "
    "(masuk karantina) dengan alasan BLOK_TIDAK_DITEMUKAN.\n"
    "- **Opsional:** kolom lainnya. Yang tidak dikirim disimpan kosong (null). JenisBibit majemuk boleh dipisah "
    "koma, '/', ';', '+', '&', atau 'dan'. Persentase topografi (TanahDatar, Berbukit, Gelombang, Curam) 0-100 "
    "dengan jumlah maksimal 100.\n"
    "- **CompanyCode:** hanya dibandingkan dengan PT blok di master; bila berbeda, baris tetap diproses dan muncul "
    "sebagai `peringatan_company_code` di hasil.\n"
    "- Nama kolom alternatif yang juga diterima antara lain Tahun/Bulan (pengganti Year/Month)."
)


_PROD_JSON_DOC = (
    _JSON_DOC + "\n\n"
    "**Kolom produksi TBS (sama dengan 14 kolom Excel):** Year, Month, UnitCode, DivisionCode, KodeBlok, TbsAktual, "
    "TbsBudget, TbsSensus, JanjangAktual, JanjangBudget, JanjangSensus, BjrAktual, BjrBudget, BjrSensus. "
    "Contoh di bawah memuat seluruhnya.\n\n"
    "- **Wajib:** periode (Year + Month), KodeBlok, DivisionCode, dan satu penanda estate (UnitCode, EstateShortName, "
    "atau Estate).\n"
    "- **Pencocokan blok:** estate + DivisionCode + KodeBlok harus persis ada di master; kalau tidak, baris ditolak "
    "(masuk karantina) dengan alasan BLOK_TIDAK_DITEMUKAN.\n"
    "- **Opsional:** sembilan kolom nilai (TBS dalam kg, janjang, BJR); yang tidak dikirim disimpan kosong (null). "
    "Nilai negatif ditolak.\n"
    "- **Parameter query `year`, `month`, `unit_code` (opsional, harus diisi bersamaan):** sistem mengecek dulu "
    "apakah data produksi estate & bulan itu sudah ada. Bila sudah ada, data lama DITIMPA dengan isi yang dikirim; "
    "blok di estate & bulan itu yang tidak ikut dikirim lagi ikut DIHAPUS. Kolom Year/Month/UnitCode di baris boleh "
    "dikosongkan (diisi dari parameter); bila diisi, harus sama dengan parameter, kalau tidak barisnya ditolak.\n"
    "- **Tanpa parameter:** estate & bulan yang ditimpa diambil dari isi file (kombinasi Year + Month + UnitCode pada "
    "baris yang valid), dengan aturan yang sama.\n"
    "- Blok yang muncul di file (termasuk yang barisnya ditolak) tidak dihapus, dan file tanpa baris valid tidak "
    "menghapus apa pun. Hasilnya memuat `mode` (TIMPA bila data lama ditemukan, BARU bila belum ada), "
    "`data_lama_ditemukan`, dan `data_lama_dihapus`.\n"
    "- **Baris ganda** untuk blok & bulan yang sama: bila hanya satu yang punya TbsAktual/JanjangAktual, itu yang "
    "dipakai; bila beberapa berbeda, semuanya ditolak (masuk karantina).\n"
    "- Nama kolom alternatif yang juga diterima antara lain Tahun/Bulan (pengganti Year/Month)."
)

_ROT_JSON_DOC = (
    _JSON_DOC + "\n\n"
    "**Kolom rotasi & pusingan (sama dengan header Excel):** Periode, Area, PT, Estate, Afdeling, Blok, Luas, Pokok, "
    "Rotasi, Pusingan, Status Pusingan, Bulan, BulanID, Tanggal. Contoh di bawah memuat seluruhnya.\n\n"
    "- **Wajib:** tahun (Periode, atau Tahun), bulan (Bulan berupa angka atau nama seperti 'Jan', atau diambil dari "
    "Tanggal berformat YYYY-MM-DD), Blok, Afdeling, dan penanda estate (UnitCode atau Estate).\n"
    "- **Pencocokan blok:** estate + Afdeling + Blok harus persis ada di master; kalau tidak, baris ditolak "
    "(masuk karantina) dengan alasan BLOK_TIDAK_DITEMUKAN.\n"
    "- **Opsional:** Luas (ha), Pokok, Rotasi, Pusingan (hari), dan Status Pusingan; yang tidak dikirim disimpan kosong. "
    "Nilai negatif ditolak.\n"
    "- **Area, PT, dan BulanID** boleh dikirim tetapi tidak disimpan; bulan diambil dari Bulan atau Tanggal."
)

@areal_statement_router.post("/import-excel", summary="Import Areal Statement dari Excel (upsert per blok & bulan)")
def import_area_statements(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_area_statements(db, file.filename, read_upload(file), user.id)


@areal_statement_router.post("/import-json", summary="Import Areal Statement dari JSON (upsert per blok & bulan)",
                             description=_AREA_JSON_DOC)
def import_area_statements_json(db: DbSession, user: CurrentUser, payload: TrxJsonImport = Body(openapi_examples={
    "lengkap": {"summary": "Seluruh 24 kolom", "value": {"sumber": "SAP", "data": [{
        "Year": 2026, "Month": 1, "AreaCode": "KUTIM2", "CompanyCode": 1500, "Estate": "Long Mesangat Estate",
        "UnitCode": "E013", "EstateShortName": "LME", "DivisionCode": "AFDI04", "KodeBlok": "H033",
        "TipeBlok": "Inti", "StatusTanam": "TM", "TahunTanam": 2007, "BulanTanam": "Sep", "LuasTanam": 41.38,
        "LuasTanah": 42.16, "TotalPokok": 5726, "SPH": 138.38, "JenisBibit": "Socfin", "JenisTopografi": "DATAR",
        "TanahDatar": 100, "Berbukit": 0, "Gelombang": 0, "Curam": 0, "JenisTanah": "TANAH MINERAL"}]}},
    "minimal": {"summary": "Hanya kolom wajib", "value": {"data": [{
        "Year": 2026, "Month": 1, "AreaCode": "KUTIM2", "UnitCode": "E013", "DivisionCode": "AFDI04",
        "KodeBlok": "H033", "StatusTanam": "TM"}]}},
})):
    return trx_import_service.import_json(db, AREA_STATEMENT, payload.data, payload.sumber, user.id)


@production_router.post("/import-produksi-tbs", summary="Import Produksi TBS dari Excel (ganti per tahun, bulan & estate)")
def import_productions(db: DbSession, user: CurrentUser, file: UploadedFile,
                       year: Tahun = None, month: Bulan = None, unit_code: UnitCodeParam = None):
    scope = _production_scope(year, month, unit_code)
    return trx_import_service.import_productions(db, file.filename, read_upload(file), user.id, scope)


@production_router.post("/import-json", summary="Import Produksi TBS dari JSON (ganti per tahun, bulan & estate)",
                        description=_PROD_JSON_DOC)
def import_productions_json(db: DbSession, user: CurrentUser, year: Tahun = None, month: Bulan = None,
                            unit_code: UnitCodeParam = None, payload: TrxJsonImport = Body(openapi_examples={
    "lengkap": {"summary": "Seluruh 14 kolom", "value": {"sumber": "SAP", "data": [{
        "Year": 2026, "Month": 1, "UnitCode": "E005", "DivisionCode": "AFDI01", "KodeBlok": "C012",
        "TbsAktual": 43630, "TbsBudget": 64290, "TbsSensus": 53020, "JanjangAktual": 2497, "JanjangBudget": 3681,
        "JanjangSensus": 3223, "BjrAktual": 17.47, "BjrBudget": 17.47, "BjrSensus": 16.45}]}},
    "minimal": {"summary": "Hanya kolom wajib", "value": {"data": [{
        "Year": 2026, "Month": 1, "UnitCode": "E005", "DivisionCode": "AFDI01", "KodeBlok": "C012"}]}},
})):
    scope = _production_scope(year, month, unit_code)
    return trx_import_service.import_json(db, PRODUCTION, payload.data, payload.sumber, user.id, scope)


@rotation_router.post("/import-rotasi-pusingan", summary="Import Rotasi & Pusingan dari Excel (upsert per blok & bulan)")
def import_rotations(db: DbSession, user: CurrentUser, file: UploadedFile):
    return trx_import_service.import_rotations(db, file.filename, read_upload(file), user.id)


@rotation_router.post("/import-json", summary="Import Rotasi & Pusingan dari JSON (upsert per blok & bulan)",
                      description=_ROT_JSON_DOC)
def import_rotations_json(db: DbSession, user: CurrentUser, payload: TrxJsonImport = Body(openapi_examples={
    "lengkap": {"summary": "Seluruh kolom Excel", "value": {"sumber": "SAP", "data": [{
        "Periode": 2026, "Area": "BERAU", "PT": "PT. INTI ENERGI KALTIM", "Estate": "Ampen Medang Estate",
        "Afdeling": "AFDI01", "Blok": "C012", "Luas": 26.55, "Pokok": 3709, "Rotasi": 4, "Pusingan": 3,
        "Status Pusingan": "Normal", "Bulan": "Jan", "BulanID": 1, "Tanggal": "2026-01-01"}]}},
    "minimal": {"summary": "Hanya kolom wajib", "value": {"data": [{
        "Periode": 2026, "Bulan": 1, "Estate": "Ampen Medang Estate", "Afdeling": "AFDI01", "Blok": "C012"}]}},
})):
    return trx_import_service.import_json(db, ROTATION, payload.data, payload.sumber, user.id)
