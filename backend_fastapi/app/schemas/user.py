from pydantic import BaseModel, EmailStr, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List


def _unique_role_ids(role_ids: Optional[List[UUID]], role_id: Optional[UUID]) -> List[UUID]:
    """Gabungkan role_ids dan role_id lama, buang duplikat tanpa mengubah urutan."""
    ordered: List[UUID] = []
    for value in [*(role_ids or []), role_id]:
        if value is not None and value not in ordered:
            ordered.append(value)
    return ordered


# Schema dasar (Shared properties)
class UserBase(BaseModel):
    username: str
    email: EmailStr
    nama_lengkap: str
    is_active: Optional[bool] = True

# Schema untuk Input saat Membuat User Baru (Wajib isi password)
class UserCreate(UserBase):
    password: str
    role_ids: List[UUID] = []
    role_id: Optional[UUID] = None

    @model_validator(mode="after")
    def require_roles(self):
        self.role_ids = _unique_role_ids(self.role_ids, self.role_id)
        if not self.role_ids:
            raise ValueError("Minimal satu role wajib dipilih.")
        return self

# Schema untuk Input saat Mengubah User (Password bersifat opsional)
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    nama_lengkap: Optional[str] = None
    role_ids: Optional[List[UUID]] = None
    role_id: Optional[UUID] = None
    password: Optional[str] = None  # Diisi hanya jika ingin ganti password
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def normalize_roles(self):
        if self.role_ids is None and self.role_id is None:
            return self
        self.role_ids = _unique_role_ids(self.role_ids, self.role_id)
        if not self.role_ids:
            raise ValueError("Minimal satu role wajib dipilih.")
        return self

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
    roles: List[RoleInUser] = []
    role: Optional[RoleInUser] = None
    # True jika user punya baris di audit.user_activities (tidak boleh dihapus)
    has_activity: bool = False

    class Config:
        from_attributes = True

class UserLoginRequest(BaseModel):
    email: str  # FE bisa mengirimkan teks username atau email ke field ini
    password: str