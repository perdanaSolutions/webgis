from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import conflict, not_found
from app.models.auth import Permission
from app.schemas.permission import PermissionCreate


def list_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.resource, Permission.action)).all())


def _get(db: Session, permission_id: UUID) -> Permission:
    permission = db.get(Permission, permission_id)
    if permission is None:
        raise not_found("Permission tidak ditemukan")
    return permission


def _apply(db: Session, permission: Permission, payload: PermissionCreate) -> None:
    resource, action = payload.resource.strip(), payload.aksi.strip()
    code = f"{resource}:{action}"  # CHECK constraint: code = resource || ':' || action
    query = select(Permission.id).where(Permission.code == code)
    if permission.id is not None:
        query = query.where(Permission.id != permission.id)
    if db.scalar(query):
        raise conflict(f"Permission dengan kode '{code}' sudah terdaftar.", field="kode")
    permission.code, permission.resource, permission.action = code, resource, action
    permission.description = payload.deskripsi


def create_permission(db: Session, payload: PermissionCreate) -> Permission:
    permission = Permission()
    _apply(db, permission, payload)
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def update_permission(db: Session, permission_id: UUID, payload: PermissionCreate) -> Permission:
    permission = _get(db, permission_id)
    _apply(db, permission, payload)
    db.commit()
    db.refresh(permission)
    return permission


def delete_permission(db: Session, permission_id: UUID) -> str:
    permission = _get(db, permission_id)
    code = permission.code
    db.delete(permission)
    db.commit()
    return code
