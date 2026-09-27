"""
Hak akses role: menu (auth.role_menus), data wilayah (auth.role_data_scopes)
dan tabel transaksi (auth.permissions dengan resource = '<schema>.<tabel>', action = 'read').

Scope data di v3 menunjuk tepat SATU node hierarki (area / company / estate /
division) lewat id. FE lama bekerja dengan kode (kode_area, kode_pt, kode_est,
kode_afd), jadi scope diekspansi ke kode lewat master.v_block_hierarchy.
Area tidak ada di hierarki master -- area sebuah company/estate/division
diambil dari area statement terbaru blok-bloknya, sehingga satu scope bisa
menghasilkan >1 baris kalau wilayahnya tersebar di beberapa area.
"""
from collections import OrderedDict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.schemas.access import AksesDataInput, AreaTreeSchema

TRX_ACTION = "read"
TRANSACTION_SCHEMAS = ("trx", "spatial")
NON_TRANSACTION_TABLES = {"spatial.layer_types", "spatial.palm_trees"}

_SCOPE_EXPANSION_SQL = """
WITH h AS (
    SELECT DISTINCT area_id, area_code, company_id, estate_id, division_id
    FROM master.v_block_hierarchy
),
s AS (
    SELECT * FROM auth.role_data_scopes WHERE role_id = ANY(CAST(:role_ids AS uuid[]))
)
SELECT s.id, s.role_id, s.created_at, 'area' AS level,
       ar.code AS area_code, ar.name AS area_name,
       NULL::bigint AS company_id, NULL AS company_code, NULL AS company_name,
       NULL::bigint AS estate_id, NULL AS estate_code, NULL AS estate_name,
       NULL::bigint AS division_id, NULL AS division_code
FROM s JOIN master.areas ar ON ar.id = s.area_id
UNION ALL
SELECT DISTINCT s.id, s.role_id, s.created_at, 'company',
       ar.code, ar.name, co.id, co.code, co.name,
       NULL::bigint, NULL, NULL, NULL::bigint, NULL
FROM s JOIN master.companies co ON co.id = s.company_id
LEFT JOIN h ON h.company_id = co.id
LEFT JOIN master.areas ar ON ar.id = h.area_id
UNION ALL
SELECT DISTINCT s.id, s.role_id, s.created_at, 'estate',
       ar.code, ar.name, co.id, co.code, co.name,
       es.id, es.code, es.name, NULL::bigint, NULL
FROM s JOIN master.estates es ON es.id = s.estate_id
JOIN master.companies co ON co.id = es.company_id
LEFT JOIN h ON h.estate_id = es.id
LEFT JOIN master.areas ar ON ar.id = h.area_id
UNION ALL
SELECT DISTINCT s.id, s.role_id, s.created_at, 'division',
       ar.code, ar.name, co.id, co.code, co.name,
       es.id, es.code, es.name, dv.id, dv.code
FROM s JOIN master.divisions dv ON dv.id = s.division_id
JOIN master.estates es ON es.id = dv.estate_id
JOIN master.companies co ON co.id = es.company_id
LEFT JOIN h ON h.division_id = dv.id
LEFT JOIN master.areas ar ON ar.id = h.area_id
ORDER BY 1
"""


# =====================================================================
# SCOPE DATA WILAYAH
# =====================================================================

def expanded_scopes(db: Session, role_ids: list[UUID]) -> list[dict]:
    if not role_ids:
        return []
    return [dict(r) for r in db.execute(text(_SCOPE_EXPANSION_SQL), {"role_ids": [str(r) for r in role_ids]}).mappings()]


def scopes_as_codes(rows: list[dict]) -> list[dict]:
    """Bentuk `akses_data` di response login/me (kode saja)."""
    seen, result = set(), []
    for r in rows:
        item = (r["area_code"], r["company_code"], r["estate_code"], r["division_code"])
        if item not in seen:
            seen.add(item)
            result.append({"kode_pt": item[1], "kode_est": item[2], "kode_area": item[0], "kode_afd": item[3]})
    return result


def scopes_as_log_rows(rows: list[dict]) -> list[dict]:
    """Bentuk `akses_data` di RoleResponse (baris log lama, lengkap dengan id scope)."""
    return [
        {
            "id": r["id"], "role_id": str(r["role_id"]), "level": r["level"],
            "kode_area": r["area_code"], "kode_pt": r["company_code"],
            "kode_est": r["estate_code"], "kode_afd": r["division_code"],
            "created_date": r["created_at"], "update_date": r["created_at"],
        }
        for r in rows
    ]


