from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.models.auth import User, UserActivityLog
from app.schemas.user import UserLoginRequest

router = APIRouter()

# =====================================================================
# 1. ENDPOINT LOGIN UTAMA - KHUSUS FRONTEND (Menerima JSON murni)
# =====================================================================
@router.post("/login")
def login_access_token_fe(
    payload: UserLoginRequest,  # Murni membaca JSON {"email": "...", "password": "..."}
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Endpoint login utama untuk Frontend Website (React/Vue/Next.js).
    Menerima JSON body dengan property 'email' dan 'password'.
    """
    return process_user_login(db, input_identifier=payload.email, input_password=payload.password)


# =====================================================================
# 2. ENDPOINT LOGIN CADANGAN - KHUSUS SWAGGER UI (Menerima Form-Data)
# =====================================================================
@router.post("/login/swagger-form", include_in_schema=True)
def login_access_token_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(), # Murni membaca Form-Data bawaan gembok
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Endpoint khusus menjembatani fitur gembok 'Authorize' Swagger UI agar tidak error.
    """
    return process_user_login(db, input_identifier=form_data.username, input_password=form_data.password)


# =====================================================================
# 3. FUNGSI LOGIKA LOGIN (Reusable Function)
# =====================================================================
def process_user_login(db: Session, input_identifier: str, input_password: str) -> Any:
    # Ambil user dari database (Bisa pakai Username maupun Email)
    user = db.query(User).filter(
        or_(
            User.username == input_identifier,
            User.email == input_identifier
        )
    ).first()
    
    # Validasi kecocokan password
    if not user or not security.verify_password(input_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "errors": [
                    {
                        "type": "invalid_credentials",
                        "field": "auth",
                        "msg": "Username, email atau password yang Anda masukkan salah",
                        "input": None
                    }
                ]
            }
        )
        
    # Buat JWT Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    # Catat log aktivitas sukses login
    log_sukses = UserActivityLog(
        user_id=user.id,
        aksi="LOGIN",
        resource="auth",
        status="SUCCESS",
        detail={"nama_lengkap": user.nama_lengkap, "role_id": str(user.role_id)}
    )
    db.add(log_sukses)
    db.commit()

    list_permissions = [perm.kode for perm in user.role.permissions]

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "nama_lengkap": user.nama_lengkap,
            "email": user.email,
            "role": user.role.nama,
            "permissions": list_permissions
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