from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from uuid import UUID
import json
import math

from app.api import deps
from app.schemas.spatial import PTResponse, EstateResponse, BlokResponse, PaginatedResponse, GeoJSONResponse

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
    where_clauses = []
    
    if search:
        where_clauses.append(f"(nama_pt ILIKE :search OR kode_pt ILIKE :search)")
        
    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    params = {"search": f"%{search}%"} if search else {}

    # Hitung total data
    total_query = db.execute(text(f"SELECT COUNT(*) FROM pts {where_str}"), params).scalar()
    
    # Ambil data ter-paginate
    data_query = db.execute(
        text(f"SELECT id, nama_pt, kode_pt FROM pts {where_str} ORDER BY nama_pt LIMIT {limit} OFFSET {offset}"),
        params
    ).mappings().all()

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit),
        "data": data_query
    }


# ==============================================
# 2. ENDPOINT ESTATES (Dengan Cascading & Search)
# ==============================================
@router.get("/estates", response_model=PaginatedResponse)
def get_estate_list(
    pt_id: Optional[UUID] = Query(None, description="Filter berdasarkan PT"),
    search: Optional[str] = Query(None, description="Cari nama/kode Estate"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    where_clauses = []
    params = {}

    if pt_id:
        where_clauses.append("pt_id = :pt_id")
        params["pt_id"] = pt_id
    if search:
        where_clauses.append("(nama_estate ILIKE :search OR kode_estate ILIKE :search)")
        params["search"] = f"%{search}%"

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total_query = db.execute(text(f"SELECT COUNT(*) FROM estates {where_str}"), params).scalar()
    
    data_query = db.execute(
        text(f"SELECT id, pt_id, nama_estate, kode_estate FROM estates {where_str} ORDER BY nama_estate LIMIT {limit} OFFSET {offset}"),
        params
    ).mappings().all()

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit),
        "data": data_query
    }


# ============================================================
# 3. ENDPOINT LIST DATA BLOK (Server-Side Pagination & Filter)
# ============================================================
@router.get("/blocks", response_model=PaginatedResponse)
def get_blocks_list(
    pt_id: Optional[UUID] = Query(None, description="Filter Blok berdasarkan PT"),
    estate_id: Optional[UUID] = Query(None, description="Filter Blok berdasarkan Estate"),
    search: Optional[str] = Query(None, description="Cari nama/kode Blok"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    offset = (page - 1) * limit
    where_clauses = []
    params = {}

    # Menggunakan JOIN jika filter dari level PT
    join_str = ""
    if pt_id:
        join_str = "JOIN estates e ON b.estate_id = e.id"
        where_clauses.append("e.pt_id = :pt_id")
        params["pt_id"] = pt_id
    if estate_id:
        where_clauses.append("b.estate_id = :estate_id")
        params["estate_id"] = estate_id
    if search:
        where_clauses.append("(b.nama_blok ILIKE :search OR b.kode_blok ILIKE :search)")
        params["search"] = f"%{search}%"

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total_query = db.execute(text(f"SELECT COUNT(*) FROM bloks b {join_str} {where_str}"), params).scalar()
    
    query_data = f"""
        SELECT b.id, b.estate_id, b.nama_blok, b.kode_blok, b.luas_ha, b.status_tanaman, b.komoditas 
        FROM bloks b {join_str} {where_str} 
        ORDER BY b.nama_blok LIMIT {limit} OFFSET {offset}
    """
    data_query = db.execute(text(query_data), params).mappings().all()

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit),
        "data": data_query
    }


# ============================================================
# 4. ENDPOINT GEOJSON BLOK PETA (Dengan Semua Multi-Filter Bawaan)
# ============================================================
@router.get("/blocks/geojson", response_model=GeoJSONResponse)
def get_blocks_geojson(
    pt_id: Optional[UUID] = Query(None, description="Filter peta skala PT"),
    estate_id: Optional[UUID] = Query(None, description="Filter peta skala Estate"),
    search: Optional[str] = Query(None, description="Sorot blok tertentu berdasarkan nama/kode"),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("blok:read"))
):
    where_clauses = []
    params = {}
    join_str = ""

    if pt_id:
        join_str = "JOIN estates e ON b.estate_id = e.id"
        where_clauses.append("e.pt_id = :pt_id")
        params["pt_id"] = pt_id
    if estate_id:
        where_clauses.append("b.estate_id = :estate_id")
        params["estate_id"] = estate_id
    if search:
        where_clauses.append("(b.nama_blok ILIKE :search OR b.kode_blok ILIKE :search)")
        params["search"] = f"%{search}%"

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query_str = f"""
        SELECT 
            b.id, b.nama_blok, b.kode_blok, b.luas_ha, b.status_tanaman, b.komoditas,
            ST_AsGeoJSON(b.geom) as geom_json 
        FROM bloks b {join_str} {where_str}
    """

    raw_data = db.execute(text(query_str), params).all()
    features = []
    
    for row in raw_data:
        geometry_dict = json.loads(row.geom_json) if row.geom_json else None
        if geometry_dict:
            features.append({
                "type": "Feature",
                "geometry": geometry_dict,
                "properties": {
                    "id": str(row.id),
                    "nama_blok": row.nama_blok,
                    "kode_blok": row.kode_blok,
                    "luas_ha": float(row.luas_ha) if row.luas_ha else 0.0,
                    "status_tanaman": row.status_tanaman,
                    "komoditas": row.komoditas
                }
            })
            
    return {"type": "FeatureCollection", "features": features}