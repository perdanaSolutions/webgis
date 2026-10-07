from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CanWriteAnnouncement, CurrentUser, DbSession, user_has_permission
from app.api.params import Limit, Page
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse, AnnouncementUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services import announcement_service as service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
def list_announcements(
    db: DbSession,
    current_user: CurrentUser,
    search: str | None = Query(None, description="Cari di judul atau isi"),
    status_filter: str | None = Query(None, alias="status", description="aktif, terjadwal, kedaluwarsa, nonaktif (khusus pengelola)"),
    page: Page = 1,
    limit: Limit = 10,
):
    """User biasa hanya melihat pengumuman yang sedang tayang; pengelola melihat semuanya."""
    can_manage = user_has_permission(db, current_user, "pengumuman:write")
    return service.list_announcements(db, can_manage=can_manage, search=search, status=status_filter,
                                      page=page, limit=limit)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
def get_announcement(announcement_id: UUID, db: DbSession, current_user: CurrentUser):
    can_manage = user_has_permission(db, current_user, "pengumuman:write")
    return service.to_response(service.get_announcement(db, announcement_id, can_manage=can_manage))


@router.post("/", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
def create_announcement(payload: AnnouncementCreate, db: DbSession, current_user: CanWriteAnnouncement):
    return service.to_response(service.create_announcement(db, payload, current_user))


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(announcement_id: UUID, payload: AnnouncementUpdate, db: DbSession, current_user: CanWriteAnnouncement):
    return service.to_response(service.update_announcement(db, announcement_id, payload, current_user))


@router.delete("/{announcement_id}", response_model=MessageResponse)
def delete_announcement(announcement_id: UUID, db: DbSession, current_user: CanWriteAnnouncement):
    title = service.delete_announcement(db, announcement_id, current_user)
    return {"message": f"Pengumuman '{title}' berhasil dihapus"}
