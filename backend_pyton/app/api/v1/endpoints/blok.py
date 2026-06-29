from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.core.database import get_db
from app.models.blok import Blok
from sqlalchemy import text, bindparam

router = APIRouter(prefix="/blocks", tags=["Blocks & Filters"])

# ========================================================
# 1. FILTER DROPDOWN: AREAS
# ========================================================
@router.get("/filters/areas", response_model=List[str])
def get_filter_areas(db: Session = Depends(get_db)):
    """Mengambil semua nama Area unik dari tabel areas"""
    query = text("SELECT DISTINCT nama_area FROM public.areas WHERE nama_area IS NOT NULL ORDER BY nama_area")
    results = db.execute(query).fetchall()
    return [r[0] for r in results]


# ========================================================
# 2. FILTER DROPDOWN: ESTATES (Cascading)
# ========================================================
@router.get("/filters/estates")
def get_filter_estates(area: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Mengambil list Estate unik, terfilter berdasarkan Area jika ada"""
    if area:
        sql = text("""
            SELECT DISTINCT e.kode_est, e.nama_estate 
            FROM public.estates e
            JOIN public.areas a ON e.area_id = a.id
            WHERE a.nama_area = :area
            ORDER BY e.nama_estate
        """)
        results = db.execute(sql, {"area": area}).fetchall()
    else:
        sql = text("SELECT kode_est, nama_estate FROM public.estates ORDER BY nama_estate")
        results = db.execute(sql).fetchall()
        
    return [{"kodeest": r[0], "estate": r[1]} for r in results]


# ========================================================
# 3. FILTER DROPDOWN: AFDELINGS (Disesuaikan dengan Kolom DB)
# ========================================================
@router.get("/filters/afdelings")
def get_filter_afdelings(kodeest: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Mengambil list kode_afd unik karena kolom nama_afdeling tidak tersedia di DB"""
    if kodeest:
        sql = text("""
            SELECT DISTINCT af.kode_afd 
            FROM public.afdelings af
            JOIN public.estates e ON af.estate_id = e.id
            WHERE e.kode_est = :kodeest
            ORDER BY af.kode_afd
        """).bindparams(bindparam("kodeest", value=str(kodeest)))
    else:
        sql = text("SELECT DISTINCT kode_afd FROM public.afdelings ORDER BY kode_afd")
        
    results = db.execute(sql).fetchall()
    # FE akan menerima kodeafd dan afdeling dengan nilai teks yang sama
    return [{"kodeafd": r[0], "afdeling": r[0]} for r in results]


# ========================================================
# 4. DATA UTAMA: LIST TABEL BLOK
# ========================================================
@router.get("")
def get_blocks(
    area: Optional[str] = Query(None),
    kodeest: Optional[str] = Query(None),
    kodeafd: Optional[str] = Query(None),
    search_blok: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Mendapatkan data ringkas blok dengan join kolom af.kode_afd yang benar"""
    sql_base = """
        SELECT b.id, b.kode_blok, b.nama_blok, b.status_tanaman, b.luas_tanah, b.luas_tanam
        FROM public.bloks b
        JOIN public.afdelings af ON b.afdeling_id = af.id
        JOIN public.estates e ON af.estate_id = e.id
        JOIN public.areas a ON e.area_id = a.id
        WHERE 1=1
    """
    params = {"limit": limit}
    
    if area:
        sql_base += " AND a.nama_area = :area"
        params["area"] = area
    if kodeest:
        sql_base += " AND e.kode_est = :kodeest"
        params["kodeest"] = kodeest
    if kodeafd:
        # Diubah dari af.nama_afdeling / af.kode_afdeling menjadi af.kode_afd
        sql_base += " AND af.kode_afd = :kodeafd"
        params["kodeafd"] = kodeafd
    if search_blok:
        sql_base += " AND b.nama_blok ILIKE :search"
        params["search"] = f"%{search_blok}%"
        
    sql_base += " ORDER BY b.nama_blok LIMIT :limit"
    results = db.execute(text(sql_base), params).fetchall()
    
    return [
        {
            "objectid": r[0], "kode_blok": r[1], "blok": r[2], 
            "status": r[3], "ltanah": float(r[4]) if r[4] else 0.0, "ltanam": float(r[5]) if r[5] else 0.0
        } for r in results
    ]


# ========================================================
# 5. API KOORDINAT PETA (Format FeatureCollection)
# ========================================================
@router.get("/map/geojson")
def get_blocks_geojson(
    area: Optional[str] = Query(None),
    kodeest: Optional[str] = Query(None),
    kodeafd: Optional[str] = Query(None),
    search_blok: Optional[str] = Query(None, description="Filter peta berdasarkan nama/kode blok"),
    db: Session = Depends(get_db)
):
    """
    API Spasial GeoJSON untuk Frontend Map.
    Mendukung cascading filter wilayah, pencarian spesifik nama blok, 
    dan mengembalikan objek detail lengkap di dalam objek 'properties'.
    """
    # Ambil seluruh detail field dari tabel bloks untuk dimasukkan ke properties GeoJSON
    sql_base = """
        SELECT 
            b.id,
            b.kode_blok,
            b.nama_blok,
            b.ownership,
            b.tahun_tanam,
            b.bulan_tanam,
            b.topografi,
            b.jenis_tanah,
            b.jenis_bibit,
            b.status_tanaman,
            b.luas_tanah,
            b.luas_tanam,
            af.kode_afd,
            e.nama_estate,
            a.nama_area,
            ST_AsGeoJSON(b.geom)::json AS geometry
        FROM public.bloks b
        JOIN public.afdelings af ON b.afdeling_id = af.id
        JOIN public.estates e ON af.estate_id = e.id
        JOIN public.areas a ON e.area_id = a.id
        WHERE b.geom IS NOT NULL
    """
    params = {}
    
    # Penerapan filter wilayah bertingkat
    if area:
        sql_base += " AND a.nama_area = :area"
        params["area"] = area
    if kodeest:
        sql_base += " AND e.kode_est = :kodeest"
        params["kodeest"] = kodeest
    if kodeafd:
        sql_base += " AND af.kode_afd = :kodeafd"
        params["kodeafd"] = kodeafd
        
    # Fitur Baru: Filter pencarian blok langsung di peta
    if search_blok:
        sql_base += " AND (b.nama_blok ILIKE :search OR b.kode_blok ILIKE :search)"
        params["search"] = f"%{search_blok}%"

    results = db.execute(text(sql_base), params).fetchall()
    
    features = []
    for r in results:
        # Bungkus semua data kolom riil ke dalam properties GeoJSON secara detail
        feature = {
            "type": "Feature",
            "geometry": r[15],  # Objek JSON geometri hasil PostGIS ST_AsGeoJSON
            "properties": {
                "id": r[0],
                "kode_blok": r[1],
                "blok": r[2],
                "ownership": r[3],
                "tahun_tanam": r[4],
                "bulan_tanam": r[5],
                "topografi": r[6],
                "jenis_tanah": r[7],
                "jenis_bibit": r[8],
                "status": r[9],
                "luas_tanah": float(r[10]) if r[10] else 0.0,
                "luas_tanam": float(r[11]) if r[11] else 0.0,
                "afdeling": r[12],
                "estate": r[13],
                "area": r[14]
            }
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features
    }