from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import math

from app.api import deps
from app.models.auth import UserActivityLog, User
from app.schemas.activity_log import ActivityLogResponse
from app.schemas.spatial import PaginatedResponse

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
def get_activity_logs(
    search: Optional[str] = Query(None, description="Cari berdasarkan aksi, resource, atau nama user"),
    status_filter: Optional[str] = Query(None, description="Filter SUCCESS atau FAILED"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    """
    Mengambil semua log aktivitas pengguna dengan Server-Side Pagination, 
    Pencarian (Search), dan Filter Status.
    """
    offset = (page - 1) * limit
    
    # Membangun query dasar menggunakan SQLAlchemy ORM agar relasi '.user' otomatis ter-load
    query = db.query(UserActivityLog).join(User, UserActivityLog.user_id == User.id, isouter=True)
    
    # Menerapkan Pencarian (Search) global jika diisi frontend
    if search:
        query = query.filter(
            UserActivityLog.aksi.ilike(f"%{search}%") |
            UserActivityLog.resource.ilike(f"%{search}%") |
            User.nama_lengkap.ilike(f"%{search}%") |
            User.username.ilike(f"%{search}%")
        )
        
    # Menerapkan Filter Status (SUCCESS/FAILED)
    if status_filter:
        query = query.filter(UserActivityLog.status == status_filter.upper())
        
    # Hitung total data setelah difilter
    total_data = query.count()
    
    # Ambil data terpaginasi (Log terbaru akan muncul paling atas)
    logs = query.order_by(UserActivityLog.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total_data": total_data,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_data / limit),
        "data": [ActivityLogResponse.model_validate(log) for log in logs]
    }