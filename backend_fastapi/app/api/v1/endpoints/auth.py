# from datetime import timedelta
from datetime import timedelta, datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt import decode as jwt_decode
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.auth_session import (
    AuthSessionUnavailable,
    create_session,
    new_jti,
    revoke_jti,
    revoke_user,
)
from app.core.config import settings
from app.models.auth import User
from app.core.exceptions import AppError
from app.schemas.common import MessageResponse
from app.schemas.user import ChangePasswordRequest, UserLoginRequest
from app.services import user_access
from app.services.user_activity import record_user_activity

router = APIRouter()
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKED_MESSAGE = "Akun Anda terkunci karena salah memasukkan password 5 kali berturut-turut. Silakan hubungi PA."
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/swagger-form")


def _auth_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"errors": [{"type": "auth_unavailable", "field": "auth",
                            "msg": "Layanan autentikasi sementara tidak tersedia", "input": None}]},
    )


# =====================================================================
# 1. ENDPOINT LOGIN UTAMA - KHUSUS FRONTEND (Menerima JSON murni)
# =====================================================================
@router.post("/login")
async def login_access_token_fe(
    payload: UserLoginRequest,  # Murni membaca JSON {"email": "...", "password": "..."}
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Endpoint login utama untuk Frontend Website (React/Vue/Next.js).
    Menerima JSON body dengan property 'email' dan 'password'.
    """
    return await process_user_login(db, input_identifier=payload.email, input_password=payload.password)


# =====================================================================
# 2. ENDPOINT LOGIN CADANGAN - KHUSUS SWAGGER UI (Menerima Form-Data)
# =====================================================================
@router.post("/login/swagger-form", include_in_schema=True)
async def login_access_token_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(), # Murni membaca Form-Data bawaan gembok
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Endpoint khusus menjembatani fitur gembok 'Authorize' Swagger UI agar tidak error.
    """
    return await process_user_login(db, input_identifier=form_data.username, input_password=form_data.password)


def _session_user(db: Session, user: User) -> dict:
    names: list[str] = []
    seen: set[str] = set()
    for role in user.roles or []:
        name = (role.nama or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    primary = user.role
    access = user_access.merged_access(db, user)
    return {
        "id": str(user.id),
        "username": user.username,
        "nama_lengkap": user.nama_lengkap,
        "email": user.email,
        "roles": names,
        "is_active": bool(user.is_active),
        "role": primary.nama if primary else None,
        "role_id": str(primary.id) if primary else None,
        "role_ids": user_access.role_ids(user),
        **access,
    }


# =====================================================================
# 3. FUNGSI LOGIKA LOGIN (Reusable Function)
# =====================================================================
async def process_user_login(db: Session, input_identifier: str, input_password: str) -> Any:
    # Ambil user dari database (Bisa pakai Username maupun Email)
    user = db.query(User).filter(
        or_(
            User.username == input_identifier,
            User.email == input_identifier
        )
    ).first()
    
    # Akun terkunci ditolak sebelum password diperiksa (password benar pun tidak diterima)
    if user and not user.is_service_account and user.locked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errors": [{"type": "account_locked", "field": "auth", "msg": LOCKED_MESSAGE, "input": None}]},
        )

    # Validasi kecocokan password
    if not user or user.is_service_account or not security.verify_password(input_password, user.hashed_password):
        if user and not user.is_service_account:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            just_locked = user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS
            if just_locked:
                user.locked_at = datetime.now(timezone.utc)
            record_user_activity(
                db, user, "LOGIN", "auth",
                detail={"reason": "account_locked" if just_locked else "invalid_credentials",
                        "failed_attempts": user.failed_login_attempts},
            )
            db.commit()
            if just_locked:
                try:
                    await revoke_user(str(user.id))
                except AuthSessionUnavailable:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"errors": [{"type": "account_locked", "field": "auth", "msg": LOCKED_MESSAGE, "input": None}]},
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "errors": [
                    {
                        "type": "invalid_credentials",
                        "field": "auth",
                        "msg": "Email atau Password yang Anda masukkan salah",
                        "input": None
                    }
                ]
            }
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errors": [{"type": "inactive_account", "field": "auth", "msg": "Akun tidak aktif", "input": None}]},
        )

    # Login berhasil: hitung salah password dimulai dari nol lagi
    user.failed_login_attempts = 0

    # JWT + registry sesi Redis (jti) agar logout konsisten di semua instance
    jti = new_jti()
    # Akun selain Admin = satu akun untuk satu pengguna: login baru mencabut sesi lama
    is_admin = any(r.nama == settings.SUPERADMIN_ROLE for r in (user.roles or []))
    if not is_admin:
        try:
            await revoke_user(str(user.id))
        except AuthSessionUnavailable:
            raise _auth_unavailable()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires, jti=jti,
    )
    try:
        await create_session(jti, str(user.id))
    except AuthSessionUnavailable:
        raise _auth_unavailable()

    primary_role = user.role
    record_user_activity(
        db,
        user,
        "LOGIN",
        "auth",
        detail={
            "nama_lengkap": user.nama_lengkap,
            "role_id": str(primary_role.id) if primary_role else None,
        },
    )
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _session_user(db, user),
    }

