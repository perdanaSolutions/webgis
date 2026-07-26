"""
Router untuk sistem jenis geo dinamis (1 tabel katalog `geo_jenis`, tanpa
level tema terpisah).

DESAIN KATALOG: `GET /geo/catalog` HANYA berfungsi sebagai "buku alamat" --
untuk jenis GENERIC (tabel dinamis, dibuat lewat `POST /geo/jenis`),
endpoint dihitung otomatis mengikuti pola `/geo/{kode}/...`. Untuk jenis
LEGACY (blok/tph/sawit/jalan/jembatan/landuse/slope -- tabel & endpoint-nya
SUDAH ADA sebelum sistem ini dibuat), endpoint yang dikembalikan adalah
URL ASLI yang disimpan apa adanya saat registrasi (lihat
`register_legacy_jenis`), BUKAN URL hasil proxy/dispatch. FE memanggil URL
itu langsung -- router ini tidak pernah meneruskan request ke endpoint lama.

PENTING SOAL URUTAN ROUTE: path literal seperti `/geo/catalog`,
`/geo/jenis` HARUS didaftarkan SEBELUM `/geo/{kode}` (catch-all 1 segmen),
karena FastAPI/Starlette mencocokkan route berdasar urutan deklarasi --
kalau `/geo/{kode}` didaftarkan lebih dulu, request ke `/geo/catalog` akan
"tertangkap" olehnya (kode="catalog") alih-alih oleh handler catalog yang
sebenarnya. (Router ini sekarang tidak lagi punya route `/geo/{kode}` sama
sekali -- lihat catatan di bawah -- tapi urutan ini tetap dijaga untuk
jaga-jaga kalau nanti ditambahkan lagi.)
"""

import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.services import geo_dynamic_service as service

router = APIRouter()


# =====================================================================
# SCHEMAS
# =====================================================================

class KolomSchema(BaseModel):
    nama_properti: str
    nama_kolom: str
    tipe: str  # boolean | integer | float | date | text
    nullable: bool = True


class JenisCreateRequest(BaseModel):
    kode: str
    nama: str
    deskripsi: Optional[str] = None
    geometry_type: str  # POINT | LINESTRING | POLYGON | MULTIPOINT | MULTILINESTRING | MULTIPOLYGON
    relasi_blok: bool = Field(True, description="Apakah data ini terikat ke blok_id (hierarki kebun)")
    kolom: List[KolomSchema]


class LegacyJenisRegisterRequest(BaseModel):
    kode: str
    nama: str
    deskripsi: Optional[str] = None
    table_name: str = Field(..., description="Nama tabel fisik yang SUDAH ADA, mis. 'geo_sawit'")
    geometry_type: str
    relasi_blok: bool = True
    endpoints: Dict[str, str] = Field(
        ...,
        description=(
            "URL asli yang SUDAH BERJALAN. Wajib ada key: upload_analyze, "
            "upload_execute, geojson. Opsional: list, cleanup_period. "
            'Contoh: {"upload_analyze": "/sawit/upload-analyze", '
            '"upload_execute": "/sawit/upload-execute", "geojson": "/sawit/geojson"}'
        ),
    )


# =====================================================================
# KATALOG -- SATU-SATUNYA ENDPOINT YANG DIPANGGIL FE UNTUK DAPAT SEMUA
# JENIS GEO (LAMA MAUPUN DINAMIS) BESERTA URL ENDPOINT-NYA MASING-MASING
# =====================================================================

