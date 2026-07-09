from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from typing import List, Optional

from app.api import deps
from app.schemas.menu import MenuCreate, MenuUpdate, MenuResponse

router = APIRouter()

# 1. CREATE MENU
@router.post("/", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
def create_menu(
    payload: MenuCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write")) # Batasi hanya role pengelola
):
    query = """
        INSERT INTO menus (title, description, bg_class, icon_class, arrow_class, "to", icon, order_position)
        VALUES (:title, :description, :bg_class, :icon_class, :arrow_class, :to, :icon, :order_position)
        RETURNING id, title, description, bg_class, icon_class, arrow_class, "to", icon, order_position;
    """
    result = db.execute(text(query), payload.model_dump()).mappings().first()
    db.commit()
    return MenuResponse.model_validate(result)


# 2. READ ALL MENUS (Untuk kebutuhan Sidebar / Dashboard FE)
@router.get("/", response_model=List[MenuResponse])
def get_all_menus(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user) # Semua user yang login boleh melihat menu
):
    query = "SELECT * FROM menus ORDER BY order_position ASC, title ASC"
    rows = db.execute(text(query)).mappings().all()
    return [MenuResponse.model_validate(row) for row in rows]


# 3. UPDATE MENU
@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(
    menu_id: UUID,
    payload: MenuUpdate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    # Cek menu ada atau tidak
    check = db.execute(text("SELECT id FROM menus WHERE id = :id"), {"id": menu_id}).first()
    if not check:
        raise HTTPException(status_code=404, detail="Menu tidak ditemukan")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Tidak ada data yang diubah")

    # Susun klausa SET SQL secara dinamis
    set_clauses = [f'{key} = :{key}' if key != "to" else '"to" = :to' for key in update_data.keys()]
    update_data["id"] = menu_id

    query = f"""
        UPDATE menus 
        SET {', '.join(set_clauses)} 
        WHERE id = :id 
        RETURNING id, title, description, bg_class, icon_class, arrow_class, "to", icon, order_position;
    """
    result = db.execute(text(query), update_data).mappings().first()
    db.commit()
    return MenuResponse.model_validate(result)


# 4. DELETE MENU
@router.delete("/{menu_id}", status_code=status.HTTP_200_OK)
def delete_menu(
    menu_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.PermissionChecker("user:write"))
):
    check = db.execute(text("SELECT id FROM menus WHERE id = :id"), {"id": menu_id}).first()
    if not check:
        raise HTTPException(status_code=404, detail="Menu tidak ditemukan")

    db.execute(text("DELETE FROM menus WHERE id = :id"), {"id": menu_id})
    db.commit()
    return {"message": "Menu berhasil dihapus dari sistem"}