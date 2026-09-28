from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from typing import List, Optional

from app.api import deps
from app.schemas.menu import MenuCreate, MenuUpdate, MenuResponse

router = APIRouter()

# gis_db_v3 menyimpan menu di auth.menus. Kolom route = field API "to".
MENU_COLUMNS = """
    id, title, description, bg_class, icon_class, arrow_class, route AS "to", icon,
    order_position, parent_id, level, is_favorite
"""

_menus_schema_ready = False


def _ensure_menus_schema(db: Session) -> None:
    """Tambah is_favorite bila belum ada. Aman dipanggil berulang."""
    global _menus_schema_ready
    if _menus_schema_ready:
        return
    db.execute(
        text(
            """
            ALTER TABLE auth.menus
            ADD COLUMN IF NOT EXISTS is_favorite boolean NOT NULL DEFAULT false
            """
        )
    )
    db.commit()
    _menus_schema_ready = True


ALLOWED_UPDATE_FIELDS = {
    "title",
    "description",
    "bg_class",
    "icon_class",
    "arrow_class",
    "to",
    "icon",
    "order_position",
    "parent_id",
    "is_favorite",
}


def _fetch_menu(db: Session, menu_id: UUID):
    _ensure_menus_schema(db)
    return db.execute(
        text(f"SELECT {MENU_COLUMNS} FROM auth.menus WHERE id = :id"),
        {"id": menu_id},
    ).mappings().first()


def _subtree_depth(db: Session, menu_id: UUID) -> int:
    _ensure_menus_schema(db)
    row = db.execute(
        text(
            """
            WITH RECURSIVE tree AS (
                SELECT id, 0 AS depth
                FROM auth.menus
                WHERE id = :root_id
                UNION ALL
                SELECT child.id, parent.depth + 1
                FROM auth.menus AS child
                INNER JOIN tree AS parent ON child.parent_id = parent.id
            )
            SELECT COALESCE(MAX(depth), 0) AS max_depth
            FROM tree
            """
        ),
        {"root_id": menu_id},
    ).mappings().first()
    return int(row["max_depth"] or 0) if row else 0


def _descendant_ids(db: Session, menu_id: UUID) -> set[str]:
    _ensure_menus_schema(db)
    rows = db.execute(
        text(
            """
            WITH RECURSIVE tree AS (
                SELECT id
                FROM auth.menus
                WHERE parent_id = :root_id
                UNION ALL
                SELECT child.id
                FROM auth.menus AS child
                INNER JOIN tree AS parent ON child.parent_id = parent.id
            )
            SELECT id FROM tree
            """
        ),
        {"root_id": menu_id},
    ).mappings().all()
    return {str(row["id"]) for row in rows}


def _resolve_level(db: Session, parent_id: Optional[UUID], menu_id: Optional[UUID] = None) -> int:
    if parent_id is None:
        if menu_id and _subtree_depth(db, menu_id) > 2:
            raise HTTPException(
                status_code=400,
                detail="Perpindahan ini membuat menu melebihi 3 level.",
            )
        return 1

    if menu_id and str(parent_id) == str(menu_id):
        raise HTTPException(
            status_code=400,
            detail="Menu tidak boleh menjadi induk dari dirinya sendiri.",
        )

    parent = _fetch_menu(db, parent_id)
    if not parent:
        raise HTTPException(status_code=400, detail="Menu induk tidak ditemukan.")

    parent_level = int(parent["level"] or 1)
    if parent_level >= 3:
        raise HTTPException(
            status_code=400,
            detail="Menu hanya bisa bertingkat sampai 3 level.",
        )

    if menu_id and str(parent_id) in _descendant_ids(db, menu_id):
        raise HTTPException(
            status_code=400,
            detail="Menu induk tidak boleh berada di bawah menu ini.",
        )

    if menu_id and parent_level + 1 + _subtree_depth(db, menu_id) > 3:
        raise HTTPException(
            status_code=400,
            detail="Perpindahan ini membuat menu melebihi 3 level.",
        )

    return parent_level + 1


def _refresh_levels(db: Session, menu_id: UUID, root_level: int) -> None:
    _ensure_menus_schema(db)
    db.execute(
        text(
            """
            WITH RECURSIVE tree AS (
                SELECT id, CAST(:root_level AS INTEGER) AS lvl
                FROM auth.menus
                WHERE id = :root_id
                UNION ALL
                SELECT child.id, parent.lvl + 1
                FROM auth.menus AS child
                INNER JOIN tree AS parent ON child.parent_id = parent.id
            )
            UPDATE auth.menus AS target
            SET level = tree.lvl
            FROM tree
            WHERE target.id = tree.id
            """
        ),
        {"root_id": menu_id, "root_level": root_level},
    )


