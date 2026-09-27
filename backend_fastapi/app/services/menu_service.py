"""Menu bertingkat maksimal 3 level (auth.menus.parent_id/level). Kolom DB `route` = field API `to`."""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.schemas.menu import MenuCreate, MenuUpdate

MAX_LEVEL = 3
_COLUMNS = "id, title, description, bg_class, icon_class, arrow_class, route, icon, order_position, parent_id, level, is_favorite"
_UPDATABLE = {"title", "description", "bg_class", "icon_class", "arrow_class", "to", "icon", "order_position", "parent_id", "is_favorite"}


def to_response(row: dict, children: list | None = None) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "bgClass": row["bg_class"],
        "iconClass": row["icon_class"],
        "arrowClass": row["arrow_class"],
        "to": row["route"] or "",
        "icon": row["icon"],
        "order_position": row["order_position"] or 0,
        "parentId": row["parent_id"],
        "level": row["level"] or 1,
        "isFavorite": bool(row.get("is_favorite")),
        "children": children or [],
    }


def _fetch(db: Session, menu_id: UUID) -> dict | None:
    row = db.execute(text(f"SELECT {_COLUMNS} FROM auth.menus WHERE id = :id"), {"id": str(menu_id)}).mappings().first()
    return dict(row) if row else None


def _subtree_depth(db: Session, menu_id: UUID) -> int:
    return db.execute(
        text("""
            WITH RECURSIVE tree AS (
                SELECT id, 0 AS depth FROM auth.menus WHERE id = :root
                UNION ALL
                SELECT c.id, t.depth + 1 FROM auth.menus c JOIN tree t ON c.parent_id = t.id
            )
            SELECT COALESCE(MAX(depth), 0) FROM tree
        """),
        {"root": str(menu_id)},
    ).scalar_one()


def _descendant_ids(db: Session, menu_id: UUID) -> set[str]:
    rows = db.execute(
        text("""
            WITH RECURSIVE tree AS (
                SELECT id FROM auth.menus WHERE parent_id = :root
                UNION ALL
                SELECT c.id FROM auth.menus c JOIN tree t ON c.parent_id = t.id
            )
            SELECT id FROM tree
        """),
        {"root": str(menu_id)},
    ).scalars()
    return {str(r) for r in rows}


def _resolve_level(db: Session, parent_id: UUID | None, menu_id: UUID | None = None) -> int:
    depth = _subtree_depth(db, menu_id) if menu_id else 0
    if parent_id is None:
        if 1 + depth > MAX_LEVEL:
            raise bad_request(f"Perpindahan ini membuat menu melebihi {MAX_LEVEL} level.", field="parent_id")
        return 1
    if menu_id and str(parent_id) == str(menu_id):
        raise bad_request("Menu tidak boleh menjadi induk dari dirinya sendiri.", field="parent_id")

    parent = _fetch(db, parent_id)
    if parent is None:
        raise bad_request("Menu induk tidak ditemukan.", field="parent_id")
    parent_level = parent["level"] or 1
    if parent_level >= MAX_LEVEL:
        raise bad_request(f"Menu hanya bisa bertingkat sampai {MAX_LEVEL} level.", field="parent_id")
    if menu_id and str(parent_id) in _descendant_ids(db, menu_id):
        raise bad_request("Menu induk tidak boleh berada di bawah menu ini.", field="parent_id")
    if parent_level + 1 + depth > MAX_LEVEL:
        raise bad_request(f"Perpindahan ini membuat menu melebihi {MAX_LEVEL} level.", field="parent_id")
    return parent_level + 1


def _refresh_levels(db: Session, menu_id: UUID, root_level: int) -> None:
    db.execute(
        text("""
            WITH RECURSIVE tree AS (
                SELECT id, CAST(:lvl AS INTEGER) AS lvl FROM auth.menus WHERE id = :root
                UNION ALL
                SELECT c.id, t.lvl + 1 FROM auth.menus c JOIN tree t ON c.parent_id = t.id
            )
            UPDATE auth.menus m SET level = tree.lvl FROM tree WHERE m.id = tree.id AND m.level IS DISTINCT FROM tree.lvl
        """),
        {"root": str(menu_id), "lvl": root_level},
    )


