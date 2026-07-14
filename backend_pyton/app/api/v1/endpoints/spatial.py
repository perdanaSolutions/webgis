import json
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import Optional
import math

from datetime import datetime
from app.services import spatial_upload as service

from app.api import deps
from app.schemas.spatial import PTResponse, EstateResponse, BlokResponse, PaginatedResponse, GeoJSONResponse
from app.models.spatial import Perusahaan, Estate, Afdeling, Blok, GeoBlok
from sqlalchemy import or_, and_


router = APIRouter()

# ==========================================
# 1. ENDPOINT PT (Dengan Server-Side Search)
# ==========================================
@router.get("/pt", response_model=PaginatedResponse)
def get_pt_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode PT"),
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode PT"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    
    query = db.query(Perusahaan)
    
    # Filter berdasarkan kode PT
    if kode_pt:
        query = query.filter(Perusahaan.kode_pt == kode_pt)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Perusahaan.nama_pt.ilike(search_filter),
                Perusahaan.kode_pt.ilike(search_filter)
            )
        )
    
    # Filter bulan dan tahun (jika ada di model Perusahaan)
    if bulan:
        query = query.filter(Perusahaan.bulan == bulan)
    if tahun:
        query = query.filter(Perusahaan.tahun == tahun)
        
    total_query = query.count()
    
    data_orm = query.order_by(Perusahaan.nama_pt).limit(limit).offset(offset).all()

    formatted_data = []
    for row in data_orm:
        formatted_data.append({
            "id": row.pt_id,        
            "nama_pt": row.nama_pt,
            "kode_pt": row.kode_pt,
            "bulan": row.bulan if hasattr(row, 'bulan') else None,
            "tahun": row.tahun if hasattr(row, 'tahun') else None
        })

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit) if total_query > 0 else 1,
        "data": formatted_data
    }

# ==================================================
# 2. ENDPOINT ESTATES (Menggantikan Area & Lama)
# ==================================================
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
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    query = db.query(Estate)
    
    # Filter berdasarkan kode PT (join dengan tabel Perusahaan)
    if kode_pt:
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
    
    # Filter berdasarkan kode Estate
    if kode_est:
        query = query.filter(Estate.kode_est == kode_est)
    
    # Filter bulan dan tahun
    if bulan:
        query = query.filter(Estate.bulan == bulan)
    if tahun:
        query = query.filter(Estate.tahun == tahun)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Estate.nama_estate.ilike(search_filter),
                Estate.kode_est.ilike(search_filter)
            )
        )
        
    total_query = query.count()
    data_orm = query.order_by(Estate.nama_estate).limit(limit).offset(offset).all()

    formatted_data = []
    for row in data_orm:
        formatted_data.append({
            "id": row.est_id,
            "pt_id": row.pt_id,
            "nama_estate": row.nama_estate,
            "kode_est": row.kode_est,
            "bulan": row.bulan,
            "tahun": row.tahun
        })

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit) if total_query > 0 else 1,
        "data": formatted_data
    }

# ==================================================
# 3. ENDPOINT AFDELING 
# ==================================================
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
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    query = db.query(Afdeling)
    
    # Filter berdasarkan kode PT (join dengan Estate dan Perusahaan)
    if kode_pt:
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
    
    # Filter berdasarkan kode Estate (join dengan Estate)
    if kode_est:
        if not kode_pt:  # Jika belum di-join
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.filter(Estate.kode_est == kode_est)
    
    # Filter berdasarkan kode Afdeling
    if kode_afd:
        query = query.filter(Afdeling.kode_afd == kode_afd)
    
    # Filter bulan dan tahun
    if bulan:
        query = query.filter(Afdeling.bulan == bulan)
    if tahun:
        query = query.filter(Afdeling.tahun == tahun)
        
    if search:
        query = query.filter(Afdeling.kode_afd.ilike(f"%{search}%"))
        
    total_query = query.count()
    data_orm = query.order_by(Afdeling.kode_afd).limit(limit).offset(offset).all()

    formatted_data = []
    for row in data_orm:
        formatted_data.append({
            "id": row.afd_id,
            "est_id": row.est_id,
            "kode_afd": row.kode_afd,
            "bulan": row.bulan,
            "tahun": row.tahun
        })

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit) if total_query > 0 else 1,
        "data": formatted_data
    }

