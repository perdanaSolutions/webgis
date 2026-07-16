from pydantic import BaseModel, UUID4
from uuid import UUID
from datetime import datetime
from typing import List, Optional

from app.schemas.akses import LogAksesMenuResponse, LogAksesDataResponse, LogAksesTransaksiResponse

# Schema dasar untuk Permission (digunakan di dalam detail Role)
class PermissionInRole(BaseModel):
    id: UUID
    kode: str
    resource: str
    aksi: str

    class Config:
        from_attributes = True

class RoleResponse(BaseModel):
    id: UUID4
    nama: str
    deskripsi: Optional[str] = None
    created_at: datetime
    # permissions: List[PermissionInRole] = [] # Hak akses legacy/lama
    
    # Tambahkan field baru untuk konfigurasi UI baru (Gambar 1)
    akses_menu: List[LogAksesMenuResponse] = []
    akses_data: List[LogAksesDataResponse] = []
    akses_transaksi: List[LogAksesTransaksiResponse] = []

    class Config:
        from_attributes = True

# Schema untuk Input saat membuat/mengubah Role
class RoleCreate(BaseModel):
    nama: str
    deskripsi: Optional[str] = None
    permission_ids: Optional[List[UUID]] = [] # Mengirimkan list UUID permission yang ingin ditempelkan

# Schema untuk Output data Role
class RoleResponse(BaseModel):
    id: UUID
    nama: str
    deskripsi: Optional[str] = None
    created_at: datetime
    # permissions: List[PermissionInRole] = [] # Mengembalikan object detail permission-nya

    # Tambahkan field baru untuk konfigurasi UI baru (Gambar 1)
    akses_menu: List[LogAksesMenuResponse] = []
    akses_data: List[LogAksesDataResponse] = []
    akses_transaksi: List[LogAksesTransaksiResponse] = []

    class Config:
        from_attributes = True