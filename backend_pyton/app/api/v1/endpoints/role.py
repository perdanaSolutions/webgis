from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api import deps
from app.models.auth import Role, Permission
from app.schemas.role import RoleCreate, RoleResponse

router = APIRouter()

# 1. GET ALL ROLES (Hanya untuk yang punya hak kelola user/role)
@router.get("/", response_model=List[RoleResponse])
def get_all_roles(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:read")) # Proteksi hak akses
):
    """Mengambil semua daftar role beserta permission di dalamnya"""
    roles = db.query(Role).all()
    return roles


# 2. CREATE NEW ROLE
@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    """Membuat role baru dan menempelkan daftar permission terkait"""
    # Cek apakah nama role sudah terpakai
    existing_role = db.query(Role).filter(Role.nama == payload.nama.lower()).first()
    if existing_role:
        raise HTTPException(status_code=400, detail=f"Role dengan nama '{payload.nama}' sudah ada.")

    # Buat objek role baru
    new_role = Role(
        nama=payload.nama.lower(),
        deskripsi=payload.deskripsi
    )

    # Jika mengirimkan list permission_ids, hubungkan relasinya
    if payload.permission_ids:
        permissions = db.query(Permission).filter(Permission.id.in_(payload.permission_ids)).all()
        new_role.permissions = permissions

    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role


# 3. UPDATE ROLE & PERMISSIONS (Sinkronisasi Hak Akses)
@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    payload: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    """Mengubah data deskripsi role dan memperbarui relasi permission-nya"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan")

    # Superadmin bawaan tidak boleh diubah namanya demi keamanan sistem internal
    if role.nama == "superadmin":
        raise HTTPException(status_code=400, detail="Role bawaan 'superadmin' tidak boleh dimodifikasi")

    role.nama = payload.nama.lower()
    role.deskripsi = payload.deskripsi

    # Sinkronisasi ulang permission Many-to-Many
    if payload.permission_ids is not None:
        permissions = db.query(Permission).filter(Permission.id.in_(payload.permission_ids)).all()
        role.permissions = permissions  # SQLAlchemy otomatis mengurus tabel pivot role_permissions

    db.commit()
    db.refresh(role)
    return role