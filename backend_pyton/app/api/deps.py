from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import decode, PyJWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.auth import User, Permission

# Mengatur endpoint mana yang dijadikan acuan Swagger untuk mengambil token JWT
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/swagger-form" # <--- ARINGKAN KE SINI
)

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """Dependency untuk mengambil data user yang sedang login berdasarkan JWT Token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau telah kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Dekode token JWT menggunakan SECRET_KEY kita
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception
        
    # Cari user di database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Akun tidak aktif")
        
    return user


class PermissionChecker:
    """Class Dependency untuk mengecek apakah user memiliki permission tertentu"""
    def __init__(self, required_permission: str):
        # Contoh required_permission: "blok:read" atau "produksi:write"
        self.required_permission = required_permission

    def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        # 1. JALUR KHUSUS: Jika role-nya 'superadmin', langsung lolos tanpa cek permission
        if current_user.role.nama == "superadmin":
            return current_user

        # 2. JALUR BIASA: Cek apakah kode permission ada di dalam daftar permission milik role user ini
        # Kita cek apakah ada relasi di role_permissions yang menyambungkan role user dengan permission terkait
        has_permission = db.query(User).filter(
            User.id == current_user.id
        ).join(User.role).join(User.role.permissions).filter(
            Permission.kode == self.required_permission
        ).first()

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Anda tidak memiliki hak akses ({self.required_permission}) untuk fitur ini"
            )
            
        return current_user