from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.exceptions import bad_request, conflict, not_found
from app.models.audit import UserActivity
from app.models.auth import Role, User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.utils.pagination import page_response


def list_users(db: Session, search: str | None, page: int, limit: int) -> dict:
    query = select(User)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(User.full_name.ilike(pattern), User.username.ilike(pattern), User.email.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    users = db.scalars(query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)).all()
    return page_response(total, page, limit, [UserResponse.model_validate(u) for u in users])


def get_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User tidak ditemukan")
    return user


def _ensure_unique(db: Session, username: str | None, email: str | None, exclude_id: UUID | None = None) -> None:
    for column, value, label in ((User.username, username, "Username sudah terpakai."),
                                 (User.email, email, "Email sudah terdaftar.")):
        if value is None:
            continue
        query = select(User.id).where(func.lower(column) == value.lower())
        if exclude_id:
            query = query.where(User.id != exclude_id)
        if db.scalar(query):
            raise conflict(label, field=column.key)


def _ensure_roles(db: Session, role_ids: list[UUID]) -> list[Role]:
    roles = list(db.scalars(select(Role).where(Role.id.in_(role_ids))).all())
    found_ids = {role.id for role in roles}
    missing = [str(rid) for rid in role_ids if rid not in found_ids]
    if missing:
        raise not_found(f"Role ID berikut tidak ditemukan: {', '.join(missing)}")
    return roles


def create_user(db: Session, payload: UserCreate) -> User:
    username, email = payload.username.lower().strip(), payload.email.lower()
    _ensure_unique(db, username, email)
    roles = _ensure_roles(db, payload.role_ids)
    user = User(
        username=username, email=email, full_name=payload.nama_lengkap.strip(),
        hashed_password=security.get_password_hash(payload.password), is_active=payload.is_active,
    )
    user.roles = roles
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: UUID, payload: UserUpdate) -> User:
    user = get_user(db, user_id)
    is_main_admin = user.username == settings.SEED_ADMIN_USERNAME
    if is_main_admin and payload.is_active is False:
        raise bad_request(f"Akun '{user.username}' utama tidak boleh dinonaktifkan.", field="is_active")

    username = payload.username.lower().strip() if payload.username else None
    email = payload.email.lower() if payload.email else None
    _ensure_unique(db, username, email, exclude_id=user.id)

    if username:
        user.username = username
    if email:
        user.email = email
    if payload.nama_lengkap:
        user.full_name = payload.nama_lengkap.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role_ids is not None:
        user.roles = _ensure_roles(db, payload.role_ids)
    if payload.password:
        user.hashed_password = security.get_password_hash(payload.password)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: UUID, current_user: User) -> str:
    user = get_user(db, user_id)
    if user.username == settings.SEED_ADMIN_USERNAME:
        raise bad_request(f"Akun '{user.username}' utama sistem tidak boleh dihapus.")
    if user.id == current_user.id:
        raise bad_request("Tidak bisa menghapus akun yang sedang dipakai login.")
    # audit.user_activities append-only: FK ON DELETE SET NULL akan ditolak trigger deny_modification.
    if db.scalar(select(UserActivity.id).where(UserActivity.user_id == user.id).limit(1)):
        raise conflict("User sudah memiliki riwayat aktivitas (log audit tidak boleh diubah). "
                       "Nonaktifkan akun (is_active=false) alih-alih menghapus.")
    username = user.username
    db.delete(user)
    db.commit()
    return username
