"""
Router endpoint spasial: Area, PT, Estate, Afdeling, Blok, GeoJSON (Blok & TPH),
upload (TPH & Geometri Blok), dan cleanup periode.

CATATAN REFACTOR:
1. Logika "kalau bulan/tahun tidak diisi, pakai periode paling terbaru dari DB"
   sebelumnya diulang identik di 5 endpoint (area, pt, estate, afdeling, blok).
   Sekarang diekstrak ke helper `_apply_period_filter`.
2. Logika pagination (hitung total, offset, total_page, bentuk response dict)
   diulang di 5 endpoint yang sama -> diekstrak ke helper `_paginate`.
3. ENDPOINT BARU: `GET /tph/geojson` -- setara dengan `GET /geojson` (blok)
   tapi untuk titik TPH (geo_tph), mengembalikan FeatureCollection GeoJSON.
   Endpoint ini butuh model `GeoTph` yang BELUM ada di app/models/spatial.py
   (tabel geo_tph sebelumnya hanya disentuh lewat raw SQL di service upload).
   Tambahkan model berikut ke app/models/spatial.py (sesuaikan tipe kolom
   dengan skema aslimu, khususnya nama kolom Geometry-nya):

       class GeoTph(Base):
           __tablename__ = "geo_tph"
           id = Column(Integer, primary_key=True)
           blok_id = Column(String, ForeignKey("blok.blok_id"))
           geom_point = Column(Geometry("POINT", srid=4326))
           kategori = Column(String, nullable=True)
           bulan = Column(Integer)
           tahun = Column(Integer)

4. FIX INKONSISTENSI KEAMANAN: endpoint `POST /tph/upload-execute` sebelumnya
   tidak punya dependency `current_user`, jadi tidak terproteksi login,
   berbeda dari endpoint upload lain. Sekarang ditambahkan.
5. FIX INKONSISTENSI PERIODE: endpoint `GET /geojson` (blok) sebelumnya TIDAK
   fallback ke "periode terbaru" ketika bulan/tahun kosong (endpoint list
   lain semuanya fallback). Sekarang dibuat konsisten lewat `_apply_period_filter`.
   Endpoint `GET /tph/geojson` yang baru juga mengikuti perilaku yang sama.
6. Blok kode yang di-comment (endpoint upload lama yang sudah digantikan
   versi aktifnya) dihapus supaya file lebih bersih. Kalau masih perlu jadi
   referensi, sebaiknya disimpan di git history, bukan di file aktif.

Nama route, parameter, dan bentuk response TIDAK diubah (kecuali penambahan
proteksi login di poin 4 dan fallback periode di poin 5), supaya kompatibel
dengan frontend yang sudah ada.
"""

import json
import math
from typing import Callable, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import and_, desc, func, or_, text
from sqlalchemy.orm import Session

from app.api import deps
from app.models.spatial import Afdeling, Area, Blok, Estate, GeoBlok, GeoTph, Perusahaan
from app.schemas.spatial import BlokResponse, EstateResponse, GeoJSONResponse, PaginatedResponse, PTResponse
from app.services import spatial_upload as service
from app.services import blok_detail_service

router = APIRouter()


# =====================================================================
# HELPERS BERSAMA (menggantikan logika yang sebelumnya copy-paste)
# =====================================================================

def _apply_period_filter(db: Session, query, model, bulan: Optional[int], tahun: Optional[int]):
    """
    Terapkan filter bulan/tahun pada query. Jika keduanya kosong, otomatis
    pakai periode (bulan, tahun) paling terbaru yang ada di tabel `model`.
    """
    if bulan is not None or tahun is not None:
        if bulan is not None:
            query = query.filter(model.bulan == bulan)
        if tahun is not None:
            query = query.filter(model.tahun == tahun)
        return query

    latest_period = (
        db.query(model.tahun, model.bulan)
        .order_by(desc(model.tahun), desc(model.bulan))
        .first()
    )
    if latest_period:
        latest_tahun, latest_bulan = latest_period
        query = query.filter(model.tahun == latest_tahun, model.bulan == latest_bulan)
    return query


