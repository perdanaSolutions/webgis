import json
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import Optional
import math

from datetime import datetime
from app.services.spatial_upload import process_geojson_upload

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
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    
    # UBAH DARI db.query(perusahaan) MENJADI HURUF KAPITAL:
    query = db.query(Perusahaan)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Perusahaan.nama_pt.ilike(search_filter),
                Perusahaan.kode_pt.ilike(search_filter)
            )
        )
        
    total_query = query.count()
    
    # UBAH JUGA DI SINI JIKA ADA YANG MASIH HURUF KECIL:
    data_orm = query.order_by(Perusahaan.nama_pt).limit(limit).offset(offset).all()

    formatted_data = []
    for row in data_orm:
        formatted_data.append({
            "id": row.pt_id,        
            "nama_pt": row.nama_pt,
            "kode_pt": row.kode_pt
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
    pt_id: Optional[int] = Query(None, description="Filter berdasarkan ID Perusahaan"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    query = db.query(Estate)
    
    # Filter relasi ke PT jika dikirim dari frontend
    if pt_id:
        query = query.filter(Estate.pt_id == pt_id)
        
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
            "id": row.est_id,  # Meng-alias composite string ID menjadi 'id' untuk Pydantic
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
    est_id: Optional[str] = Query(None, description="Filter berdasarkan ID Estate"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    query = db.query(Afdeling)
    
    if est_id:
        query = query.filter(Afdeling.est_id == est_id)
        
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
    afd_id: Optional[str] = Query(None, description="Filter berdasarkan ID Afdeling"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    query = db.query(Blok)
    
    if afd_id:
        query = query.filter(Blok.afd_id == afd_id)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Blok.nama_blok.ilike(search_filter),
                Blok.kode_blok.ilike(search_filter)
            )
        )
        
    total_query = query.count()
    data_orm = query.order_by(Blok.global_id).limit(limit).offset(offset).all()

    formatted_data = []
    for row in data_orm:
        formatted_data.append({
            "id": row.global_id,
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
    estate_id: Optional[str] = Query(None, description="Filter peta berdasarkan ID Estate saja"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    # Query gabungan Blok dengan GeoBlok menggunakan ORM + PostGIS function
    # func.ST_AsGeoJSON(GeoBlok.geom_polygon) mengubah biner EWKB menjadi string JSON spasial
    query = db.query(
        Blok, 
        func.ST_AsGeoJSON(GeoBlok.geom_polygon).label("geojson_geom")
    ).join(GeoBlok, Blok.global_id == GeoBlok.global_id)
    
    # Jika frontend memilih filter Estate tertentu, saring berdasarkan awalan ID blok
    if estate_id:
        query = query.filter(Blok.global_id.like(f"{estate_id}%"))
        
    results = query.all()
    
    # Merakit struktur standard FeatureCollection GeoJSON
    features = []
    for blok_data, geom_json_str in results:
        if not geom_json_str:
            continue
            
        features.append({
            "type": "Feature",
            "geometry": json.loads(geom_json_str), # Parse string JSON dari PostGIS menjadi Object
            "properties": {
                "global_id": blok_data.global_id,
                "nama_blok": blok_data.nama_blok,
                "kode_blok": blok_data.kode_blok,
                "afd_id": blok_data.afd_id,
                "tahun_tanam": blok_data.tahun_tanam,
                "jenis_bibit": blok_data.jenis_bibit,
                "status_tanam": blok_data.status_tanam
            }
        })
        
    geojson_response = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # Mengembalikan response langsung berbentuk aplikasi JSON murni
    return Response(content=json.dumps(geojson_response), media_type="application/json")

# endpoin upload blok
@router.post("/blocks/upload")
async def upload_blocks_geojson(
    bulan: int = Query(..., ge=1, le=12, description="Bulan periode data (1-12)"),
    tahun: int = Query(..., ge=2000, le=2100, description="Tahun periode data (YYYY)"),
    file: UploadFile = File(..., description="File GeoJSON Blok Spasial"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:write")) # Akses untuk level write/upload
):
    # 1. Catat inisialisasi awal ke dalam sys_upload_log
    log_query = text("""
        INSERT INTO sys_upload_log (source_type, target_table, source_name, status, meta_data)
        VALUES ('GEOJSON_UPLOAD', 'blok', :source_name, 'IN_PROGRESS', :meta_data)
        RETURNING upload_batch_id;
    """)
    
    meta_data_json = json.dumps({"bulan": bulan, "tahun": tahun})
    upload_batch_id = db.execute(log_query, {"source_name": file.filename, "meta_data": meta_data_json}).scalar()
    db.commit()

    try:
        # Read konten berkas spasial
        contents = await file.read()
        
        # Eksekusi parser service spatial
        total_records = process_geojson_upload(db=db, geojson_content=contents, bulan=bulan, tahun=tahun)
        
        # 2. Update log status sukses
        update_success_query = text("""
            UPDATE sys_upload_log 
            SET status = 'SUCCESS', record_count = :record_count, finished_at = :finished_at
            WHERE upload_batch_id = :batch_id;
        """)
        db.execute(update_success_query, {
            "record_count": total_records, 
            "finished_at": datetime.now(), 
            "batch_id": upload_batch_id
        })
        db.commit()

        return {
            "status": "success",
            "message": f"Berhasil mengunggah file {file.filename}.",
            "detail": f"{total_records} data blok spasial berhasil disimpan/diperbarui.",
            "upload_batch_id": str(upload_batch_id)
        }

    except Exception as e:
        # 1. ISI ROLLBACK DISINI UNTUK MERESET TRANSAKSI YANG ERROR
        db.rollback() 
        
        # 2. Update log status gagal
        update_fail_query = text("""
            UPDATE sys_upload_log 
            SET status = 'FAILED', error_message = :error_message, finished_at = :finished_at
            WHERE upload_batch_id = :batch_id;
        """)
        db.execute(update_fail_query, {
            "error_message": str(e), 
            "finished_at": datetime.now(), 
            "batch_id": upload_batch_id
        })
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Gagal memproses berkas spasial: {str(e)}")