def scopes_as_tree(rows: list[dict]) -> list[dict]:
    areas: OrderedDict[str, dict] = OrderedDict()
    for r in rows:
        area_key = r["area_code"] or "UNASSIGNED"
        area = areas.setdefault(area_key, {"id_area": area_key, "nama_area": r["area_name"] or area_key, "perusahaan": OrderedDict()})
        if r["company_id"] is None:
            continue
        company = area["perusahaan"].setdefault(r["company_id"], {
            "id_perusahaan": str(r["company_id"]),
            "nama_perusahaan": r["company_name"] or r["company_code"],
            "estate": OrderedDict(),
        })
        if r["estate_id"] is None:
            continue
        estate = company["estate"].setdefault(r["estate_id"], {
            "id_estate": str(r["estate_id"]), "nama_estate": r["estate_name"] or r["estate_code"], "afdeling": OrderedDict(),
        })
        if r["division_id"] is not None:
            estate["afdeling"].setdefault(r["division_id"], {"id_afdeling": str(r["division_id"]), "nama_afdeling": r["division_code"]})

    return [
        {
            "id_area": a["id_area"], "nama_area": a["nama_area"],
            "perusahaan": [
                {
                    "id_perusahaan": c["id_perusahaan"], "nama_perusahaan": c["nama_perusahaan"],
                    "estate": [{**e, "afdeling": list(e["afdeling"].values())} for e in c["estate"].values()],
                }
                for c in a["perusahaan"].values()
            ],
        }
        for a in areas.values()
    ]


def _resolve_id(db: Session, table: str, value: str | None, extra_where: str = "", extra_params: dict | None = None) -> int | None:
    """Cari id master berdasarkan id numerik ATAU kode (case-insensitive)."""
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    params = {"v": value, **(extra_params or {})}
    sql = f"SELECT id FROM master.{table} WHERE (id::text = :v OR upper(code) = upper(:v)) {extra_where} ORDER BY (id::text = :v) DESC LIMIT 1"
    return db.execute(text(sql), params).scalar()


def _insert_scope(db: Session, role_id: UUID, **ids: int | None) -> int:
    result = db.execute(
        text("""
            INSERT INTO auth.role_data_scopes (role_id, area_id, company_id, estate_id, division_id)
            VALUES (:role_id, :area_id, :company_id, :estate_id, :division_id)
            ON CONFLICT DO NOTHING
        """),
        {"role_id": str(role_id), "area_id": None, "company_id": None, "estate_id": None, "division_id": None, **ids},
    )
    return result.rowcount


def add_scopes_from_tree(db: Session, role_id: UUID, tree: list[AreaTreeSchema]) -> dict:
    """Setiap daun pohon (node terdalam yang dipilih) menjadi satu scope."""
    inserted, unresolved = 0, []
    for area in tree:
        if not area.perusahaan:
            area_id = _resolve_id(db, "areas", area.id_area)
            if area_id is None:
                unresolved.append(f"area:{area.id_area}")
            else:
                inserted += _insert_scope(db, role_id, area_id=area_id)
            continue
        for pt in area.perusahaan:
            company_id = _resolve_id(db, "companies", pt.id_perusahaan)
            if company_id is None:
                unresolved.append(f"pt:{pt.id_perusahaan}")
                continue
            if not pt.estate:
                inserted += _insert_scope(db, role_id, company_id=company_id)
                continue
            for est in pt.estate:
                estate_id = _resolve_id(db, "estates", est.id_estate)
                if estate_id is None:
                    unresolved.append(f"estate:{est.id_estate}")
                    continue
                if not est.afdeling:
                    inserted += _insert_scope(db, role_id, estate_id=estate_id)
                    continue
                for afd in est.afdeling:
                    division_id = _resolve_id(db, "divisions", afd.id_afdeling, "AND estate_id = :e", {"e": estate_id})
                    if division_id is None:
                        unresolved.append(f"afdeling:{afd.id_afdeling}")
                        continue
                    inserted += _insert_scope(db, role_id, division_id=division_id)
    return {"inserted": inserted, "unresolved": unresolved}


