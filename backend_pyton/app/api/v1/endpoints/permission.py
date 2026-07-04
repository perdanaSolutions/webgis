from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api import deps
from app.models.auth import Permission
from app.schemas.permission import PermissionCreate, PermissionResponse

router = APIRouter()

# 1. READ ALL PERMISSIONS
@router.get("/", response_model=List[PermissionResponse])
def get_all_permissions(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:read"))
):
    """Mengambil semua daftar master permission yang tersedia di sistem"""
    permissions = db.query(Permission).order_by(Permission.resource, Permission.aksi).all()
    return permissions


# 2. CREATE NEW PERMISSION
@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(
    payload: PermissionCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    """Membuat kode master permission baru"""
    # Cek apakah kode permission sudah ada (misal 'blok:read')
    existing_perm = db.query(Permission).filter(Permission.kode == payload.kode).first()
    if existing_perm:
        raise HTTPException(
            status_code=400, 
            detail=f"Permission dengan kode '{payload.kode}' sudah terdaftar."
        )

    new_permission = Permission(
        kode=payload.kode,
        resource=payload.resource,
        aksi=payload.aksi,
        deskripsi=payload.deskripsi
    )
    db.add(new_permission)
    db.commit()
    db.refresh(new_permission)
    return new_permission


# 3. UPDATE PERMISSION
@router.put("/{permission_id}", response_model=PermissionResponse)
def update_permission(
    permission_id: UUID,
    payload: PermissionCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    """Mengubah detail master permission"""
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission tidak ditemukan")

    permission.kode = payload.kode
    permission.resource = payload.resource
    permission.aksi = payload.aksi
    permission.deskripsi = payload.deskripsi

    db.commit()
    db.refresh(permission)
    return permission


# 4. DELETE PERMISSION
@router.delete("/{permission_id}", status_code=status.HTTP_200_OK)
def delete_permission(
    permission_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    """Menghapus master permission dari sistem"""
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission tidak ditemukan")

    db.delete(permission)
    db.commit()
    return {"message": f"Permission '{permission.kode}' berhasil dihapus secara permanen"}