def _paginate(query, order_col, page: int, limit: int, formatter: Callable) -> dict:
    """Jalankan query dengan pagination lalu bentuk response standar PaginatedResponse."""
    offset = (page - 1) * limit
    total_query = query.count()
    data_orm = query.order_by(order_col).limit(limit).offset(offset).all()

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit) if total_query > 0 else 1,
        "data": [formatter(row) for row in data_orm],
    }


# =====================================================================
# ENDPOINT AREA
# =====================================================================

@router.get("/area", response_model=PaginatedResponse)
def get_area_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode area"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    query = db.query(Area)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Area.nama.ilike(search_filter),
                Area.kode_area.ilike(search_filter),
                Area.area_id.ilike(search_filter),
            )
        )

    query = _apply_period_filter(db, query, Area, bulan, tahun)

    return _paginate(
        query,
        Area.nama,
        page,
        limit,
        lambda row: {
            "id": row.id,
            "area_id": row.area_id,
            "nama": row.nama,
            "kode_area": row.kode_area,
            "bulan": row.bulan,
            "tahun": row.tahun,
        },
    )


# =====================================================================
# ENDPOINT PT (Dengan Server-Side Search)
# =====================================================================

@router.get("/pt", response_model=PaginatedResponse)
def get_pt_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode PT"),
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode PT"),
    area_id: Optional[str] = Query(None, description="Filter berdasarkan ID Area (contoh: AR_BERAU)"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    query = db.query(Perusahaan)

    if kode_pt:
        query = query.filter(Perusahaan.kode_pt == kode_pt)

    if area_id:
        query = query.filter(Perusahaan.area_id == area_id)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Perusahaan.nama_pt.ilike(search_filter),
                Perusahaan.kode_pt.ilike(search_filter),
            )
        )

    query = _apply_period_filter(db, query, Perusahaan, bulan, tahun)

    return _paginate(
        query,
        Perusahaan.nama_pt,
        page,
        limit,
        lambda row: {
            "id": row.pt_id,
            "nama_pt": row.nama_pt,
            "kode_pt": row.kode_pt,
            "area_id": row.area_id,
            "nama_area": row.area.nama if row.area else None,
            "bulan": getattr(row, "bulan", None),
            "tahun": getattr(row, "tahun", None),
        },
    )


# =====================================================================
# ENDPOINT ESTATE
# =====================================================================

@router.get("/estate", response_model=PaginatedResponse)
def get_estate_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode Estate"),
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode Perusahaan"),
    kode_est: Optional[str] = Query(None, description="Filter berdasarkan kode Estate"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    query = db.query(Estate)

    if kode_pt:
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)

    if kode_est:
        query = query.filter(Estate.kode_est == kode_est)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Estate.nama_estate.ilike(search_filter),
                Estate.kode_est.ilike(search_filter),
            )
        )

    query = _apply_period_filter(db, query, Estate, bulan, tahun)

    return _paginate(
        query,
        Estate.nama_estate,
        page,
        limit,
        lambda row: {
            "id": row.est_id,
            "pt_id": row.pt_id,
            "nama_estate": row.nama_estate,
            "kode_est": row.kode_est,
            "bulan": row.bulan,
            "tahun": row.tahun,
        },
    )


# =====================================================================
# ENDPOINT AFDELING
# =====================================================================

