from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
import math
from typing import Optional

from app.api import deps
from app.core import security
from app.models.auth import User, Role
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.spatial import PaginatedResponse  # Menggunakan wrapper pagination kita sebelumnya

router = APIRouter()

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
        where_clauses.append("(nama_lengkap ILIKE :search OR username ILIKE :search OR email ILIKE :search)")
        params["search"] = f"%{search}%"

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Hitung total data
    total_query = db.execute(text(f"SELECT COUNT(*) FROM users {where_str}"), params).scalar()
    
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
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    # Cek duplikasi username
    if db.query(User).filter(User.username == payload.username.lower()).first():
        raise HTTPException(status_code=400, detail="Username sudah terpakai.")
        
    # Cek duplikasi email
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email sudah terdaftar.")

    # Cek validitas role_id
    if not db.query(Role).filter(Role.id == payload.role_id).first():
        raise HTTPException(status_code=404, detail="Role ID yang dipilih tidak ditemukan.")

    new_user = User(
        username=payload.username.lower(),
        email=payload.email.lower(),
        nama_lengkap=payload.nama_lengkap,
        role_id=payload.role_id,
        hashed_password=security.get_password_hash(payload.password), # Hashing password wajib!
        is_active=payload.is_active
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
    current_user = Depends(deps.PermissionChecker("user:write"))
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
    if payload.role_id:
        if not db.query(Role).filter(Role.id == payload.role_id).first():
            raise HTTPException(status_code=404, detail="Role ID tidak ditemukan.")
        user.role_id = payload.role_id
        
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
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    if user.username == "superadmin":
        raise HTTPException(status_code=400, detail="Akun 'superadmin' utama sistem tidak boleh dihapus.")

    db.delete(user)
    db.commit()
    return {"message": f"User '{user.username}' berhasil dihapus secara permanen dari sistem"}