from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.api import deps
# from app.dependencies import deps.get_db
from app.services import spatial_sawit as service

router = APIRouter(prefix="/spatial/sawit", tags=["Spatial Sawit"])

@router.post("/analyze")
async def analyze_sawit_file(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    """Endpoint Tahap 1: Menganalisis isi berkas GeoJSON sawit sebelum disimpan."""
    contents = await file.read()
    analysis_result = service.analyze_geojson_sawit(db, contents, bulan, tahun)
    return {
        "status": "success",
        "message": "Analisis file GeoJSON sawit berhasil.",
        "data": analysis_result
    }

@router.post("/upload")
async def upload_sawit_execute(
    bulan: int,
    tahun: int,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    # Sesuaikan dengan fungsi get_current_user/auth yang Anda miliki di project
    current_user = Depends(deps.get_current_user)
):
    """Endpoint Tahap 2: Mengeksekusi bulk upload data titik sawit & mencatat audit log."""
    contents = await file.read()
    
    # Kirim user_id (current_user.id) ke dalam fungsi service
    stats = service.execute_bulk_sawit(
        db=db, 
        geojson_content=contents, 
        filename=file.filename, 
        bulan=bulan, 
        tahun=tahun,
        user_id=current_user.id  # <-- TAMBAHKAN INI
    )
    
    return {
        "status": "success",
        "message": f"Proses bulk upload spasial sawit periode {bulan}-{tahun} selesai.",
        "detail": stats
    }

@router.get("/list")
async def get_sawit_data(
    bulan: int,
    tahun: int,
    blok_id: Optional[str] = Query(None, description="Filter opsional per ID Blok tertentu"),
    db: Session = Depends(deps.get_db)
):
    """Endpoint Menampilkan Data: Mengambil data spasial geo_sawit per periode."""
    data = service.get_geo_sawit_by_period(db, bulan, tahun, blok_id)
    return {
        "status": "success",
        "total_records": len(data),
        "periode": f"{bulan}-{tahun}",
        "data": data
    }