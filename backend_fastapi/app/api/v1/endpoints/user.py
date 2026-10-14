from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
import math
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.api import deps
from app.core import security
from app.models.auth import User, Role, UserActivityLog
from app.core.config import settings
from app.schemas.user import ServiceTokenRequest, UserCreate, UserUpdate, UserResponse
from app.schemas.spatial import PaginatedResponse  # Menggunakan wrapper pagination kita sebelumnya

router = APIRouter()


def _roles_by_ids(db: Session, role_ids: list[UUID]) -> list[Role]:
    """Ambil role sesuai id. Id yang sama hanya sekali, urutan payload dipertahankan."""
    unique_ids: list[UUID] = []
    for role_id in role_ids:
        if role_id not in unique_ids:
            unique_ids.append(role_id)
    found = db.query(Role).filter(Role.id.in_(unique_ids)).all() if unique_ids else []
    by_id = {role.id: role for role in found}
    missing = [str(role_id) for role_id in unique_ids if role_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Role ID berikut tidak ditemukan: {', '.join(missing)}")
    return [by_id[role_id] for role_id in unique_ids]


def _user_ids_with_activity(db: Session, user_ids: list[UUID]) -> set[UUID]:
    if not user_ids:
        return set()
    rows = (
        db.query(UserActivityLog.user_id)
        .filter(UserActivityLog.user_id.in_(user_ids))
        .distinct()
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _to_user_response(user: User, has_activity: bool = False) -> UserResponse:
    return UserResponse.model_validate(user).model_copy(update={"has_activity": has_activity})


def _user_has_activity(db: Session, user_id: UUID) -> bool:
    return (
        db.query(UserActivityLog.id)
        .filter(UserActivityLog.user_id == user_id)
        .limit(1)
        .first()
        is not None
    )

def _is_superadmin(user: User) -> bool:
    return any(role.nama == settings.SUPERADMIN_ROLE for role in user.roles)


def _forbid_unless_superadmin(current_user: User, message: str, *, target: User | None = None,
                              roles: list[Role] | None = None) -> None:
    """Hanya superadmin yang boleh menyentuh akun superadmin atau memberi role superadmin."""
    if _is_superadmin(current_user):
        return
    touches_superadmin = (target is not None and _is_superadmin(target)) or any(
        role.nama == settings.SUPERADMIN_ROLE for role in roles or [])
    if touches_superadmin:
        raise HTTPException(status_code=403, detail=message)


def _issue_service_token(user: User, days: int) -> tuple[str, datetime]:
    """Terbitkan token layanan baru; versi dinaikkan sehingga token sebelumnya langsung tidak berlaku."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    user.token_version = (user.token_version or 1) + 1
    user.token_expires_at = expires_at
    token = security.create_service_token(user.id, user.token_version, expires_at, [security.SCOPE_PRODUKSI_IMPORT])
    return token, expires_at


# 1. READ ALL USERS (Dengan Server-Side Pagination & Search)
@router.get("/", response_model=PaginatedResponse)
def get_users_list(
    search: Optional[str] = Query(None, description="Cari berdasarkan nama, username, atau email"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:read"))
):
    offset = (page - 1) * limit
    where_clauses = []
    params = {}

    if search:
        where_clauses.append("(full_name ILIKE :search OR username ILIKE :search OR email ILIKE :search)")
        params["search"] = f"%{search}%"

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Hitung total data
    total_query = db.execute(text(f"SELECT COUNT(*) FROM auth.users {where_str}"), params).scalar()
    
    # Ambil data dari database ORM SQLAlchemy agar relasi role otomatis ikut terbaca rapi oleh schema
    query = db.query(User)
    if search:
        query = query.filter(
            User.nama_lengkap.ilike(f"%{search}%") | 
            User.username.ilike(f"%{search}%") | 
            User.email.ilike(f"%{search}%")
        )
    
    users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    active_ids = _user_ids_with_activity(db, [u.id for u in users])

    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit) if total_query else 0,
        "data": [_to_user_response(u, u.id in active_ids) for u in users],
    }


# 2. CREATE NEW USER
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    # Cek duplikasi username
    if db.query(User).filter(User.username == payload.username.lower()).first():
        raise HTTPException(status_code=409, detail="Username sudah terpakai.")
        
    # Cek duplikasi email
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email sudah terdaftar.")

    if payload.is_service_account and not _is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Hanya superadmin yang boleh membuat akun layanan.")

    roles = _roles_by_ids(db, payload.role_ids)
    _forbid_unless_superadmin(current_user, "Hanya superadmin yang boleh memberi role superadmin.", roles=roles)

    new_user = User(
        username=payload.username.lower(),
        email=payload.email.lower(),
        nama_lengkap=payload.nama_lengkap,
        # Akun layanan tidak punya password yang bisa dipakai: login ditolak untuknya.
        hashed_password=security.get_password_hash(payload.password or secrets.token_urlsafe(32)),
        is_active=payload.is_active,
        is_service_account=payload.is_service_account,
        roles=roles,
    )
    token = None
    if payload.is_service_account:
        db.add(new_user)
        db.flush()  # id dibutuhkan untuk token
        token, _ = _issue_service_token(new_user, payload.masa_berlaku_token_hari)
    else:
        db.add(new_user)
    db.commit()
    db.refresh(new_user)
    response = _to_user_response(new_user, False)
    return response.model_copy(update={"access_token": token, "token_type": "bearer" if token else None})


# 2b. TERBITKAN ULANG TOKEN AKUN LAYANAN
@router.post("/{user_id}/service-token", response_model=UserResponse)
def reissue_service_token(
    user_id: UUID,
    payload: ServiceTokenRequest,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    """Token lama langsung tidak berlaku. Token baru hanya ditampilkan sekali di respons ini."""
    if not _is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Hanya superadmin yang boleh menerbitkan token akun layanan.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if not user.is_service_account:
        raise HTTPException(status_code=400, detail="User ini bukan akun layanan.")
    token, _ = _issue_service_token(user, payload.masa_berlaku_token_hari)
    db.commit()
    db.refresh(user)
    response = _to_user_response(user, _user_has_activity(db, user.id))
    return response.model_copy(update={"access_token": token, "token_type": "bearer"})


# 3. UPDATE USER DETAILS & PASSWORD
@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    _forbid_unless_superadmin(current_user, "Hanya superadmin yang boleh mengubah akun superadmin.", target=user)

    # Mencegah penonaktifan akun superadmin bawaan secara tidak sengaja
    if user.username == "superadmin" and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Akun 'superadmin' utama tidak boleh dinonaktifkan.")

    if payload.username:
        user.username = payload.username.lower()
    if payload.email:
        user.email = payload.email.lower()
    if payload.nama_lengkap:
        user.nama_lengkap = payload.nama_lengkap
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role_ids is not None:
        new_roles = _roles_by_ids(db, payload.role_ids)
        _forbid_unless_superadmin(current_user, "Hanya superadmin yang boleh memberi role superadmin.", roles=new_roles)
        user.roles = new_roles
        
    # Jika frontend mengirimkan string password baru, lakukan hashing ulang
    if payload.password:
        user.hashed_password = security.get_password_hash(payload.password)

    db.commit()
    db.refresh(user)
    return _to_user_response(user, _user_has_activity(db, user.id))


# 4. DELETE USER PERMANENTLY
@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    _forbid_unless_superadmin(current_user, "Hanya superadmin yang boleh menghapus akun superadmin.", target=user)

    if user.username == "superadmin":
        raise HTTPException(status_code=400, detail="Akun 'superadmin' utama sistem tidak boleh dihapus.")

    if current_user.id == user.id:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus akun yang sedang dipakai login.")

    # audit.user_activities append-only. FK ON DELETE SET NULL pun ditolak
    # trigger deny_modification(), jadi user yang sudah punya log tidak boleh dihapus.
    has_activity = _user_has_activity(db, user.id)
    if has_activity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "User sudah memiliki riwayat aktivitas. Log audit bersifat append-only "
                "dan tidak boleh diubah atau dihapus. Nonaktifkan akun (is_active=false) "
                "alih-alih menghapus."
            ),
        )

    db.delete(user)
    db.commit()
    return {"message": f"User '{user.username}' berhasil dihapus secara permanen dari sistem"}