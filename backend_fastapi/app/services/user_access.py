"""
Gabungan hak akses seorang user dari SEMUA role-nya.

Sumber yang dipakai (mana yang ada di database):
- menu: public/auth.log_akses_menu dan auth.role_menus
- data: log_akses_data dan auth.role_data_scopes
- transaksi: log_akses_transaksi dan auth.role_permissions

Baris yang sama dari role berbeda digabung sekali, supaya pembatasan
di menu, data wilayah, dan jenis geo tidak error karena data redundan.
"""
from fastapi import HTTPException, status
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

_TABLE_NAMES = (
    "log_akses_menu",
    "log_akses_data",
    "log_akses_transaksi",
    "role_menus",
    "role_data_scopes",
    "role_permissions",
    "permissions",
    "layer_types",
)
_ALLOWED_SCHEMAS = {"auth", "public", "spatial"}

_SCOPE_SQL = """
SELECT DISTINCT
    a.code AS kode_area,
    COALESCE(c_direct.code, c_via_estate.code, c_via_div.code) AS kode_pt,
    COALESCE(e_direct.code, e_via_div.code) AS kode_est,
    d.code AS kode_afd
FROM {table} AS s
LEFT JOIN master.areas AS a ON a.id = s.area_id
LEFT JOIN master.companies AS c_direct ON c_direct.id = s.company_id
LEFT JOIN master.estates AS e_direct ON e_direct.id = s.estate_id
LEFT JOIN master.companies AS c_via_estate ON c_via_estate.id = e_direct.company_id
LEFT JOIN master.divisions AS d ON d.id = s.division_id
LEFT JOIN master.estates AS e_via_div ON e_via_div.id = d.estate_id
LEFT JOIN master.companies AS c_via_div ON c_via_div.id = e_via_div.company_id
WHERE s.role_id::text IN :role_ids
"""


def is_superadmin(user) -> bool:
    return any((getattr(role, "nama", None) or "").strip().lower() == "superadmin" for role in (user.roles or []))


def role_ids(user) -> list[str]:
    seen: list[str] = []
    for role in user.roles or []:
        value = str(role.id)
        if value not in seen:
            seen.append(value)
    return seen