def add_scopes_from_legacy_payload(db: Session, role_id: UUID, items: list[AksesDataInput]) -> None:
    """Payload `akses_data` lama di POST/PUT /roles: satu PT dengan list area/afdeling."""
    for item in items:
        estate_id = _resolve_id(db, "estates", item.kode_est)
        if item.kode_afd:
            for afd in item.kode_afd:
                where, params = ("AND estate_id = :e", {"e": estate_id}) if estate_id else ("", {})
                division_id = _resolve_id(db, "divisions", afd, where, params)
                if division_id is None:
                    raise bad_request(f"Afdeling '{afd}' tidak ditemukan.", field="akses_data")
                _insert_scope(db, role_id, division_id=division_id)
        elif estate_id:
            _insert_scope(db, role_id, estate_id=estate_id)
        elif item.kode_pt:
            company_id = _resolve_id(db, "companies", item.kode_pt)
            if company_id is None:
                raise bad_request(f"PT '{item.kode_pt}' tidak ditemukan.", field="akses_data")
            _insert_scope(db, role_id, company_id=company_id)
        else:
            for area in item.kode_area or []:
                area_id = _resolve_id(db, "areas", area)
                if area_id is None:
                    raise bad_request(f"Area '{area}' tidak ditemukan.", field="akses_data")
                _insert_scope(db, role_id, area_id=area_id)


def clear_scopes(db: Session, role_id: UUID) -> None:
    db.execute(text("DELETE FROM auth.role_data_scopes WHERE role_id = :r"), {"r": str(role_id)})


def delete_scope(db: Session, scope_id: int) -> None:
    deleted = db.execute(text("DELETE FROM auth.role_data_scopes WHERE id = :id"), {"id": scope_id}).rowcount
    if not deleted:
        raise not_found("Hak akses data tidak ditemukan")


# =====================================================================
# MENU
# =====================================================================

def menu_access_id(role_id, menu_id) -> str:
    return f"{role_id}:{menu_id}"


def split_access_id(access_id: str) -> tuple[str, str]:
    role_id, sep, other_id = access_id.partition(":")
    if not sep:
        raise bad_request("Format id akses harus '<role_id>:<id>'.")
    try:
        UUID(role_id), UUID(other_id)
    except ValueError:
        raise bad_request("Id akses tidak valid.") from None
    return role_id, other_id


def role_menu_rows(db: Session, role_id: UUID | str) -> list[dict]:
    rows = db.execute(
        text("SELECT role_id, menu_id, created_at FROM auth.role_menus WHERE role_id = :r ORDER BY created_at"),
        {"r": str(role_id)},
    ).mappings()
    return [
        {"id": menu_access_id(r["role_id"], r["menu_id"]), "role_id": str(r["role_id"]), "menu_id": str(r["menu_id"]),
         "created_date": r["created_at"], "update_date": r["created_at"]}
        for r in rows
    ]


def role_menu_rows_for_roles(db: Session, role_ids: list[UUID]) -> list[dict]:
    """Sama seperti `role_menu_rows` tapi diagregasi (dedup) untuk banyak role sekaligus (user dengan multi-role)."""
    if not role_ids:
        return []
    rows = db.execute(
        text("SELECT DISTINCT ON (menu_id) role_id, menu_id, created_at FROM auth.role_menus "
             "WHERE role_id = ANY(CAST(:ids AS uuid[])) ORDER BY menu_id, created_at"),
        {"ids": [str(r) for r in role_ids]},
    ).mappings()
    return [
        {"id": menu_access_id(r["role_id"], r["menu_id"]), "role_id": str(r["role_id"]), "menu_id": str(r["menu_id"]),
         "created_date": r["created_at"], "update_date": r["created_at"]}
        for r in rows
    ]


def add_menu(db: Session, role_id: str, menu_id: str) -> dict:
    _ensure_exists(db, "auth.roles", role_id, "Role")
    _ensure_exists(db, "auth.menus", menu_id, "Menu")
    db.execute(
        text("INSERT INTO auth.role_menus (role_id, menu_id) VALUES (:r, :m) ON CONFLICT DO NOTHING"),
        {"r": role_id, "m": menu_id},
    )
    return next(row for row in role_menu_rows(db, role_id) if row["menu_id"] == menu_id)


def delete_menu(db: Session, role_id: str, menu_id: str) -> None:
    deleted = db.execute(
        text("DELETE FROM auth.role_menus WHERE role_id = :r AND menu_id = :m"), {"r": role_id, "m": menu_id}
    ).rowcount
    if not deleted:
        raise not_found("Hak akses menu tidak ditemukan")


def replace_menus(db: Session, role_id: UUID, menu_ids: list[str]) -> None:
    db.execute(text("DELETE FROM auth.role_menus WHERE role_id = :r"), {"r": str(role_id)})
    for menu_id in dict.fromkeys(m for m in menu_ids if m):
        add_menu(db, str(role_id), menu_id)


