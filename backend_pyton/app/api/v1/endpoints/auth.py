from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.api import deps  # Asumsi kamu punya file dependencies untuk get_db
from app.models.auth import User, UserActivityLog

router = APIRouter()

@router.post("/login")
def login_access_token(
    db: Session = Depends(deps.get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, menerima username dan password.
    """
    # 1. Cari user berdasarkan username
    user = db.query(User).filter(User.username == form_data.username).first()
    
    # 2. Validasi keberadaan user dan kecocokan password
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        # Catat log aktivitas jika gagal login (Gunakan IP dummy atau pasif jika belum ada request extractor)
        log_gagal = UserActivityLog(
            user_id=user.id if user else None,
            aksi="LOGIN",
            resource="auth",
            status="FAILED",
            detail={"reason": "Username atau password salah", "attempted_username": form_data.username}
        )
        db.add(log_gagal)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username atau password salah",
        )
    
    # 3. Validasi apakah status user aktif
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun Anda tidak aktif. Silakan hubungi admin.",
        )

    # 4. Buat JWT Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    # 5. Catat log aktivitas sukses login
    log_sukses = UserActivityLog(
        user_id=user.id,
        aksi="LOGIN",
        resource="auth",
        status="SUCCESS",
        detail={"nama_lengkap": user.nama_lengkap, "role_id": str(user.role_id)}
    )
    db.add(log_sukses)
    db.commit()

    # PERBAIKAN: Ambil daftar kode permission dari relasi Many-to-Many
    # Hasilnya nanti berupa list string, contoh: ["blok:read", "blok:write", "produksi:read"]
    list_permissions = [perm.kode for perm in user.role.permissions]

    # 6. Kembalikan token BESERTA informasi user profile & hak akses
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "nama_lengkap": user.nama_lengkap,
            "email": user.email,
            "role": user.role.nama,          # Mengembalikan nama role (e.g. "superadmin")
            "permissions": list_permissions   # Mengembalikan array isi kode akses
        }
    }

@router.get("/me")
def get_user_me(
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Mengambil informasi profil user yang sedang aktif berdasarkan token JWT.
    Berguna untuk menjaga sesi login saat halaman web di-refresh.
    """
    # Ambil daftar kode permission yang dimiliki oleh role user ini
    list_permissions = [perm.kode for perm in current_user.role.permissions]
    
    # Kembalikan data profile yang sama persis dengan response login
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "nama_lengkap": current_user.nama_lengkap,
        "email": current_user.email,
        "role": current_user.role.nama,
        "permissions": list_permissions
    }