from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.params import Limit, Page
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
def list_users(db: DbSession, _: CurrentUser, search: str | None = Query(None, description="Nama, username, atau email"),
               page: Page = 1, limit: Limit = 10):
    return user_service.list_users(db, search, page, limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: DbSession, _: CurrentUser):
    return user_service.get_user_response(db, user_id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, _: CurrentUser):
    return user_service.create_user(db, payload)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: UUID, payload: UserUpdate, db: DbSession, _: CurrentUser):
    return user_service.update_user(db, user_id, payload)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(user_id: UUID, db: DbSession, current_user: CurrentUser):
    username = user_service.delete_user(db, user_id, current_user)
    return {"message": f"User '{username}' berhasil dihapus secara permanen dari sistem"}