# =====================================================================
# TRANSAKSI (permission read per tabel)
# =====================================================================

def transaction_tables(db: Session) -> list[str]:
    rows = db.execute(
        text("""
            SELECT table_schema || '.' || table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND table_schema = ANY(:schemas)
            ORDER BY 1
        """),
        {"schemas": list(TRANSACTION_SCHEMAS)},
    ).scalars()
    return [name for name in rows if name not in NON_TRANSACTION_TABLES]


def role_transaction_rows(db: Session, role_id: UUID | str) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT rp.role_id, p.id AS permission_id, p.resource, rp.created_at
            FROM auth.role_permissions rp JOIN auth.permissions p ON p.id = rp.permission_id
            WHERE rp.role_id = :r AND p.action = :a AND p.resource LIKE '%.%'
            ORDER BY p.resource
        """),
        {"r": str(role_id), "a": TRX_ACTION},
    ).mappings()
    return [
        {"id": menu_access_id(r["role_id"], r["permission_id"]), "role_id": str(r["role_id"]),
         "nama_table_transaksi": r["resource"], "created_date": r["created_at"], "update_date": r["created_at"]}
        for r in rows
    ]


def role_transaction_rows_for_roles(db: Session, role_ids: list[UUID]) -> list[dict]:
    """Sama seperti `role_transaction_rows` tapi diagregasi (dedup) untuk banyak role sekaligus (user dengan multi-role)."""
    if not role_ids:
        return []
    rows = db.execute(
        text("""
            SELECT DISTINCT ON (p.resource) rp.role_id, p.id AS permission_id, p.resource, rp.created_at
            FROM auth.role_permissions rp JOIN auth.permissions p ON p.id = rp.permission_id
            WHERE rp.role_id = ANY(CAST(:ids AS uuid[])) AND p.action = :a AND p.resource LIKE '%.%'
            ORDER BY p.resource, rp.created_at
        """),
        {"ids": [str(r) for r in role_ids], "a": TRX_ACTION},
    ).mappings()
    return [
        {"id": menu_access_id(r["role_id"], r["permission_id"]), "role_id": str(r["role_id"]),
         "nama_table_transaksi": r["resource"], "created_date": r["created_at"], "update_date": r["created_at"]}
        for r in rows
    ]


def add_transaction(db: Session, role_id: str, table_name: str) -> dict:
    _ensure_exists(db, "auth.roles", role_id, "Role")
    if table_name not in transaction_tables(db):
        raise bad_request(f"Tabel transaksi '{table_name}' tidak dikenal. Lihat GET /database/tables.", field="nama_table_transaksi")
    permission_id = db.execute(
        text("""
            INSERT INTO auth.permissions (code, resource, action, description)
            VALUES (:code, :res, :act, :desc)
            ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code
            RETURNING id
        """),
        {"code": f"{table_name}:{TRX_ACTION}", "res": table_name, "act": TRX_ACTION, "desc": f"Akses baca tabel {table_name}"},
    ).scalar_one()
    db.execute(
        text("INSERT INTO auth.role_permissions (role_id, permission_id) VALUES (:r, :p) ON CONFLICT DO NOTHING"),
        {"r": role_id, "p": permission_id},
    )
    return next(row for row in role_transaction_rows(db, role_id) if row["nama_table_transaksi"] == table_name)


def delete_transaction(db: Session, role_id: str, permission_id: str) -> None:
    deleted = db.execute(
        text("DELETE FROM auth.role_permissions WHERE role_id = :r AND permission_id = :p"),
        {"r": role_id, "p": permission_id},
    ).rowcount
    if not deleted:
        raise not_found("Hak akses transaksi tidak ditemukan")


def replace_transactions(db: Session, role_id: UUID, tables: list[str]) -> None:
    db.execute(
        text("""
            DELETE FROM auth.role_permissions rp USING auth.permissions p
            WHERE rp.permission_id = p.id AND rp.role_id = :r AND p.action = :a AND p.resource LIKE '%.%'
        """),
        {"r": str(role_id), "a": TRX_ACTION},
    )
    for table_name in dict.fromkeys(t for t in tables if t):
        add_transaction(db, str(role_id), table_name)


def _ensure_exists(db: Session, table: str, row_id: str, label: str) -> None:
    try:
        UUID(str(row_id))
    except ValueError:
        raise bad_request(f"{label} id '{row_id}' bukan UUID yang valid.") from None
    if db.execute(text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": str(row_id)}).first() is None:
        raise not_found(f"{label} dengan id {row_id} tidak ditemukan")
