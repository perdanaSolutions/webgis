from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List

# Schema dasar (Shared properties)
class UserBase(BaseModel):
    username: str
    email: EmailStr
    nama_lengkap: str
    role_id: UUID
    is_active: Optional[bool] = True

# Schema untuk Input saat Membuat User Baru (Wajib isi password)
class UserCreate(UserBase):
    password: str

# Schema untuk Input saat Mengubah User (Password bersifat opsional)
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    nama_lengkap: Optional[str] = None
    role_id: Optional[UUID] = None
    password: Optional[str] = None  # Diisi hanya jika ingin ganti password
    is_active: Optional[bool] = None

# Schema Ringkas untuk data Role di dalam response User
class RoleInUser(BaseModel):
    id: UUID
    nama: str
    class Config:
        from_attributes = True

# Schema untuk Output data User (Password tidak boleh dikembalikan!)
class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    nama_lengkap: str
    is_active: bool
    created_at: datetime
    role: RoleInUser  # Mengembalikan detail informasi nama role-nya

    class Config:
        from_attributes = True