@router.get("/afdeling", response_model=PaginatedResponse)
def get_afdeling_list(
    search: Optional[str] = Query(None, description="Cari kode Afdeling"),
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode Perusahaan"),
    kode_est: Optional[str] = Query(None, description="Filter berdasarkan kode Estate"),
    kode_afd: Optional[str] = Query(None, description="Filter berdasarkan kode Afdeling"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    query = db.query(Afdeling)

    joined_estate = False
    if kode_pt:
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
        joined_estate = True

    if kode_est:
        if not joined_estate:
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.filter(Estate.kode_est == kode_est)

    if kode_afd:
        query = query.filter(Afdeling.kode_afd == kode_afd)

    if search:
        query = query.filter(Afdeling.kode_afd.ilike(f"%{search}%"))

    query = _apply_period_filter(db, query, Afdeling, bulan, tahun)

    return _paginate(
        query,
        Afdeling.kode_afd,
        page,
        limit,
        lambda row: {
            "id": row.afd_id,
            "est_id": row.est_id,
            "kode_afd": row.kode_afd,
            "bulan": row.bulan,
            "tahun": row.tahun,
        },
    )


# =====================================================================
# ENDPOINT LIST DATA BLOK (Server-Side Pagination & Filter)
# =====================================================================

@router.get("/blok", response_model=PaginatedResponse)
def get_blok_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode Blok"),
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode Perusahaan"),
    kode_est: Optional[str] = Query(None, description="Filter berdasarkan kode Estate"),
    kode_afd: Optional[str] = Query(None, description="Filter berdasarkan kode Afdeling"),
    kode_blok: Optional[str] = Query(None, description="Filter berdasarkan kode Blok"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    query = db.query(Blok)

    joined_afdeling = False
    joined_estate = False

    if kode_pt:
        query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
        joined_afdeling = True
        joined_estate = True

    if kode_est:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        if not joined_estate:
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
            joined_estate = True
        query = query.filter(Estate.kode_est == kode_est)

    if kode_afd:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        query = query.filter(Afdeling.kode_afd == kode_afd)

    if kode_blok:
        query = query.filter(Blok.kode_blok == kode_blok)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Blok.nama_blok.ilike(search_filter),
                Blok.kode_blok.ilike(search_filter),
            )
        )

    query = _apply_period_filter(db, query, Blok, bulan, tahun)

    return _paginate(
        query,
        Blok.blok_id,
        page,
        limit,
        lambda row: {
            "id": row.blok_id,
            "afd_id": row.afd_id,
            "nama_blok": row.nama_blok,
            "kode_blok": row.kode_blok,
            "tipe_blok": row.tipe_blok,
            "jenis_topografi": row.jenis_topografi,
            "jenis_tanah": row.jenis_tanah,
            "jenis_bibit": row.jenis_bibit,
            "tahun_tanam": row.tahun_tanam,
            "status_tanam": row.status_tanam,
            "bulan": row.bulan,
            "tahun": row.tahun,
        },
    )


# =====================================================================
# ENDPOINT GEOJSON BLOK PETA (Polygon)
# =====================================================================

@router.get("/geojson")
def get_blocks_geojson(
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode Perusahaan"),
    kode_est: Optional[str] = Query(None, description="Filter berdasarkan kode Estate"),
    kode_afd: Optional[str] = Query(None, description="Filter berdasarkan kode Afdeling"),
    kode_blok: Optional[str] = Query(None, description="Filter berdasarkan kode Blok"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    query = db.query(
        Blok,
        func.ST_AsGeoJSON(GeoBlok.geom_polygon).label("geojson_geom"),
    ).join(GeoBlok, Blok.blok_id == GeoBlok.blok_id)

    joined_afdeling = False
    joined_estate = False

    if kode_pt:
        query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
        joined_afdeling = True
        joined_estate = True

    if kode_est:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        if not joined_estate:
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
            joined_estate = True
        query = query.filter(Estate.kode_est == kode_est)

    if kode_afd:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        query = query.filter(Afdeling.kode_afd == kode_afd)

    if kode_blok:
        query = query.filter(Blok.kode_blok == kode_blok)

    query = _apply_period_filter(db, query, Blok, bulan, tahun)

    results = query.all()

    # Ambil ringkasan 3 tabel trx untuk SEMUA blok yang tampil sekaligus
    # (1-3 query total, bukan per-blok) -- lihat blok_detail_service untuk
    # alasan kenapa cuma ringkasan (bukan semua kolom/riwayat lengkap) yang
    # di-embed di sini; info lengkap ada di GET /blok/detail.
    blok_ids = [blok_data.blok_id for blok_data, _ in results]
    resolved_bulan = results[0][0].bulan if results else bulan
    resolved_tahun = results[0][0].tahun if results else tahun
    trx_summary = blok_detail_service.fetch_trx_summary_by_blok(db, blok_ids, resolved_bulan, resolved_tahun)

    features = []
    for blok_data, geom_json_str in results:
        if not geom_json_str:
            continue

        properties = {
            "blok_id": blok_data.blok_id,
            "nama_blok": blok_data.nama_blok,
            "kode_blok": blok_data.kode_blok,
            "afd_id": blok_data.afd_id,
            "tahun_tanam": blok_data.tahun_tanam,
            "jenis_bibit": blok_data.jenis_bibit,
            "status_tanam": blok_data.status_tanam,
            "bulan": blok_data.bulan,
            "tahun": blok_data.tahun,
        }
        properties.update(trx_summary.get(blok_data.blok_id, {}))

        features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": json.loads(geom_json_str),
        })

    geojson_response = {"type": "FeatureCollection", "features": features}
    return Response(content=json.dumps(geojson_response), media_type="application/json")


# =====================================================================
# DETAIL BLOK UNTUK POPUP & HISTORY TRX (dipakai FE saat blok diklik di peta)
# =====================================================================

@router.get("/blok/detail", summary="Atribut Popup Peta Blok lengkap (Master, KPI Yield, BJR, Kg/pkk, SPH)")
def get_blok_detail(
    blok_id: str = Query(..., description="ID Blok yang diklik pada peta (misal: PT_TELEN_E006_AFDI02_G018)"),
    bulan: Optional[int] = Query(None, ge=1, le=12, description="Kosongkan untuk ambil periode terbaru"),
    tahun: Optional[int] = Query(None, ge=2000, description="Kosongkan untuk ambil periode terbaru"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user),
):
    return blok_detail_service.get_blok_detail(db, blok_id, bulan, tahun)


@router.get("/history/tables", summary="Daftar tabel/tema yang tersedia untuk GET /history")
def get_history_tables(current_user=Depends(deps.get_current_user)):
    return blok_detail_service.list_history_tables()

# =====================================================================
# ENDPOINT AKUMULASI HISTORY (BULANAN / TAHUNAN DENGAN HIERARKI)
# =====================================================================

@router.get("/history", summary="Data Akumulasi Bulanan/Tahunan untuk 3 Tabel Transaksi Spasial")
def get_history_data(
    table: str = Query(
        "trx_produksi_tbs", 
        description="Pilihan tabel: 'trx_produksi_tbs', 'trx_areal_statement', atau 'trx_rotasi_pusingan'"
    ),
    tahun: Optional[int] = Query(None, ge=2000, description="Kosongkan untuk akumulasi Tahunan (Multi-Year), isi untuk akumulasi Bulanan"),
    area_id: Optional[str] = Query(None, description="Filter tingkat Area"),
    kode_pt: Optional[str] = Query(None, description="Filter tingkat PT"),
    kode_est: Optional[str] = Query(None, description="Filter tingkat Estate"),
    kode_afd: Optional[str] = Query(None, description="Filter tingkat Afdeling"),
    blok_id: Optional[str] = Query(None, description="Filter tingkat Blok Spesifik"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user),
):
    return blok_detail_service.get_history_aggregated(
        db=db,
        table=table,
        tahun=tahun,
        area_id=area_id,
        kode_pt=kode_pt,
        kode_est=kode_est,
        kode_afd=kode_afd,
        blok_id=blok_id
    )


# =====================================================================
# ENDPOINT GEOJSON TPH TITIK (Point) -- BARU
# =====================================================================

@router.get("/tph/geojson", summary="Tampilkan Titik TPH sebagai GeoJSON FeatureCollection")
def get_tph_geojson(
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode Perusahaan"),
    kode_est: Optional[str] = Query(None, description="Filter berdasarkan kode Estate"),
    kode_afd: Optional[str] = Query(None, description="Filter berdasarkan kode Afdeling"),
    kode_blok: Optional[str] = Query(None, description="Filter berdasarkan kode Blok"),
    kategori: Optional[str] = Query(None, description="Filter berdasarkan kategori TPH"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Setara dengan `/geojson` (blok/polygon) tapi untuk titik TPH (geo_tph).
    Di-join ke Blok/Afdeling/Estate/Perusahaan supaya bisa difilter dengan
    kode hierarki yang sama seperti endpoint lain, dan supaya properti hasil
    GeoJSON menyertakan info blok induknya.
    """
    query = db.query(
        GeoTph,
        Blok,
        func.ST_AsGeoJSON(GeoTph.geom_point).label("geojson_geom"),
    ).join(Blok, GeoTph.blok_id == Blok.blok_id)

    joined_afdeling = False
    joined_estate = False

    if kode_pt:
        query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
        joined_afdeling = True
        joined_estate = True

    if kode_est:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        if not joined_estate:
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
            joined_estate = True
        query = query.filter(Estate.kode_est == kode_est)

    if kode_afd:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        query = query.filter(Afdeling.kode_afd == kode_afd)

    if kode_blok:
        query = query.filter(Blok.kode_blok == kode_blok)

    if kategori:
        query = query.filter(GeoTph.kategori == kategori)

    # Periode mengikuti data titik TPH itu sendiri (GeoTph.bulan/tahun),
    # karena satu blok bisa saja punya titik TPH untuk beberapa periode.
    query = _apply_period_filter(db, query, GeoTph, bulan, tahun)

    results = query.all()

    features = []
    for tph_data, blok_data, geom_json_str in results:
        if not geom_json_str:
            continue

        features.append({
            "type": "Feature",
            "properties": {
                "tph_id": tph_data.id,
                "blok_id": blok_data.blok_id,
                "nama_blok": blok_data.nama_blok,
                "kode_blok": blok_data.kode_blok,
                "afd_id": blok_data.afd_id,
                "kategori": tph_data.kategori,
                "bulan": tph_data.bulan,
                "tahun": tph_data.tahun,
            },
            "geometry": json.loads(geom_json_str),
        })

    geojson_response = {"type": "FeatureCollection", "features": features}
    return Response(content=json.dumps(geojson_response), media_type="application/json")


# =====================================================================
# FLOW UPLOAD: GEOMETRI BLOK (POLYGON) -- DENGAN PROTEKSI LOGIN
# =====================================================================

@router.post("/blok-geometry/upload-analyze", summary="POLYGON TAHAP 1: Analisis Kesesuaian Peta")
async def upload_geometry_analyze(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=2000),
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    contents = await file.read()
    return service.analyze_geojson_geometry_blok(db, contents, bulan, tahun)


@router.post("/blok-geometry/upload-execute", summary="POLYGON TAHAP 2: Bulk Save Geometri Map")
async def upload_blok_geometry(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    contents = await file.read()
    result = service.execute_bulk_geometry_blok(
        db=db,
        geojson_content=contents,
        filename=file.filename,
        bulan=bulan,
        tahun=tahun,
        user_id=current_user.id,
    )
    return {"status": "success", "data": result}


# =====================================================================
# FLOW UPLOAD: MASTER DATA TPH (POINT) -- DENGAN PROTEKSI LOGIN
# =====================================================================

@router.post("/tph/upload-analyze", summary="TPH TAHAP 1: Analisis Atribut Master")
async def upload_tph_analyze(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=2000),
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    contents = await file.read()
    return service.analyze_geojson_tph(db, contents, bulan, tahun)


@router.post("/tph/upload-execute", summary="TPH TAHAP 2: Bulk Save Master Atribut")
async def upload_tph_execute(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),  # <-- FIX: sebelumnya endpoint ini tidak terproteksi login
):
    contents = await file.read()
    stats = service.execute_bulk_tph(db, contents, bulan, tahun)

    return {
        "status": "success",
        "message": f"Proses unggah data spasial TPH periode {bulan}-{tahun} selesai.",
        "detail": stats,
    }


# =====================================================================
# AKSI HAPUS DATA PERIODE (CLEANUP DATA)
# =====================================================================

@router.delete("/cleanup-period", summary="Hapus Semua Data Spasial & Atribut Berdasarkan Periode")
def delete_period_data(
    bulan: int = Query(..., ge=1, le=12, description="Bulan data yang ingin dibersihkan"),
    tahun: int = Query(..., ge=2000, description="Tahun data yang ingin dibersihkan"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Gunakan ini jika terjadi kesalahan upload periode atau ingin mereset data
    pada bulan dan tahun tertentu dari database.
    """
    return service.delete_spatial_data_by_period(db, bulan, tahun)