@router.get("/geo/catalog", summary="Katalog seluruh jenis data geo (lama & dinamis) beserta endpoint masing-masing")
def get_catalog(
    search: Optional[str] = Query(None, description="Cari berdasarkan nama/kode jenis"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    jenis_list = service.list_jenis(db, search)
    return [
        {
            "kode": j["kode"],
            "nama": j["nama"],
            "deskripsi": j["deskripsi"],
            "geometry_type": j["geometry_type"],
            "relasi_blok": j["relasi_blok"],
            "handler_type": j["handler_type"],  # "GENERIC" (tabel dinamis) atau "LEGACY" (sudah ada sebelumnya)
            "endpoints": j["endpoints"] if j["endpoints"] else _default_generic_endpoints(j["kode"]),
        }
        for j in jenis_list
    ]
    


def _default_generic_endpoints(kode: str) -> dict:
    """Pola URL untuk jenis GENERIC (tabel dinamis) -- dihitung, bukan disimpan."""
    return {
        "upload_analyze": f"/geo/{kode}/upload-analyze",
        "upload_execute": f"/geo/{kode}/upload-execute",
        "geojson": f"/geo/{kode}/geojson",
        "list": f"/geo/{kode}",
        "cleanup_period": f"/geo/{kode}/cleanup-period",
    }


# =====================================================================
# MANAJEMEN JENIS DINAMIS (BUAT TABEL FISIK BARU)
# =====================================================================

@router.post("/geo/jenis/analyze-sample", summary="Analisis 1 file GeoJSON contoh -> usulan skema kolom & tipe geometry")
async def analyze_sample(
    file: UploadFile = File(...),
    current_user=Depends(deps.get_current_user),
):
    content = await file.read()
    return service.analyze_sample_geojson(content)


@router.get("/geo/jenis", summary="List semua jenis")
def get_jenis_list(
    search: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    return service.list_jenis(db, search)


@router.post("/geo/jenis", summary="Konfirmasi skema & buat jenis baru (CREATE TABLE otomatis)")
def create_jenis(
    payload: JenisCreateRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    return service.create_jenis(
        db=db,
        kode=payload.kode,
        nama=payload.nama,
        deskripsi=payload.deskripsi,
        geometry_type=payload.geometry_type,
        relasi_blok=payload.relasi_blok,
        kolom=[k.dict() for k in payload.kolom],
        created_by=str(current_user.id),
    )


# =====================================================================
# PENDAFTARAN JENIS "LAMA" (tabel & endpoint sudah ada -- TANPA CREATE
# TABLE, TANPA proxy/dispatch. Cukup daftarkan URL aslinya ke katalog.)
#
# Catatan: TIDAK ADA lagi endpoint generik `/geo/{kode}/upload-analyze`
# dkk. untuk jenis LEGACY -- FE memanggil URL asli yang dikembalikan
# `GET /geo/catalog` langsung (mis. `/sawit/upload-analyze`), bukan lewat
# router ini. Endpoint `/geo/{kode}/...` (generik) HANYA berlaku untuk
# jenis GENERIC yang tabelnya dibuat lewat `POST /geo/jenis`.
# =====================================================================

@router.post(
    "/geo/jenis/register-legacy",
    summary="Daftarkan jenis dengan tabel & endpoint yang sudah ada (blok/tph/sawit/dst) ke katalog",
)
def register_legacy_jenis(
    payload: LegacyJenisRegisterRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    return service.register_legacy_jenis(
        db=db, kode=payload.kode, nama=payload.nama, table_name=payload.table_name,
        geometry_type=payload.geometry_type, relasi_blok=payload.relasi_blok,
        endpoints=payload.endpoints, deskripsi=payload.deskripsi,
    )


@router.post(
    "/geo/jenis/seed-legacy",
    summary="Daftarkan sekaligus jenis lama yang sudah terisi di geo_legacy_registry.DEFAULT_LEGACY_JENIS -- idempotent",
)
def seed_legacy_jenis(db: Session = Depends(deps.get_db), current_user=Depends(deps.get_current_user)):
    from app.services import geo_legacy_registry as legacy
    return {"hasil": legacy.seed_default_legacy_jenis(db)}


# =====================================================================
# UPLOAD & TAMPILAN DATA GENERIK -- HANYA UNTUK JENIS DINAMIS (GENERIC)
# =====================================================================

def _reject_if_legacy(jenis: dict) -> None:
    """
    Guard keamanan: endpoint generik di bawah ini mengasumsikan struktur
    tabel dinamis (skema_kolom = daftar kolom sebenarnya, DELETE+COPY per
    periode langsung ke tabel). Untuk jenis LEGACY, `skema_kolom` cuma
    dokumentasi (bisa kosong/tidak lengkap) dan tabelnya adalah tabel
    PRODUKSI yang sudah ada -- kalau endpoint ini dipakai untuk jenis
    LEGACY, `execute_generic_upload` bisa salah DELETE/INSERT ke tabel
    produksi dengan asumsi kolom yang keliru. Karena itu ditolak eksplisit;
    pakai URL asli dari `GET /geo/catalog` untuk jenis LEGACY.
    """
    if jenis["handler_type"] == "LEGACY":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Jenis '{jenis['kode']}' adalah jenis LEGACY (tabel & endpoint sudah ada sebelumnya). "
                "Endpoint /geo/{kode}/... generik tidak berlaku untuk jenis ini -- pakai URL asli "
                "dari field 'endpoints' di GET /geo/catalog."
            ),
        )


@router.post("/geo/{kode}/upload-analyze", summary="[Jenis GENERIC] TAHAP 1: Analisis kesiapan data sebelum diunggah")
async def generic_upload_analyze(
    kode: str,
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=2000),
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    jenis = service.get_jenis_or_404(db, kode)
    _reject_if_legacy(jenis)
    contents = await file.read()
    return service.analyze_generic_upload(db, jenis, contents, bulan, tahun)


@router.post("/geo/{kode}/upload-execute", summary="[Jenis GENERIC] TAHAP 2: Eksekusi bulk upload data")
async def generic_upload_execute(
    kode: str,
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=2000),
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    jenis = service.get_jenis_or_404(db, kode)
    _reject_if_legacy(jenis)
    contents = await file.read()
    result = service.execute_generic_upload(
        db=db, jenis=jenis, geojson_content=contents, filename=file.filename,
        bulan=bulan, tahun=tahun, user_id=str(current_user.id),
    )
    return {"status": "success", "data": result}


@router.get("/geo/{kode}/geojson", summary="[Jenis GENERIC] Ambil data sebagai GeoJSON FeatureCollection")
def generic_geojson(
    kode: str,
    bulan: Optional[int] = Query(None),
    tahun: Optional[int] = Query(None),
    blok_id: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    jenis = service.get_jenis_or_404(db, kode)
    _reject_if_legacy(jenis)
    geojson_data = service.get_generic_geojson(db, jenis, bulan, tahun, blok_id)
    return Response(content=json.dumps(geojson_data), media_type="application/json")


@router.delete("/geo/{kode}/cleanup-period", summary="[Jenis GENERIC] Hapus data 1 jenis untuk periode tertentu")
def generic_cleanup_period(
    kode: str,
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=2000),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    jenis = service.get_jenis_or_404(db, kode)
    _reject_if_legacy(jenis)
    return service.delete_generic_period(db, jenis, bulan, tahun)


@router.get("/geo/{kode}", summary="[Jenis GENERIC] List data (tabel, tanpa geometry) dengan pagination")
def generic_list(
    kode: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    bulan: Optional[int] = Query(None),
    tahun: Optional[int] = Query(None),
    blok_id: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    jenis = service.get_jenis_or_404(db, kode)
    _reject_if_legacy(jenis)
    return service.get_generic_list(db, jenis, page, limit, bulan, tahun, blok_id)