from pydantic import BaseModel
from uuid import UUID
from typing import Optional

# Schema dasar (Shared properties)
class PermissionBase(BaseModel):
    kode: str
    resource: str
    aksi: str
    deskripsi: Optional[str] = None

# Schema untuk Input saat Membuat/Mengubah Permission
class PermissionCreate(PermissionBase):
    pass

# Schema untuk Output data Permission
class PermissionResponse(PermissionBase):
    id: UUID

    class Config:
        from_attributes = True