# ============================================================
# 4. ENDPOINT LIST DATA BLOK (Server-Side Pagination & Filter)
# ============================================================
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
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    query = db.query(Blok)
    
    # Flag untuk tracking apakah sudah join
    joined_afdeling = False
    joined_estate = False
    
    # Filter berdasarkan kode PT (join dengan Afdeling, Estate, Perusahaan)
    if kode_pt:
        query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
        joined_afdeling = True
        joined_estate = True
    
    # Filter berdasarkan kode Estate (join dengan Afdeling dan Estate)
    if kode_est:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        if not joined_estate:
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
            joined_estate = True
        query = query.filter(Estate.kode_est == kode_est)
    
    # Filter berdasarkan kode Afdeling (join dengan Afdeling)
    if kode_afd:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        query = query.filter(Afdeling.kode_afd == kode_afd)
    
    # Filter berdasarkan kode Blok
    if kode_blok:
        query = query.filter(Blok.kode_blok == kode_blok)
    
    # Filter bulan dan tahun
    if bulan:
        query = query.filter(Blok.bulan == bulan)
    if tahun:
        query = query.filter(Blok.tahun == tahun)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Blok.nama_blok.ilike(search_filter),
                Blok.kode_blok.ilike(search_filter)
            )
        )
        
    total_query = query.count()
    data_orm = query.order_by(Blok.blok_id).limit(limit).offset(offset).all()

    formatted_data = []
    for row in data_orm:
        formatted_data.append({
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
            "tahun": row.tahun
        })

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit) if total_query > 0 else 1,
        "data": formatted_data
    }

