from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional

# Schema dasar untuk Permission (digunakan di dalam detail Role)
class PermissionInRole(BaseModel):
    id: UUID
    kode: str
    resource: str
    aksi: str

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
    permissions: List[PermissionInRole] = [] # Mengembalikan object detail permission-nya

    class Config:
        from_attributes = True