def list_menus(db: Session, flat: bool) -> list[dict]:
    rows = [dict(r) for r in db.execute(
        text(f"SELECT {_COLUMNS} FROM auth.menus ORDER BY level, order_position, title")
    ).mappings()]

    nodes = {str(r["id"]): {"row": r, "children": []} for r in rows}
    roots = []
    for node in nodes.values():
        parent_key = str(node["row"]["parent_id"]) if node["row"]["parent_id"] else None
        (nodes[parent_key]["children"] if parent_key in nodes else roots).append(node)

    def build(node: dict) -> dict:
        return to_response(node["row"], [build(c) for c in node["children"]])

    tree = [build(n) for n in roots]
    if not flat:
        return tree

    flat_rows: list[dict] = []

    def walk(items: list[dict]) -> None:
        for item in items:
            flat_rows.append({**item, "children": []})
            walk(item["children"])

    walk(tree)
    return flat_rows


def create_menu(db: Session, payload: MenuCreate) -> dict:
    data = payload.model_dump()
    params = {
        **{k: data[k] for k in ("title", "description", "bg_class", "icon_class", "arrow_class", "icon")},
        "route": data["to"] or "",
        "order_position": data["order_position"] or 0,
        "parent_id": str(data["parent_id"]) if data["parent_id"] else None,
        "level": _resolve_level(db, payload.parent_id),
        "is_favorite": bool(data.get("is_favorite")),
    }
    row = db.execute(
        text(f"""
            INSERT INTO auth.menus (title, description, bg_class, icon_class, arrow_class, route, icon, order_position, parent_id, level, is_favorite)
            VALUES (:title, :description, :bg_class, :icon_class, :arrow_class, :route, :icon, :order_position, :parent_id, :level, :is_favorite)
            RETURNING {_COLUMNS}
        """),
        params,
    ).mappings().one()
    db.commit()
    return to_response(dict(row))


def update_menu(db: Session, menu_id: UUID, payload: MenuUpdate) -> dict:
    existing = _fetch(db, menu_id)
    if existing is None:
        raise not_found("Menu tidak ditemukan")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise bad_request("Tidak ada data yang diubah")

    parent_id = payload.parent_id if "parent_id" in payload.model_fields_set else existing["parent_id"]
    level = _resolve_level(db, parent_id, menu_id)

    assignments, params = ["parent_id = :parent_id", "level = :level"], {
        "id": str(menu_id), "parent_id": str(parent_id) if parent_id else None, "level": level,
    }
    for key, value in changes.items():
        if key not in _UPDATABLE or key == "parent_id":
            continue
        column = "route" if key == "to" else key
        if key == "to":
            value = value or ""
        if value is None and key in {"title", "icon", "order_position"}:
            continue  # kolom NOT NULL: abaikan null
        assignments.append(f"{column} = :{column}")
        params[column] = value

    db.execute(text(f"UPDATE auth.menus SET {', '.join(assignments)} WHERE id = :id"), params)
    _refresh_levels(db, menu_id, level)
    db.commit()
    return to_response(_fetch(db, menu_id))


def delete_menu(db: Session, menu_id: UUID) -> None:
    if _fetch(db, menu_id) is None:
        raise not_found("Menu tidak ditemukan")
    has_child = db.execute(text("SELECT 1 FROM auth.menus WHERE parent_id = :id LIMIT 1"), {"id": str(menu_id)}).first()
    if has_child:
        raise bad_request("Menu masih memiliki submenu. Hapus submenu terlebih dahulu.")
    db.execute(text("DELETE FROM auth.menus WHERE id = :id"), {"id": str(menu_id)})
    db.commit()
