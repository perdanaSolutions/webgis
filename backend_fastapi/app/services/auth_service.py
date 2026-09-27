from datetime import datetime, timezone

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.auth import User
from app.services import access_service
from app.services.activity_service import log_activity


def user_profile(db: Session, user: User) -> dict:
    """Profil + hak akses (union lintas semua role user)."""
    role_ids = [r.id for r in user.roles]
    return {
        "id": str(user.id),
        "username": user.username,
        "nama_lengkap": user.full_name,
        "email": user.email,
        "roles": [r.name for r in user.roles],
        "akses_menu": [row["menu_id"] for row in access_service.role_menu_rows_for_roles(db, role_ids)],
        "akses_data": access_service.scopes_as_codes(access_service.expanded_scopes(db, role_ids)),
        "akses_transaksi": [row["nama_table_transaksi"] for row in access_service.role_transaction_rows_for_roles(db, role_ids)],
    }


def login(db: Session, identifier: str, password: str, ip_address: str | None) -> dict:
    identifier = identifier.strip()
    user = db.scalar(select(User).where(or_(func.lower(User.username) == identifier.lower(),
                                            func.lower(User.email) == identifier.lower())))

    if user is None or not security.verify_password(password, user.hashed_password):
        log_activity(db, user_id=user.id if user else None, action="LOGIN", resource="auth", status="FAILED",
                     detail={"identifier": identifier, "reason": "invalid_credentials"}, ip_address=ip_address)
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Username, email atau password yang Anda masukkan salah",
                       type_="invalid_credentials", field="auth")
    if not user.is_active:
        log_activity(db, user_id=user.id, action="LOGIN", resource="auth", status="FAILED",
                     detail={"reason": "inactive_account"}, ip_address=ip_address)
        raise AppError(status.HTTP_403_FORBIDDEN, "Akun tidak aktif", type_="inactive_account", field="auth")

    token = security.create_access_token(subject=user.id)
    log_activity(db, user_id=user.id, action="LOGIN", resource="auth",
                 detail={"nama_lengkap": user.full_name, "role_ids": [str(r.id) for r in user.roles]}, ip_address=ip_address)
    return {"access_token": token, "token_type": "bearer", "user": user_profile(db, user)}


def token_status(token: str, user: User) -> dict:
    payload = security.decode_access_token(token)
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(payload["exp"], timezone.utc)
    issued_at = datetime.fromtimestamp(payload["iat"], timezone.utc) if payload.get("iat") else None

    remaining = int((expires_at - now).total_seconds())
    if remaining > 0:
        days, rest = divmod(remaining, 86400)
        remaining_label = f"{days} hari, {rest // 3600} jam, {(rest % 3600) // 60} menit"
    else:
        remaining_label = "Token sudah kedaluwarsa"

    return {
        "status": "success",
        "is_expired": remaining <= 0,
        "konfigurasi_sistem_menit": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "waktu_terbit_server": issued_at.isoformat() if issued_at else None,
        "waktu_expired_server": expires_at.isoformat(),
        "waktu_sekarang_server": now.isoformat(),
        "sisa_waktu_aktif": remaining_label,
        "user": {"username": user.username, "nama_lengkap": user.full_name},
    }
