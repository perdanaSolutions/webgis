from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.api import deps
from app.services import spatial_jalan as service

router = APIRouter(tags=["Spatial Jalan"])

@router.post("/analyze")
async def analyze_jalan_file(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    """Endpoint Tahap 1: Menganalisis isi berkas GeoJSON jalan sebelum disimpan."""
    contents = await file.read()
    analysis_result = service.analyze_geojson_jalan(db, contents, bulan, tahun)
    return {
        "status": "success",
        "message": "Analisis file GeoJSON jalan berhasil.",
        "data": analysis_result
    }

@router.post("/upload")
async def upload_jalan_execute(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:read"))
):
    """Endpoint Tahap 2: Mengeksekusi bulk upload data garis infrastruktur jalan & mencatat audit log."""
    contents = await file.read()
    stats = service.execute_bulk_jalan(
        db=db, 
        geojson_content=contents, 
        filename=file.filename, 
        bulan=bulan, 
        tahun=tahun,
        user_id=current_user.id
    )
    return {
        "status": "success",
        "message": f"Proses bulk upload spasial jalan periode {bulan}-{tahun} selesai.",
        "detail": stats
    }

@router.get("/list")
async def get_jalan_data(
    bulan: int,
    tahun: int,
    blok_id: Optional[str] = Query(None, description="Filter opsional per ID Blok tertentu"),
    db: Session = Depends(deps.get_db)
):
    """Endpoint Menampilkan Data: Mengambil data koordinat spasial geo_jalan per periode."""
    data = service.get_geo_jalan_by_period(db, bulan, tahun, blok_id)
    return {
        "status": "success",
        "total_records": len(data),
        "periode": f"{bulan}-{tahun}",
        "data": data
    }