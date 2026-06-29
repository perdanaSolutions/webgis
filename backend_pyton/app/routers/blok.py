"""
app/routers/blok.py — Endpoint spatial untuk data blok kebun
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.schemas.blok import BlokBase, BlokSummary

router = APIRouter()

TABLE = "tpa_sga_2026"


# ─────────────────────────────────────────────
#  GET /blok — List blok (tanpa geometry)
# ─────────────────────────────────────────────
@router.get("/blok", response_model=list[BlokBase])
def list_blok(
    area    : Optional[str] = Query(None, description="Filter by area (e.g. BERAU)"),
    estate  : Optional[str] = Query(None, description="Filter by estate name"),
    status  : Optional[str] = Query(None, description="Filter by status (TM/TBM/etc)"),
    tt      : Optional[int] = Query(None, description="Filter by tahun tanam"),
    limit   : int           = Query(100, le=1000),
    offset  : int           = Query(0),
    db      : Session       = Depends(get_db),
):
    filters = []
    params  = {"limit": limit, "offset": offset}

    if area:
        filters.append("area ILIKE :area")
        params["area"] = f"%{area}%"
    if estate:
        filters.append("estate ILIKE :estate")
        params["estate"] = f"%{estate}%"
    if status:
        filters.append("status = :status")
        params["status"] = status
    if tt:
        filters.append("tt = :tt")
        params["tt"] = tt

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = text(f"""
        SELECT objectid, globalid, area, pt, estate, blok, kode_blok,
               ownership, afdeling, tt, blntanam, status,
               ltanah, ltanam, pokok, sph, topografi, jenistanah
        FROM {TABLE}
        {where}
        ORDER BY estate, blok
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  GET /blok/{objectid} — Detail satu blok
# ─────────────────────────────────────────────
@router.get("/blok/{objectid}", response_model=BlokBase)
def get_blok(objectid: int, db: Session = Depends(get_db)):
    sql = text(f"""
        SELECT objectid, globalid, area, pt, estate, blok, kode_blok,
               ownership, afdeling, tt, blntanam, status,
               ltanah, ltanam, pokok, sph, topografi, jenistanah
        FROM {TABLE}
        WHERE objectid = :objectid
    """)
    row = db.execute(sql, {"objectid": objectid}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Blok tidak ditemukan")
    return dict(row)


# ─────────────────────────────────────────────
#  GET /blok/geojson — Semua blok sebagai FeatureCollection
# ─────────────────────────────────────────────
@router.get("/blok/geojson/all")
def get_geojson_all(
    area  : Optional[str] = Query(None),
    estate: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db    : Session       = Depends(get_db),
):
    filters = []
    params  = {}

    if area:
        filters.append("area ILIKE :area")
        params["area"] = f"%{area}%"
    if estate:
        filters.append("estate ILIKE :estate")
        params["estate"] = f"%{estate}%"
    if status:
        filters.append("status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = text(f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(feat), '[]'::jsonb)
        ) AS geojson
        FROM (
            SELECT jsonb_build_object(
                'type',       'Feature',
                'geometry',   ST_AsGeoJSON(geometry, 6)::jsonb,
                'properties', jsonb_build_object(
                    'objectid',  objectid,
                    'blok',      blok,
                    'kode_blok', kode_blok,
                    'estate',    estate,
                    'area',      area,
                    'tt',        tt,
                    'status',    status,
                    'ltanam',    ltanam,
                    'ltanah',    ltanah,
                    'pokok',     pokok,
                    'sph',       sph,
                    'ownership', ownership
                )
            ) AS feat
            FROM {TABLE}
            {where}
        ) sub
    """)

    result = db.execute(sql, params).scalar()
    return result


# ─────────────────────────────────────────────
#  GET /blok/geojson/bbox — Blok dalam bounding box
# ─────────────────────────────────────────────
@router.get("/blok/geojson/bbox")
def get_geojson_bbox(
    min_lon: float = Query(..., description="Longitude minimum"),
    min_lat: float = Query(..., description="Latitude minimum"),
    max_lon: float = Query(..., description="Longitude maximum"),
    max_lat: float = Query(..., description="Latitude maximum"),
    db     : Session = Depends(get_db),
):
    sql = text(f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(feat), '[]'::jsonb)
        ) AS geojson
        FROM (
            SELECT jsonb_build_object(
                'type',       'Feature',
                'geometry',   ST_AsGeoJSON(geometry, 6)::jsonb,
                'properties', jsonb_build_object(
                    'objectid',  objectid,
                    'blok',      blok,
                    'estate',    estate,
                    'ltanam',    ltanam,
                    'status',    status
                )
            ) AS feat
            FROM {TABLE}
            WHERE ST_Intersects(
                geometry,
                ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
            )
        ) sub
    """)

    result = db.execute(sql, {
        "min_lon": min_lon, "min_lat": min_lat,
        "max_lon": max_lon, "max_lat": max_lat,
    }).scalar()
    return result


# ─────────────────────────────────────────────
#  GET /blok/geojson/point — Blok yang mengandung titik koordinat
# ─────────────────────────────────────────────
@router.get("/blok/geojson/point")
def get_blok_by_point(
    lon: float = Query(..., description="Longitude titik"),
    lat: float = Query(..., description="Latitude titik"),
    db : Session = Depends(get_db),
):
    sql = text(f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(feat), '[]'::jsonb)
        ) AS geojson
        FROM (
            SELECT jsonb_build_object(
                'type',       'Feature',
                'geometry',   ST_AsGeoJSON(geometry, 6)::jsonb,
                'properties', jsonb_build_object(
                    'objectid',  objectid,
                    'blok',      blok,
                    'estate',    estate,
                    'ltanam',    ltanam,
                    'status',    status,
                    'pokok',     pokok
                )
            ) AS feat
            FROM {TABLE}
            WHERE ST_Contains(
                geometry,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            )
        ) sub
    """)

    result = db.execute(sql, {"lon": lon, "lat": lat}).scalar()
    return result


# ─────────────────────────────────────────────
#  GET /blok/summary/estate — Statistik per estate
# ─────────────────────────────────────────────
@router.get("/blok/summary/estate", response_model=list[BlokSummary])
def summary_by_estate(
    area: Optional[str] = Query(None),
    db  : Session       = Depends(get_db),
):
    params  = {}
    filters = []
    if area:
        filters.append("area ILIKE :area")
        params["area"] = f"%{area}%"
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = text(f"""
        SELECT
            area,
            estate,
            COUNT(*)          AS total_blok,
            SUM(ltanah)       AS total_lahan,
            SUM(ltanam)       AS total_tanam,
            SUM(pokok)::int   AS total_pokok
        FROM {TABLE}
        {where}
        GROUP BY area, estate
        ORDER BY area, estate
    """)
    rows = db.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]
