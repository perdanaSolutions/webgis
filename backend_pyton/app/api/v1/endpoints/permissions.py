from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, PermissionChecker
from app.models.auth import User
from app.schemas.common import MessageResponse
from app.schemas.permission import PermissionCreate, PermissionResponse
from app.services import permission_service

router = APIRouter()
CanRead = Annotated[User, Depends(PermissionChecker("user:read"))]
CanWrite = Annotated[User, Depends(PermissionChecker("user:write"))]


@router.get("/", response_model=list[PermissionResponse])
def list_permissions(db: DbSession, _: CanRead):
    return permission_service.list_permissions(db)


@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(payload: PermissionCreate, db: DbSession, _: CanWrite):
    return permission_service.create_permission(db, payload)


@router.put("/{permission_id}", response_model=PermissionResponse)
def update_permission(permission_id: UUID, payload: PermissionCreate, db: DbSession, _: CanWrite):
    return permission_service.update_permission(db, permission_id, payload)


@router.delete("/{permission_id}", response_model=MessageResponse)
def delete_permission(permission_id: UUID, db: DbSession, _: CanWrite):
    code = permission_service.delete_permission(db, permission_id)
    return {"message": f"Permission '{code}' berhasil dihapus secara permanen"}
