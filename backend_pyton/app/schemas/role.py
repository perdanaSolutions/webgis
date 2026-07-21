from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# Import skema response & create dari akses.py
from app.schemas.akses import (
    LogAksesDataCreate, 
    LogAksesMenuResponse, 
    LogAksesDataResponse, 
    LogAksesTransaksiResponse
)

class RoleBase(BaseModel):
    nama: str
    deskripsi: Optional[str] = None

class RoleCreate(RoleBase):
    # Payload yang dikirim oleh Frontend saat buat/edit Role
    akses_menu: Optional[List[str]] = []                 # Berisi list menu_id (e.g. ["menu-1", "menu-2"])
    akses_data: Optional[List[LogAksesDataCreate]] = []  # Berisi list object wilayah GIS
    akses_transaksi: Optional[List[str]] = []            # Berisi list nama tabel (e.g. ["trx_panen"])

class RoleResponse(RoleBase):
    id: UUID
    created_at: datetime
    
    # Menampilkan detail log akses yang aktif pada Role
    akses_menu: List[LogAksesMenuResponse] = []
    akses_data: List[LogAksesDataResponse] = []
    akses_transaksi: List[LogAksesTransaksiResponse] = []

    class Config:
        from_attributes = True