@router.get("/me")
def get_user_me(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Mengambil informasi profil user yang sedang aktif berdasarkan token JWT.
    Berguna untuk menjaga sesi login saat halaman web di-refresh.
    """
    return _session_user(db, current_user)


@router.put("/me/password", response_model=MessageResponse)
async def change_own_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Ganti password akun yang sedang login. Password lama wajib cocok. Semua sesi dicabut."""
    if not security.verify_password(payload.password_lama, current_user.hashed_password):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "Password lama tidak sesuai",
            type_="invalid_password",
            field="password_lama",
        )

    current_user.hashed_password = security.get_password_hash(payload.password_baru)
    record_user_activity(
        db,
        current_user,
        "CHANGE_PASSWORD",
        "auth",
        record_id=str(current_user.id),
        detail={"username": current_user.username},
    )
    db.commit()
    try:
        await revoke_user(str(current_user.id))
    except AuthSessionUnavailable:
        raise _auth_unavailable()
    return {"message": "Password berhasil diperbarui"}


@router.get("/check-token")
async def check_token_validity(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    token: str = Depends(oauth2_scheme)
) -> Any:
    """
    Endpoint untuk mengecek masa berlaku token yang sedang digunakan saat ini.
    Decode memakai SECRET_KEY (signature diverifikasi); get_current_user sudah cek sesi Redis.
    """
    try:
        payload = jwt_decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        exp_timestamp = payload.get("exp")
        iat_timestamp = payload.get("iat")

        if not exp_timestamp:
            return {"status": "error", "message": "Token tidak memiliki klaim kedaluwarsa (exp)"}

        waktu_sekarang = datetime.now(timezone.utc)
        waktu_expired = datetime.fromtimestamp(exp_timestamp, timezone.utc)
        waktu_terbit = datetime.fromtimestamp(iat_timestamp, timezone.utc) if iat_timestamp else None

        sisa_waktu = waktu_expired - waktu_sekarang
        sisa_detik = int(sisa_waktu.total_seconds())

        if sisa_detik > 0:
            hari = sisa_detik // 86400
            jam = (sisa_detik % 86400) // 3600
            menit = (sisa_detik % 3600) // 60
            string_sisa = f"{hari} hari, {jam} jam, {menit} menit"
            is_expired = False
        else:
            string_sisa = "Token sudah kedaluwarsa"
            is_expired = True

        return {
            "status": "success",
            "is_expired": is_expired,
            "konfigurasi_sistem_menit": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "waktu_terbit_server": waktu_terbit.isoformat() if waktu_terbit else None,
            "waktu_expired_server": waktu_expired.isoformat(),
            "waktu_sekarang_server": waktu_sekarang.isoformat(),
            "sisa_waktu_aktif": string_sisa,
            "user": {
                "username": current_user.username,
                "nama_lengkap": current_user.nama_lengkap
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membedah token: {str(e)}")


@router.post("/logout")
async def logout(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    token: str | None = Depends(deps.oauth2_scheme),
):
    """
    Logout: cabut jti di Redis (semua instance menolak token ini) + audit.
    Frontend tetap harus menghapus token dari cookie/localStorage setelah memanggil API ini.
    """
    jti = None
    if token:
        try:
            payload = jwt_decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            jti = payload.get("jti")
        except Exception:
            jti = None
    try:
        await revoke_jti(jti, user_id=str(current_user.id))
    except AuthSessionUnavailable:
        raise _auth_unavailable()

    record_user_activity(
        db,
        current_user,
        "LOGOUT",
        "auth",
        detail={"nama_lengkap": current_user.nama_lengkap},
    )
    db.commit()

    return {"message": "Berhasil logout dari sistem, aktivitas telah dicatat."}