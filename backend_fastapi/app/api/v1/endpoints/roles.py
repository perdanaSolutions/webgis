from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import MessageResponse
from app.schemas.role import RoleCreate, RoleResponse, RoleUpdate
from app.services import role_service

router = APIRouter()


@router.get("/", response_model=list[RoleResponse], summary="Semua role beserta hak akses menu, data, dan transaksi")
def list_roles(db: DbSession, _: CurrentUser):
    return role_service.list_roles(db)


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(role_id: UUID, db: DbSession, _: CurrentUser):
    return role_service.role_responses(db, [role_service.get_role(db, role_id)])[0]


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, db: DbSession, _: CurrentUser):
    return role_service.create_role(db, payload)


@router.put("/{role_id}", response_model=RoleResponse,
            summary="Ubah role; akses_* yang tidak dikirim tidak diubah, list kosong = kosongkan")
def update_role(role_id: UUID, payload: RoleUpdate, db: DbSession, _: CurrentUser):
    return role_service.update_role(db, role_id, payload)


@router.delete("/{role_id}", response_model=MessageResponse)
def delete_role(role_id: UUID, db: DbSession, _: CurrentUser):
    name = role_service.delete_role(db, role_id)
    return {"message": f"Role '{name}' berhasil dihapus"}
