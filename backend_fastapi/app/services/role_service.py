from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import bad_request, conflict, not_found
from app.models.auth import Role, UserRole
from app.schemas.permission import PermissionResponse
from app.schemas.role import RoleCreate, RoleUpdate
from app.services import access_service
from app.services.user_activity import record_user_activity


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def get_role(db: Session, role_id: UUID) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise not_found(f"Role dengan ID {role_id} tidak ditemukan")
    return role


def role_responses(db: Session, roles: list[Role]) -> list[dict]:
    role_ids = [role.id for role in roles]
    scopes = access_service.expanded_scopes(db, role_ids)
    scopes_by_role: dict[str, list[dict]] = {}
    for row in scopes:
        scopes_by_role.setdefault(str(row["role_id"]), []).append(row)
    menus_by_role = access_service.role_menu_rows_by_role(db, role_ids)
    transactions_by_role = access_service.role_transaction_rows_by_role(db, role_ids)

    return [
        {
            "id": role.id,
            "nama": role.nama,
            "deskripsi": role.deskripsi,
            "created_at": role.created_at,
            "permissions": [
                PermissionResponse.model_validate(p) for p in role.permissions if "." not in p.resource
            ],
            "akses_menu": menus_by_role.get(str(role.id), []),
            "akses_data": access_service.scopes_as_log_rows(scopes_by_role.get(str(role.id), [])),
            "akses_wilayah": access_service.scopes_as_tree(scopes_by_role.get(str(role.id), [])),
            "akses_transaksi": transactions_by_role.get(str(role.id), []),
        }
        for role in roles
    ]


def list_roles(db: Session) -> list[dict]:
    roles = list(
        db.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.created_at)).all()
    )
    return role_responses(db, roles)


def _ensure_unique_name(db: Session, name: str, exclude_id: UUID | None = None) -> None:
    query = select(Role.id).where(func.lower(Role.nama) == name)
    if exclude_id:
        query = query.where(Role.id != exclude_id)
    if db.scalar(query):
        raise conflict(f"Role dengan nama '{name}' sudah ada.", field="nama")


def _replace_data_access(db: Session, role_id: UUID, items: list) -> None:
    access_service.apply_akses_data(db, role_id, items, replace=True)


def _sync_access(db: Session, role: Role, payload: RoleCreate | RoleUpdate, *, replace_missing: bool) -> None:
    if replace_missing or payload.akses_menu is not None:
        access_service.replace_menus(db, role.id, payload.akses_menu or [])
    if replace_missing or payload.akses_data is not None:
        _replace_data_access(db, role.id, payload.akses_data or [])
    if replace_missing or payload.akses_transaksi is not None:
        access_service.replace_transactions(db, role.id, payload.akses_transaksi or [])


def create_role(db: Session, payload: RoleCreate, current_user=None) -> dict:
    name = _normalize_name(payload.nama)
    _ensure_unique_name(db, name)
    role = Role(nama=name, deskripsi=payload.deskripsi)
    db.add(role)
    db.flush()

    _sync_access(db, role, payload, replace_missing=True)
    if current_user is not None:
        record_user_activity(
            db,
            current_user,
            "CREATE_ROLE",
            "roles",
            record_id=str(role.id),
            detail={
                "nama": role.nama,
                "deskripsi": role.deskripsi,
                "jumlah_menu": len(payload.akses_menu or []),
                "jumlah_wilayah": len(payload.akses_data or []),
                "jumlah_transaksi": len(payload.akses_transaksi or []),
            },
        )
    db.commit()
    db.refresh(role)
    return role_responses(db, [role])[0]


def update_role(db: Session, role_id: UUID, payload: RoleUpdate, current_user=None) -> dict:
    role = get_role(db, role_id)
    before = {"nama": role.nama, "deskripsi": role.deskripsi}

    name = _normalize_name(payload.nama)
    _ensure_unique_name(db, name, exclude_id=role.id)
    role.nama = name
    if "deskripsi" in payload.model_fields_set:
        role.deskripsi = payload.deskripsi

    _sync_access(db, role, payload, replace_missing=False)
    if current_user is not None:
        record_user_activity(
            db,
            current_user,
            "UPDATE_ROLE",
            "roles",
            record_id=str(role.id),
            detail={
                "nama_sebelum": before["nama"],
                "nama_sesudah": role.nama,
                "deskripsi_sebelum": before["deskripsi"],
                "deskripsi_sesudah": role.deskripsi,
                "akses_menu_diubah": payload.akses_menu is not None,
                "akses_data_diubah": payload.akses_data is not None,
                "akses_transaksi_diubah": payload.akses_transaksi is not None,
            },
        )
    db.commit()
    db.refresh(role)
    return role_responses(db, [role])[0]


def delete_role(db: Session, role_id: UUID) -> str:
    role = get_role(db, role_id)
    if role.nama == settings.SUPERADMIN_ROLE:
        raise bad_request(f"Role bawaan '{settings.SUPERADMIN_ROLE}' tidak boleh dihapus")
    user_count = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id))
    if user_count:
        raise conflict(f"Role masih dipakai oleh {user_count} user. Pindahkan user ke role lain terlebih dahulu.")
    name = role.nama
    db.delete(role)
    db.commit()
    return name
