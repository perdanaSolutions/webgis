"""
Hak akses role. Path & bentuk response mengikuti API lama (log_akses_*), penyimpanan memakai tabel v3:
menu -> auth.role_menus, data -> auth.role_data_scopes, transaksi -> auth.permissions + role_permissions.
"""
from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.access import (
    AksesDataResponse,
    AksesMenuCreate,
    AksesMenuResponse,
    AksesMenuUpdate,
    AksesTransaksiCreate,
    AksesTransaksiResponse,
    AksesTransaksiUpdate,
    AreaTreeSchema,
)
from app.schemas.common import MessageResponse
from app.services import access_service
from app.services.role_service import get_role

router = APIRouter()


# ---------------------------------------------------------------- menu

@router.post("/menu", response_model=AksesMenuResponse, status_code=status.HTTP_201_CREATED,
             summary="Beri akses menu ke role (idempoten)")
def create_menu_access(payload: AksesMenuCreate, db: DbSession, _: CurrentUser):
    row = access_service.add_menu(db, payload.role_id, payload.menu_id)
    db.commit()
    return row


@router.put("/menu/{access_id}", response_model=AksesMenuResponse, summary="access_id = '<role_id>:<menu_id>'")
def update_menu_access(access_id: str, payload: AksesMenuUpdate, db: DbSession, _: CurrentUser):
    role_id, menu_id = access_service.split_access_id(access_id)
    access_service.delete_menu(db, role_id, menu_id)
    row = access_service.add_menu(db, payload.role_id or role_id, payload.menu_id or menu_id)
    db.commit()
    return row


@router.get("/menu/role/{role_id}", response_model=list[AksesMenuResponse])
def list_menu_access(role_id: UUID, db: DbSession, _: CurrentUser):
    return access_service.role_menu_rows(db, role_id)


@router.delete("/menu/{access_id}", response_model=MessageResponse)
def delete_menu_access(access_id: str, db: DbSession, _: CurrentUser):
    access_service.delete_menu(db, *access_service.split_access_id(access_id))
    db.commit()
    return {"message": f"Berhasil menghapus hak akses menu {access_id}"}


# ---------------------------------------------------------------- data wilayah

@router.get("/data/role/{role_id}", response_model=list[AreaTreeSchema],
            summary="Hak akses wilayah berjenjang Area -> PT -> Estate -> Afdeling")
def get_data_access_tree(role_id: UUID, db: DbSession, _: CurrentUser):
    return access_service.scopes_as_tree(access_service.expanded_scopes(db, [role_id]))


@router.get("/data/role/{role_id}/rows", response_model=list[AksesDataResponse],
            summary="Hak akses wilayah dalam bentuk baris (dengan id scope untuk DELETE /data/{id})")
def get_data_access_rows(role_id: UUID, db: DbSession, _: CurrentUser):
    return access_service.scopes_as_log_rows(access_service.expanded_scopes(db, [role_id]))


@router.post("/data/role/{role_id}", status_code=status.HTTP_201_CREATED,
             summary="Tambah hak akses wilayah; node terdalam yang dikirim menjadi scope (idempoten)")
def add_data_access(role_id: UUID, payload: list[AreaTreeSchema], db: DbSession, _: CurrentUser):
    get_role(db, role_id)
    result = access_service.add_scopes_from_tree(db, role_id, payload)
    db.commit()
    message = f"Berhasil menambahkan {result['inserted']} record hak akses wilayah"
    return {"message": message, "tidak_ditemukan": result["unresolved"]}


@router.put("/data/role/{role_id}", response_model=list[AreaTreeSchema], summary="Ganti total hak akses wilayah role")
def replace_data_access(role_id: UUID, payload: list[AreaTreeSchema], db: DbSession, _: CurrentUser):
    get_role(db, role_id)
    access_service.clear_scopes(db, role_id)
    access_service.add_scopes_from_tree(db, role_id, payload)
    db.commit()
    return access_service.scopes_as_tree(access_service.expanded_scopes(db, [role_id]))


@router.delete("/data/{scope_id}", response_model=MessageResponse)
def delete_data_access(scope_id: int, db: DbSession, _: CurrentUser):
    access_service.delete_scope(db, scope_id)
    db.commit()
    return {"message": f"Berhasil menghapus hak akses data ID {scope_id}"}


# ---------------------------------------------------------------- transaksi

@router.post("/transaksi", response_model=AksesTransaksiResponse, status_code=status.HTTP_201_CREATED,
             summary="Beri akses baca tabel transaksi ke role (idempoten)")
def create_transaction_access(payload: AksesTransaksiCreate, db: DbSession, _: CurrentUser):
    row = access_service.add_transaction(db, payload.role_id, payload.nama_table_transaksi)
    db.commit()
    return row


@router.put("/transaksi/{access_id}", response_model=AksesTransaksiResponse, summary="access_id = '<role_id>:<permission_id>'")
def update_transaction_access(access_id: str, payload: AksesTransaksiUpdate, db: DbSession, _: CurrentUser):
    role_id, permission_id = access_service.split_access_id(access_id)
    current = next((r for r in access_service.role_transaction_rows(db, role_id) if r["id"] == access_id), None)
    access_service.delete_transaction(db, role_id, permission_id)
    table_name = payload.nama_table_transaksi or (current["nama_table_transaksi"] if current else None)
    row = access_service.add_transaction(db, payload.role_id or role_id, table_name or "")
    db.commit()
    return row


@router.get("/transaksi/role/{role_id}", response_model=list[AksesTransaksiResponse])
def list_transaction_access(role_id: UUID, db: DbSession, _: CurrentUser):
    return access_service.role_transaction_rows(db, role_id)


@router.delete("/transaksi/{access_id}", response_model=MessageResponse)
def delete_transaction_access(access_id: str, db: DbSession, _: CurrentUser):
    access_service.delete_transaction(db, *access_service.split_access_id(access_id))
    db.commit()
    return {"message": f"Berhasil menghapus hak akses transaksi {access_id}"}
