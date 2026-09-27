from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.schemas.access import AksesDataResponse, AksesMenuResponse, AksesTransaksiResponse
from app.schemas.akses import LogAksesDataCreate

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
    
    # Diisi dari auth.role_menus, auth.role_data_scopes, dan auth.role_permissions.
    akses_menu: List[AksesMenuResponse] = []
    akses_data: List[AksesDataResponse] = []
    akses_transaksi: List[AksesTransaksiResponse] = []

    class Config:
        from_attributes = True