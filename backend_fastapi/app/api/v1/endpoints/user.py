from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
import math
from typing import Optional

from app.api import deps
from app.core import security
from app.models.auth import User, Role, UserActivityLog
from app.schemas.user import UserCreate, UserUpdate, UserResponse
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

# 1. READ ALL USERS (Dengan Server-Side Pagination & Search)
@router.get("/", response_model=PaginatedResponse)
def get_users_list(
    search: Optional[str] = Query(None, description="Cari berdasarkan nama, username, atau email"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
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

    # UBAH BAGIAN RETURN MENJADI SEPERTI INI:
    return {
        "total_data": total_query,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total_query / limit),
        # Kita paksa konversi tiap item SQLAlchemy User menjadi Pydantic model response
        "data": [UserResponse.model_validate(u) for u in users]
    }


# 2. CREATE NEW USER
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    # Cek duplikasi username
    if db.query(User).filter(User.username == payload.username.lower()).first():
        raise HTTPException(status_code=400, detail="Username sudah terpakai.")
        
    # Cek duplikasi email
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email sudah terdaftar.")

    roles = _roles_by_ids(db, payload.role_ids)

    new_user = User(
        username=payload.username.lower(),
        email=payload.email.lower(),
        nama_lengkap=payload.nama_lengkap,
        hashed_password=security.get_password_hash(payload.password),
        is_active=payload.is_active,
        roles=roles,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# 3. UPDATE USER DETAILS & PASSWORD
@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

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
        user.roles = _roles_by_ids(db, payload.role_ids)
        
    # Jika frontend mengirimkan string password baru, lakukan hashing ulang
    if payload.password:
        user.hashed_password = security.get_password_hash(payload.password)

    db.commit()
    db.refresh(user)
    return user


# 4. DELETE USER PERMANENTLY
@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    if user.username == "superadmin":
        raise HTTPException(status_code=400, detail="Akun 'superadmin' utama sistem tidak boleh dihapus.")

    if current_user.id == user.id:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus akun yang sedang dipakai login.")

    # audit.user_activities append-only. FK ON DELETE SET NULL pun ditolak
    # trigger deny_modification(), jadi user yang sudah punya log tidak boleh dihapus.
    has_activity = (
        db.query(UserActivityLog.id)
        .filter(UserActivityLog.user_id == user.id)
        .limit(1)
        .first()
    )
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