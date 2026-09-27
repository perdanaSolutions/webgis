from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import bad_request, conflict, not_found
from app.models.auth import Role, UserRole
from app.schemas.permission import PermissionResponse
from app.schemas.role import RoleCreate, RoleUpdate
from app.services import access_service


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def get_role(db: Session, role_id: UUID) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise not_found(f"Role dengan ID {role_id} tidak ditemukan")
    return role


def role_responses(db: Session, roles: list[Role]) -> list[dict]:
    scopes = access_service.expanded_scopes(db, [r.id for r in roles])
    scopes_by_role: dict[str, list[dict]] = {}
    for row in scopes:
        scopes_by_role.setdefault(str(row["role_id"]), []).append(row)

    return [
        {
            "id": role.id,
            "nama": role.name,
            "deskripsi": role.description,
            "created_at": role.created_at,
            "permissions": [
                PermissionResponse.model_validate(p) for p in role.permissions if "." not in p.resource
            ],
            "akses_menu": access_service.role_menu_rows(db, role.id),
            "akses_data": access_service.scopes_as_log_rows(scopes_by_role.get(str(role.id), [])),
            "akses_transaksi": access_service.role_transaction_rows(db, role.id),
        }
        for role in roles
    ]


def list_roles(db: Session) -> list[dict]:
    return role_responses(db, list(db.scalars(select(Role).order_by(Role.created_at)).all()))


def _ensure_unique_name(db: Session, name: str, exclude_id: UUID | None = None) -> None:
    query = select(Role.id).where(func.lower(Role.name) == name)
    if exclude_id:
        query = query.where(Role.id != exclude_id)
    if db.scalar(query):
        raise conflict(f"Role dengan nama '{name}' sudah ada.", field="nama")


def create_role(db: Session, payload: RoleCreate) -> dict:
    name = _normalize_name(payload.nama)
    _ensure_unique_name(db, name)
    role = Role(name=name, description=payload.deskripsi)
    db.add(role)
    db.flush()

    access_service.replace_menus(db, role.id, payload.akses_menu)
    access_service.add_scopes_from_legacy_payload(db, role.id, payload.akses_data)
    access_service.replace_transactions(db, role.id, payload.akses_transaksi)
    db.commit()
    return role_responses(db, [role])[0]


def update_role(db: Session, role_id: UUID, payload: RoleUpdate) -> dict:
    role = get_role(db, role_id)
    if role.name == settings.SUPERADMIN_ROLE:
        raise bad_request(f"Role bawaan '{settings.SUPERADMIN_ROLE}' tidak boleh dimodifikasi")

    name = _normalize_name(payload.nama)
    _ensure_unique_name(db, name, exclude_id=role.id)
    role.name = name
    role.description = payload.deskripsi

    if payload.akses_menu is not None:
        access_service.replace_menus(db, role.id, payload.akses_menu)
    if payload.akses_data is not None:
        access_service.clear_scopes(db, role.id)
        access_service.add_scopes_from_legacy_payload(db, role.id, payload.akses_data)
    if payload.akses_transaksi is not None:
        access_service.replace_transactions(db, role.id, payload.akses_transaksi)

    db.commit()
    db.refresh(role)
    return role_responses(db, [role])[0]


def delete_role(db: Session, role_id: UUID) -> str:
    role = get_role(db, role_id)
    if role.name == settings.SUPERADMIN_ROLE:
        raise bad_request(f"Role bawaan '{settings.SUPERADMIN_ROLE}' tidak boleh dihapus")
    user_count = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id))
    if user_count:
        raise conflict(f"Role masih dipakai oleh {user_count} user. Pindahkan user ke role lain terlebih dahulu.")
    name = role.name
    db.delete(role)
    db.commit()
    return name
