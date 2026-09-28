from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import MessageResponse
from app.schemas.menu import MenuCreate, MenuResponse, MenuUpdate
from app.services import menu_service

router = APIRouter()


@router.get("/", response_model=list[MenuResponse])
def list_menus(db: DbSession, _: CurrentUser,
               flat: bool = Query(False, description="true = daftar datar, false = pohon sampai 3 level")):
    return menu_service.list_menus(db, flat)


@router.post("/", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
def create_menu(payload: MenuCreate, db: DbSession, _: CurrentUser):
    return menu_service.create_menu(db, payload)


@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(menu_id: UUID, payload: MenuUpdate, db: DbSession, _: CurrentUser):
    return menu_service.update_menu(db, menu_id, payload)


@router.delete("/{menu_id}", response_model=MessageResponse)
def delete_menu(menu_id: UUID, db: DbSession, _: CurrentUser):
    menu_service.delete_menu(db, menu_id)
    return {"message": "Menu berhasil dihapus dari sistem"}