def _locate(db: Session) -> dict[str, list[str]]:
    rows = db.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name IN (
                'log_akses_menu', 'log_akses_data', 'log_akses_transaksi',
                'role_menus', 'role_data_scopes', 'role_permissions', 'permissions', 'layer_types'
            )
              AND table_schema IN ('auth', 'public', 'spatial')
            """
        )
    ).all()
    found: dict[str, list[str]] = {}
    for schema, name in rows:
        if schema not in _ALLOWED_SCHEMAS or name not in _TABLE_NAMES:
            continue
        qualified = f"{schema}.{name}"
        bucket = found.setdefault(name, [])
        if qualified not in bucket:
            bucket.append(qualified)
    return found


def _pick(options: list[str], preferred_schema: str) -> str | None:
    for item in options:
        if item.startswith(f"{preferred_schema}."):
            return item
    return options[0] if options else None


def _distinct(db: Session, sql: str, role_id_list: list[str]):
    if not role_id_list:
        return []
    stmt = text(sql).bindparams(bindparam("role_ids", expanding=True))
    try:
        with db.begin_nested():
            return db.execute(stmt, {"role_ids": role_id_list}).mappings().all()
    except Exception:
        return []


def _scope_key(row: dict) -> tuple:
    return tuple((row.get(key) or None) for key in ("kode_area", "kode_pt", "kode_est", "kode_afd"))


def merged_access(db: Session, user) -> dict:
    """Union hak akses. Superadmin tetap menerima daftar (frontend membuka semua)."""
    ids = role_ids(user)
    tables = _locate(db) if ids else {}
    menus: list[str] = []
    menu_seen: set[str] = set()
    scopes: list[dict] = []
    scope_seen: set[tuple] = set()
    transactions: list[str] = []
    trx_seen: set[str] = set()

    def add_menu(value) -> None:
        text_value = str(value or "").strip()
        if text_value and text_value not in menu_seen:
            menu_seen.add(text_value)
            menus.append(text_value)

    def add_scope(row) -> None:
        item = {
            "kode_pt": row.get("kode_pt"),
            "kode_est": row.get("kode_est"),
            "kode_area": row.get("kode_area"),
            "kode_afd": row.get("kode_afd"),
        }
        key = _scope_key(item)
        if key in scope_seen or key == (None, None, None, None):
            return
        scope_seen.add(key)
        scopes.append(item)

    def add_trx(value) -> None:
        text_value = str(value or "").strip()
        folded = text_value.lower()
        if text_value and folded not in trx_seen:
            trx_seen.add(folded)
            transactions.append(text_value)

    for table in tables.get("log_akses_menu", []):
        for row in _distinct(
            db,
            f"SELECT DISTINCT menu_id::text AS menu_id FROM {table} WHERE role_id::text IN :role_ids",
            ids,
        ):
            add_menu(row["menu_id"])
    for table in tables.get("role_menus", []):
        for row in _distinct(
            db,
            f"SELECT DISTINCT menu_id::text AS menu_id FROM {table} WHERE role_id::text IN :role_ids",
            ids,
        ):
            add_menu(row["menu_id"])

    for table in tables.get("log_akses_data", []):
        for row in _distinct(
            db,
            f"""
            SELECT DISTINCT kode_pt, kode_est, kode_area, kode_afd
            FROM {table}
            WHERE role_id::text IN :role_ids
            """,
            ids,
        ):
            add_scope(row)
    for table in tables.get("role_data_scopes", []):
        for row in _distinct(db, _SCOPE_SQL.format(table=table), ids):
            add_scope(row)

    for table in tables.get("log_akses_transaksi", []):
        for row in _distinct(
            db,
            f"""
            SELECT DISTINCT nama_table_transaksi
            FROM {table}
            WHERE role_id::text IN :role_ids
            """,
            ids,
        ):
            add_trx(row["nama_table_transaksi"])
    permissions = _pick(tables.get("permissions", []), "auth")
    role_permissions = _pick(tables.get("role_permissions", []), "auth")
    if ids and permissions and role_permissions:
        for row in _distinct(
            db,
            f"""
            SELECT DISTINCT p.resource AS nama_table_transaksi
            FROM {role_permissions} rp
            JOIN {permissions} p ON p.id = rp.permission_id
            WHERE rp.role_id::text IN :role_ids
              AND p.resource LIKE '%.%'
            """,
            ids,
        ):
            add_trx(row["nama_table_transaksi"])

    return {"akses_menu": menus, "akses_data": scopes, "akses_transaksi": transactions}


def transaction_keys(db: Session, user) -> set[str] | None:
    """None artinya tidak dibatasi (superadmin)."""
    if is_superadmin(user):
        return None
    access = merged_access(db, user)
    return {item.strip().lower() for item in access["akses_transaksi"] if str(item).strip()}


def layer_allowed(db: Session, user, code: str) -> bool:
    allowed = transaction_keys(db, user)
    if allowed is None:
        return True
    folded = (code or "").strip().lower()
    if not folded:
        return False
    if folded in allowed:
        return True
    layer_types = _pick(_locate(db).get("layer_types", []), "spatial")
    if not layer_types:
        return False
    try:
        with db.begin_nested():
            table_name = db.execute(
                text(f"SELECT table_name FROM {layer_types} WHERE lower(code) = :c LIMIT 1"),
                {"c": folded},
            ).scalar()
    except Exception:
        table_name = None
    return bool(table_name) and str(table_name).strip().lower() in allowed


def require_layer(db: Session, user, code: str) -> None:
    if layer_allowed(db, user, code):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Tidak ada hak akses transaksi untuk jenis '{code}'.",
    )
