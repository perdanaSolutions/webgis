from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.config import settings
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
    password: Optional[str] = None  # wajib untuk user biasa; akun layanan tidak memakai password
    role_ids: List[UUID] = []
    role_id: Optional[UUID] = None
    # Akun layanan = akun untuk sistem lain: tidak bisa login, hanya memakai Bearer token berumur panjang.
    is_service_account: bool = False
    masa_berlaku_token_hari: Optional[int] = Field(
        default=None, ge=1,
        description="Masa berlaku token akun layanan (hari). Kosong = SERVICE_TOKEN_DEFAULT_DAYS. "
                    "Maksimum SERVICE_TOKEN_MAX_DAYS.",
    )

    @model_validator(mode="after")
    def validate_account_type(self):
        self.role_ids = _unique_role_ids(self.role_ids, self.role_id)
        if self.is_service_account:
            days = self.masa_berlaku_token_hari or settings.SERVICE_TOKEN_DEFAULT_DAYS
            if days > settings.SERVICE_TOKEN_MAX_DAYS:
                raise ValueError(f"masa_berlaku_token_hari maksimal {settings.SERVICE_TOKEN_MAX_DAYS} hari.")
            self.masa_berlaku_token_hari = days
            return self
        if self.masa_berlaku_token_hari is not None:
            raise ValueError("masa_berlaku_token_hari hanya untuk akun layanan (is_service_account=true).")
        if not self.password:
            raise ValueError("Password wajib diisi.")
        if not self.role_ids:
            raise ValueError("Minimal satu role wajib dipilih.")
        return self


class ServiceTokenRequest(BaseModel):
    masa_berlaku_token_hari: Optional[int] = Field(
        default=None, ge=1, description="Kosong = SERVICE_TOKEN_DEFAULT_DAYS. Maksimum SERVICE_TOKEN_MAX_DAYS.")

    @model_validator(mode="after")
    def validate_days(self):
        days = self.masa_berlaku_token_hari or settings.SERVICE_TOKEN_DEFAULT_DAYS
        if days > settings.SERVICE_TOKEN_MAX_DAYS:
            raise ValueError(f"masa_berlaku_token_hari maksimal {settings.SERVICE_TOKEN_MAX_DAYS} hari.")
        self.masa_berlaku_token_hari = days
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
    # False = buka kunci akun yang terkunci karena salah password berulang kali.
    is_locked: Optional[bool] = None

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
    is_service_account: bool = False
    is_locked: bool = False
    token_expires_at: Optional[datetime] = None
    # Token layanan hanya ditampilkan SEKALI, saat akun dibuat atau token diterbitkan ulang.
    access_token: Optional[str] = None
    token_type: Optional[str] = None

    class Config:
        from_attributes = True

class UserLoginRequest(BaseModel):
    email: str  # FE bisa mengirimkan teks username atau email ke field ini
    password: str


class ChangePasswordRequest(BaseModel):
    password_lama: str = Field(min_length=1)
    password_baru: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_must_differ(self):
        if self.password_lama == self.password_baru:
            raise ValueError("Password baru harus berbeda dari password lama")
        return self