# ============================================================
# 5. ENDPOINT GEOJSON BLOK PETA (Dengan Sinkronisasi Tabel Spasial)
# ============================================================
@router.get("/geojson")
def get_blocks_geojson(
    kode_pt: Optional[str] = Query(None, description="Filter berdasarkan kode Perusahaan"),
    kode_est: Optional[str] = Query(None, description="Filter berdasarkan kode Estate"),
    kode_afd: Optional[str] = Query(None, description="Filter berdasarkan kode Afdeling"),
    kode_blok: Optional[str] = Query(None, description="Filter berdasarkan kode Blok"),
    bulan: Optional[int] = Query(None, description="Filter berdasarkan bulan (1-12)"),
    tahun: Optional[int] = Query(None, description="Filter berdasarkan tahun"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    # Query gabungan Blok dengan GeoBlok menggunakan ORM + PostGIS function
    query = db.query(
        Blok, 
        func.ST_AsGeoJSON(GeoBlok.geom_polygon).label("geojson_geom")
    ).join(GeoBlok, Blok.blok_id == GeoBlok.blok_id)
    
    # Flag untuk tracking join
    joined_afdeling = False
    joined_estate = False
    joined_perusahaan = False
    
    # Filter berdasarkan kode PT
    if kode_pt:
        query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
        query = query.join(Estate, Afdeling.est_id == Estate.est_id)
        query = query.join(Perusahaan, Estate.pt_id == Perusahaan.pt_id)
        query = query.filter(Perusahaan.kode_pt == kode_pt)
        joined_afdeling = True
        joined_estate = True
        joined_perusahaan = True
    
    # Filter berdasarkan kode Estate
    if kode_est:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        if not joined_estate:
            query = query.join(Estate, Afdeling.est_id == Estate.est_id)
            joined_estate = True
        query = query.filter(Estate.kode_est == kode_est)
    
    # Filter berdasarkan kode Afdeling
    if kode_afd:
        if not joined_afdeling:
            query = query.join(Afdeling, Blok.afd_id == Afdeling.afd_id)
            joined_afdeling = True
        query = query.filter(Afdeling.kode_afd == kode_afd)
    
    # Filter berdasarkan kode Blok
    if kode_blok:
        query = query.filter(Blok.kode_blok == kode_blok)
    
    # Filter bulan dan tahun
    if bulan:
        query = query.filter(Blok.bulan == bulan)
    if tahun:
        query = query.filter(Blok.tahun == tahun)
        
    results = query.all()
    
    # Merakit struktur standard FeatureCollection GeoJSON
    features = []
    for blok_data, geom_json_str in results:
        if not geom_json_str:
            continue
            
        features.append({
            "type": "Feature",
            "properties": {
                "blok_id": blok_data.blok_id,
                "nama_blok": blok_data.nama_blok,
                "kode_blok": blok_data.kode_blok,
                "afd_id": blok_data.afd_id,
                "tahun_tanam": blok_data.tahun_tanam,
                "jenis_bibit": blok_data.jenis_bibit,
                "status_tanam": blok_data.status_tanam,
                "bulan": blok_data.bulan,
                "tahun": blok_data.tahun
            },
            "geometry": json.loads(geom_json_str)
        })
        
    geojson_response = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return Response(content=json.dumps(geojson_response), media_type="application/json")

# # endpoin upload blok
# @router.post("/blocks/upload")
# async def upload_blocks_geojson(
#     bulan: int = Query(..., ge=1, le=12, description="Bulan periode data (1-12)"),
#     tahun: int = Query(..., ge=2000, le=2100, description="Tahun periode data (YYYY)"),
#     file: UploadFile = File(..., description="File GeoJSON Blok Spasial"),
#     db: Session = Depends(deps.get_db),
#     current_user = Depends(deps.PermissionChecker("blok:write")) # Akses untuk level write/upload
# ):
#     # 1. Catat inisialisasi awal ke dalam sys_upload_log
#     log_query = text("""
#         INSERT INTO sys_upload_log (source_type, target_table, source_name, status, meta_data)
#         VALUES ('GEOJSON_UPLOAD', 'blok', :source_name, 'IN_PROGRESS', :meta_data)
#         RETURNING upload_batch_id;
#     """)
    
#     meta_data_json = json.dumps({"bulan": bulan, "tahun": tahun})
#     upload_batch_id = db.execute(log_query, {"source_name": file.filename, "meta_data": meta_data_json}).scalar()
#     db.commit()

#     try:
#         # Read konten berkas spasial
#         contents = await file.read()
        
#         # Eksekusi parser service spatial
#         total_records = process_geojson_upload(db=db, geojson_content=contents, bulan=bulan, tahun=tahun)
        
#         # 2. Update log status sukses
#         update_success_query = text("""
#             UPDATE sys_upload_log 
#             SET status = 'SUCCESS', record_count = :record_count, finished_at = :finished_at
#             WHERE upload_batch_id = :batch_id;
#         """)
#         db.execute(update_success_query, {
#             "record_count": total_records, 
#             "finished_at": datetime.now(), 
#             "batch_id": upload_batch_id
#         })
#         db.commit()

#         return {
#             "status": "success",
#             "message": f"Berhasil mengunggah file {file.filename}.",
#             "detail": f"{total_records} data blok spasial berhasil disimpan/diperbarui.",
#             "upload_batch_id": str(upload_batch_id)
#         }

#     except Exception as e:
#         # 1. ISI ROLLBACK DISINI UNTUK MERESET TRANSAKSI YANG ERROR
#         db.rollback() 
        
#         # 2. Update log status gagal
#         update_fail_query = text("""
#             UPDATE sys_upload_log 
#             SET status = 'FAILED', error_message = :error_message, finished_at = :finished_at
#             WHERE upload_batch_id = :batch_id;
#         """)
#         db.execute(update_fail_query, {
#             "error_message": str(e), 
#             "finished_at": datetime.now(), 
#             "batch_id": upload_batch_id
#         })
#         db.commit()
        
#         raise HTTPException(status_code=500, detail=f"Gagal memproses berkas spasial: {str(e)}")


# =====================================================================
# FLOW UPLOAD 1: MASTER DATA TPH (POINT) - DENGAN PROTEKSI LOGIN
# =====================================================================

@router.post("/tph/upload-analyze", summary="TPH TAHAP 1: Analisis Atribut Master")
async def upload_tph_analyze(
    bulan: int = Query(..., ge=1, le=12), 
    tahun: int = Query(..., ge=2000),
    file: UploadFile = File(...), 
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:write"))  # Proteksi Login & Hak Akses
):
    contents = await file.read()
    return service.analyze_geojson_tph(db, contents, bulan, tahun)

@router.post("/tph/upload-execute", summary="TPH TAHAP 2: Bulk Save Master Atribut")
# async def upload_tph_execute(
#     bulan: int = Query(..., ge=1, le=12), 
#     tahun: int = Query(..., ge=2000),
#     file: UploadFile = File(...), 
#     db: Session = Depends(deps.get_db),
#     current_user = Depends(deps.PermissionChecker("blok:write"))  # Proteksi Login & Hak Akses
# ):
#     contents = await file.read()
#     total = service.execute_bulk_tph(db, contents, bulan, tahun)
#     return {"status": "success", "detail": f"{total} baris data TPH periode {bulan}-{tahun} berhasil masuk ke database."}

async def upload_tph_execute(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    contents = await file.read()
    
    # Menampung hasil berupa dictionary statistik
    stats = service.execute_bulk_tph(db, contents, bulan, tahun)
    
    return {
        "status": "success",
        "message": f"Proses unggah data spasial TPH periode {bulan}-{tahun} selesai.",
        "detail": stats
    }


# =====================================================================
# FLOW UPLOAD 2: GEOMETRI BLOK (POLYGON) - DENGAN PROTEKSI LOGIN
# =====================================================================

@router.post("/blok-geometry/upload-analyze", summary="POLYGON TAHAP 1: Analisis Kesesuaian Peta")
async def upload_geometry_analyze(
    bulan: int = Query(..., ge=1, le=12), 
    tahun: int = Query(..., ge=2000),
    file: UploadFile = File(...), 
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:write"))  # Proteksi Login & Hak Akses
):
    contents = await file.read()
    return service.analyze_geojson_geometry_blok(db, contents, bulan, tahun)

@router.post("/blok-geometry/upload-execute", summary="POLYGON TAHAP 2: Bulk Save Geometri Map")
# async def upload_geometry_execute(
#     bulan: int = Query(..., ge=1, le=12), 
#     tahun: int = Query(..., ge=2000),
#     file: UploadFile = File(...), 
#     db: Session = Depends(deps.get_db),
#     current_user = Depends(deps.PermissionChecker("blok:write"))  # Proteksi Login & Hak Akses
# ):
#     contents = await file.read()
#     total = service.execute_bulk_geometry_blok(db, contents, bulan, tahun)
#     return {"status": "success", "detail": f"{total} data spasial polygon blok periode {bulan}-{tahun} berhasil disuntikkan."}


async def upload_geometry_execute(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    # ... (proses baca file geojson seperti biasa) ...
    contents = await file.read()
    
    # Panggil service yang kini mengembalikan dictionary statistik
    stats = service.execute_bulk_geometry_blok(db, contents, bulan, tahun)
    
    return {
        "status": "success",
        "message": f"Proses unggah spasial blok periode {bulan}-{tahun} selesai.",
        "detail": stats
    }

# ==========================================
# AKSI HAPUS DATA PERIODE (CLEANUP DATA)
# ==========================================
@router.delete("/cleanup-period", summary="Hapus Semua Data Spasial & Atribut Berdasarkan Periode")
def delete_period_data(
    bulan: int = Query(..., ge=1, le=12, description="Bulan data yang ingin dibersihkan"),
    tahun: int = Query(..., ge=2000, description="Tahun data yang ingin dibersihkan"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:write"))
):
    """
    Gunakan ini jika terjadi kesalahan upload periode atau ingin mereset data 
    pada bulan dan tahun tertentu dari database.
    """
    return service.delete_spatial_data_by_period(db, bulan, tahun)