def _build_tree(rows) -> list[dict]:
    nodes: dict[str, dict] = {}
    for row in rows:
        item = dict(row)
        item["children"] = []
        nodes[str(item["id"])] = item

    roots: list[dict] = []
    for item in nodes.values():
        parent_id = item.get("parent_id")
        parent_key = str(parent_id) if parent_id else None
        if parent_key and parent_key in nodes:
            nodes[parent_key]["children"].append(item)
        else:
            roots.append(item)
    return roots


def _column_sql(key: str) -> str:
    return "route" if key == "to" else key


@router.post("/", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
def create_menu(
    payload: MenuCreate,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    _ensure_menus_schema(db)
    level = _resolve_level(db, payload.parent_id)
    data = payload.model_dump()
    data["level"] = level
    data["to"] = data.get("to") or ""
    data["order_position"] = data.get("order_position") or 0
    data["is_favorite"] = bool(data.get("is_favorite"))

    query = f"""
        INSERT INTO auth.menus (
            title, description, bg_class, icon_class, arrow_class, route, icon,
            order_position, parent_id, level, is_favorite
        )
        VALUES (
            :title, :description, :bg_class, :icon_class, :arrow_class, :to, :icon,
            :order_position, :parent_id, :level, :is_favorite
        )
        RETURNING {MENU_COLUMNS};
    """
    result = db.execute(text(query), data).mappings().first()
    db.commit()
    return MenuResponse.model_validate(result)


@router.get("/", response_model=List[MenuResponse])
def get_all_menus(
    flat: bool = Query(False, description="true = daftar datar, false = pohon sampai 3 level"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    _ensure_menus_schema(db)
    rows = db.execute(
        text(
            f"""
            SELECT {MENU_COLUMNS}
            FROM auth.menus
            ORDER BY level ASC, order_position ASC, title ASC
            """
        )
    ).mappings().all()
    tree = _build_tree(rows)
    if flat:
        flat_rows: list[dict] = []

        def walk(nodes: list[dict]) -> None:
            for node in nodes:
                children = node.get("children") or []
                copy = dict(node)
                copy["children"] = []
                flat_rows.append(copy)
                walk(children)

        walk(tree)
        return [MenuResponse.model_validate(row) for row in flat_rows]

    return [MenuResponse.model_validate(node) for node in tree]


@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(
    menu_id: UUID,
    payload: MenuUpdate,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    existing = _fetch_menu(db, menu_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Menu tidak ditemukan")

    update_data = payload.model_dump(exclude_unset=True)
    if "is_favorite" in update_data:
        update_data["is_favorite"] = bool(update_data["is_favorite"])
    if not update_data:
        raise HTTPException(status_code=400, detail="Tidak ada data yang diubah")

    if "parent_id" in payload.model_fields_set:
        parent_id = payload.parent_id
    else:
        parent_id = existing["parent_id"]

    level = _resolve_level(db, parent_id, menu_id)
    update_data["parent_id"] = parent_id
    update_data["level"] = level
    if update_data.get("to") is None and "to" in update_data:
        update_data["to"] = ""

    set_clauses = []
    params = {"id": menu_id}
    for key, value in update_data.items():
        if key not in ALLOWED_UPDATE_FIELDS and key != "level":
            continue
        set_clauses.append(f"{_column_sql(key)} = :{key}")
        params[key] = value

    if not set_clauses:
        raise HTTPException(status_code=400, detail="Tidak ada data yang diubah")

    db.execute(
        text(
            f"""
            UPDATE auth.menus
            SET {", ".join(set_clauses)}
            WHERE id = :id
            """
        ),
        params,
    )
    _refresh_levels(db, menu_id, level)
    db.commit()

    updated = _fetch_menu(db, menu_id)
    return MenuResponse.model_validate(updated)


@router.delete("/{menu_id}", status_code=status.HTTP_200_OK)
def delete_menu(
    menu_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    existing = _fetch_menu(db, menu_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Menu tidak ditemukan")

    child = db.execute(
        text("SELECT id FROM auth.menus WHERE parent_id = :id LIMIT 1"),
        {"id": menu_id},
    ).first()
    if child:
        raise HTTPException(
            status_code=400,
            detail="Menu masih memiliki submenu. Hapus submenu terlebih dahulu.",
        )

    db.execute(text("DELETE FROM auth.menus WHERE id = :id"), {"id": menu_id})
    db.commit()
    return {"message": "Menu berhasil dihapus dari sistem"}
