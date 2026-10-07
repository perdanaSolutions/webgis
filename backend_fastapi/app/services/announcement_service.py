from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.models.announcement import Announcement
from app.models.auth import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse, AnnouncementUpdate
from app.services.user_activity import record_user_activity
from app.utils.pagination import page_response

RESOURCE = "pengumuman"


def _status(item: Announcement, now: datetime) -> str:
    if not item.is_active:
        return "nonaktif"
    if item.start_at and item.start_at > now:
        return "terjadwal"
    if item.end_at and item.end_at < now:
        return "kedaluwarsa"
    return "aktif"


def to_response(item: Announcement) -> AnnouncementResponse:
    return AnnouncementResponse(
        id=item.id,
        judul=item.title,
        isi=item.content,
        is_active=item.is_active,
        status=_status(item, datetime.now(timezone.utc)),
        tanggal_mulai=item.start_at,
        tanggal_berakhir=item.end_at,
        dibuat_oleh=item.author.nama_lengkap if item.author else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _published_clause(now: datetime):
    return and_(
        Announcement.is_active.is_(True),
        or_(Announcement.start_at.is_(None), Announcement.start_at <= now),
        or_(Announcement.end_at.is_(None), Announcement.end_at >= now),
    )


def _status_clause(status: str, now: datetime):
    if status == "aktif":
        return _published_clause(now)
    if status == "nonaktif":
        return Announcement.is_active.is_(False)
    if status == "terjadwal":
        return and_(Announcement.is_active.is_(True), Announcement.start_at > now)
    if status == "kedaluwarsa":
        return and_(Announcement.is_active.is_(True), Announcement.end_at < now)
    raise bad_request("status harus salah satu dari: aktif, terjadwal, kedaluwarsa, nonaktif", field="status")


def list_announcements(db: Session, *, can_manage: bool, search: str | None, status: str | None,
                       page: int, limit: int) -> dict:
    """Pengelola melihat semua pengumuman; user biasa hanya yang sedang tayang."""
    now = datetime.now(timezone.utc)
    query = select(Announcement)
    if not can_manage:
        query = query.where(_published_clause(now))
    elif status:
        query = query.where(_status_clause(status, now))
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Announcement.title.ilike(pattern), Announcement.content.ilike(pattern)))

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Announcement.created_at.desc()).offset((page - 1) * limit).limit(limit)
    ).unique().all()
    return page_response(total, page, limit, [to_response(row) for row in rows])


def get_announcement(db: Session, announcement_id: UUID, *, can_manage: bool = True) -> Announcement:
    item = db.get(Announcement, announcement_id)
    if item is None or (not can_manage and _status(item, datetime.now(timezone.utc)) != "aktif"):
        raise not_found("Pengumuman tidak ditemukan")
    return item


def create_announcement(db: Session, payload: AnnouncementCreate, current_user: User) -> Announcement:
    item = Announcement(
        title=payload.judul,
        content=payload.isi,
        is_active=payload.is_active,
        start_at=payload.tanggal_mulai,
        end_at=payload.tanggal_berakhir,
        created_by=current_user.id,
    )
    db.add(item)
    db.flush()
    record_user_activity(db, current_user, "CREATE_PENGUMUMAN", RESOURCE, record_id=str(item.id),
                         detail={"judul": item.title, "is_active": item.is_active})
    db.commit()
    db.refresh(item)
    return item


def update_announcement(db: Session, announcement_id: UUID, payload: AnnouncementUpdate, current_user: User) -> Announcement:
    item = get_announcement(db, announcement_id)
    sent = payload.model_fields_set
    if not sent:
        raise bad_request("Tidak ada data yang diubah")
    for key in ("judul", "isi", "is_active"):
        if key in sent and getattr(payload, key) is None:
            raise bad_request(f"{key} tidak boleh null", field=key)

    if "judul" in sent:
        item.title = payload.judul
    if "isi" in sent:
        item.content = payload.isi
    if "is_active" in sent:
        item.is_active = payload.is_active
    if "tanggal_mulai" in sent:
        item.start_at = payload.tanggal_mulai
    if "tanggal_berakhir" in sent:
        item.end_at = payload.tanggal_berakhir
    if item.start_at and item.end_at and item.end_at < item.start_at:
        raise bad_request("tanggal_berakhir tidak boleh lebih awal dari tanggal_mulai", field="tanggal_berakhir")

    item.updated_at = func.now()
    record_user_activity(db, current_user, "UPDATE_PENGUMUMAN", RESOURCE, record_id=str(item.id),
                         detail={"judul": item.title, "field_diubah": sorted(sent)})
    db.commit()
    db.refresh(item)
    return item


def delete_announcement(db: Session, announcement_id: UUID, current_user: User) -> str:
    item = get_announcement(db, announcement_id)
    title = item.title
    db.delete(item)
    record_user_activity(db, current_user, "DELETE_PENGUMUMAN", RESOURCE, record_id=str(announcement_id),
                         detail={"judul": title})
    db.commit()
    return title
