"""
Gabungan hak akses seorang user dari SEMUA role-nya.

Sumber yang dipakai (mana yang ada di database):
- menu: public/auth.log_akses_menu dan auth.role_menus
- data: log_akses_data dan auth.role_data_scopes
- transaksi: log_akses_transaksi dan auth.role_permissions

Baris yang sama dari role berbeda digabung sekali, supaya pembatasan
di menu, data wilayah, dan jenis geo tidak error karena data redundan.
"""
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.services import access_service
from app.services.block_filter import BlockFilter

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

# Nama fisik (yang disimpan di role) <-> kode layer / nama tabel lama di API peta.
_GRANT_ALIASES = {
    "spatial.tph_points": ("tph",),
    "spatial.tree_censuses": ("sawit",),
    "spatial.palm_trees": ("sawit",),
    "spatial.slope_polygons": ("slope",),
    "spatial.landuse_polygons": ("landuse",),
    "spatial.roads": ("jalan",),
    "spatial.bridges": ("jembatan",),
    "spatial.block_boundaries": ("blok",),
    "trx.block_productions": ("trx_produksi_tbs",),
    "trx.area_statements": ("trx_areal_statement",),
    "trx.harvest_rotations": ("trx_rotasi_pusingan",),
}

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


def _uuid_role_ids(user) -> list[UUID]:
    result: list[UUID] = []
    for value in role_ids(user):
        try:
            result.append(UUID(value))
        except ValueError:
            continue
    return result


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

    uuid_ids = _uuid_role_ids(user)
    scope_loaded = False
    if uuid_ids:
        try:
            with db.begin_nested():
                for item in access_service.scopes_as_codes(access_service.expanded_scopes(db, uuid_ids)):
                    add_scope(item)
                scope_loaded = True
        except Exception:
            scope_loaded = False
    # Cadangan bila view hierarki tidak ada: kode PT/estate/afdeling tetap terisi, area boleh kosong.
    if not scope_loaded:
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
    if uuid_ids:
        try:
            with db.begin_nested():
                for row in access_service.role_transaction_rows_for_roles(db, uuid_ids):
                    add_trx(row["nama_table_transaksi"])
        except Exception:
            pass

    return {"akses_menu": menus, "akses_data": scopes, "akses_transaksi": transactions}


def _expand_grants(names: set[str]) -> set[str]:
    expanded = set(names)
    changed = True
    while changed:
        changed = False
        for table, aliases in _GRANT_ALIASES.items():
            group = {table, *aliases}
            if expanded & group and not group <= expanded:
                expanded |= group
                changed = True
    return expanded


def transaction_keys(db: Session, user) -> set[str] | None:
    """None artinya tidak dibatasi (superadmin). Kunci sudah termasuk alias layer & nama tabel lama."""
    if is_superadmin(user):
        return None
    access = merged_access(db, user)
    raw = {item.strip().lower() for item in access["akses_transaksi"] if str(item).strip()}
    return _expand_grants(raw)


def transaction_granted(db: Session, user, *keys: str) -> bool:
    allowed = transaction_keys(db, user)
    if allowed is None:
        return True
    return any(str(key).strip().lower() in allowed for key in keys if str(key).strip())


def require_transaction(db: Session, user, *keys: str) -> None:
    if transaction_granted(db, user, *keys):
        return
    label = next((str(key) for key in keys if str(key).strip()), "transaksi")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Tidak ada hak akses transaksi untuk '{label}'.",
    )


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


# ---------------------------------------------------------------------
# Pembatasan wilayah (hak akses data) untuk query peta
# ---------------------------------------------------------------------

def _uniq_text(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text_value = str(value or "").strip()
        key = text_value.upper()
        if text_value and key not in seen:
            seen.add(key)
            result.append(text_value)
    return result


def _uniq_int(values) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value is None:
            continue
        number = int(value)
        if number not in seen:
            seen.add(number)
            result.append(number)
    return result


@dataclass
class DataScope:
    """Union scope semua role user. `unrestricted` hanya untuk superadmin."""

    unrestricted: bool = False
    area_codes: list[str] = field(default_factory=list)
    visible_areas: list[str] = field(default_factory=list)
    companies: list[int] = field(default_factory=list)
    estates: list[int] = field(default_factory=list)
    divisions: list[int] = field(default_factory=list)

    def _id_parts(self, company_sql: str, estate_sql: str, division_sql: str) -> tuple[list[str], dict]:
        parts: list[str] = []
        params: dict = {}
        if self.companies:
            parts.append(company_sql)
            params["dsc_companies"] = self.companies
        if self.estates:
            parts.append(estate_sql)
            params["dsc_estates"] = self.estates
        if self.divisions:
            parts.append(division_sql)
            params["dsc_divisions"] = self.divisions
        return parts, params

    def hierarchy_clause(self, level: str) -> tuple[str, dict] | None:
        """None = tidak difilter. Klause SQL memakai alias halaman master (ar / co / es / dv)."""
        if self.unrestricted:
            return None
        parts, params = [], {}
        if level == "area":
            if self.visible_areas:
                parts.append("upper(ar.code) = ANY(CAST(:dsc_areas AS text[]))")
                params["dsc_areas"] = [code.upper() for code in self.visible_areas]
            id_parts, id_params = self._id_parts(
                "co.id = ANY(CAST(:dsc_companies AS bigint[]))",
                "es.id = ANY(CAST(:dsc_estates AS bigint[]))",
                "dv.id = ANY(CAST(:dsc_divisions AS bigint[]))",
            )
            if id_parts:
                parts.append(
                    "EXISTS (SELECT 1 FROM master.blocks bl "
                    "JOIN master.divisions dv ON dv.id = bl.division_id "
                    "JOIN master.estates es ON es.id = dv.estate_id "
                    "JOIN master.companies co ON co.id = es.company_id "
                    "LEFT JOIN LATERAL (SELECT a.area_id FROM trx.area_statements a "
                    "WHERE a.block_id = bl.id ORDER BY a.period DESC LIMIT 1) la ON true "
                    f"WHERE la.area_id = ar.id AND ({' OR '.join(id_parts)}))"
                )
                params.update(id_params)
        elif level == "company":
            id_parts, id_params = self._id_parts(
                "co.id = ANY(CAST(:dsc_companies AS bigint[]))",
                "co.id IN (SELECT company_id FROM master.estates WHERE id = ANY(CAST(:dsc_estates AS bigint[])))",
                "co.id IN (SELECT es.company_id FROM master.divisions dv "
                "JOIN master.estates es ON es.id = dv.estate_id WHERE dv.id = ANY(CAST(:dsc_divisions AS bigint[])))",
            )
            parts.extend(id_parts)
            params.update(id_params)
            if self.area_codes:
                parts.append(
                    "EXISTS (SELECT 1 FROM master.blocks bl "
                    "JOIN master.divisions dv ON dv.id = bl.division_id "
                    "JOIN master.estates es ON es.id = dv.estate_id "
                    "LEFT JOIN LATERAL (SELECT a.area_id FROM trx.area_statements a "
                    "WHERE a.block_id = bl.id ORDER BY a.period DESC LIMIT 1) la ON true "
                    "LEFT JOIN master.areas ar ON ar.id = la.area_id "
                    "WHERE es.company_id = co.id AND upper(ar.code) = ANY(CAST(:dsc_areas AS text[])))"
                )
                params["dsc_areas"] = [code.upper() for code in self.area_codes]
        elif level == "estate":
            id_parts, id_params = self._id_parts(
                "co.id = ANY(CAST(:dsc_companies AS bigint[]))",
                "es.id = ANY(CAST(:dsc_estates AS bigint[]))",
                "es.id IN (SELECT estate_id FROM master.divisions WHERE id = ANY(CAST(:dsc_divisions AS bigint[])))",
            )
            parts.extend(id_parts)
            params.update(id_params)
            if self.area_codes:
                parts.append(
                    "EXISTS (SELECT 1 FROM master.blocks bl "
                    "JOIN master.divisions dv ON dv.id = bl.division_id "
                    "LEFT JOIN LATERAL (SELECT a.area_id FROM trx.area_statements a "
                    "WHERE a.block_id = bl.id ORDER BY a.period DESC LIMIT 1) la ON true "
                    "LEFT JOIN master.areas ar ON ar.id = la.area_id "
                    "WHERE dv.estate_id = es.id AND upper(ar.code) = ANY(CAST(:dsc_areas AS text[])))"
                )
                params["dsc_areas"] = [code.upper() for code in self.area_codes]
        elif level == "division":
            id_parts, id_params = self._id_parts(
                "co.id = ANY(CAST(:dsc_companies AS bigint[]))",
                "es.id = ANY(CAST(:dsc_estates AS bigint[]))",
                "dv.id = ANY(CAST(:dsc_divisions AS bigint[]))",
            )
            parts.extend(id_parts)
            params.update(id_params)
            if self.area_codes:
                parts.append(
                    "EXISTS (SELECT 1 FROM master.blocks bl "
                    "JOIN master.divisions dv2 ON dv2.id = bl.division_id "
                    "LEFT JOIN LATERAL (SELECT a.area_id FROM trx.area_statements a "
                    "WHERE a.block_id = bl.id ORDER BY a.period DESC LIMIT 1) la ON true "
                    "LEFT JOIN master.areas ar ON ar.id = la.area_id "
                    "WHERE dv2.id = dv.id AND upper(ar.code) = ANY(CAST(:dsc_areas AS text[])))"
                )
                params["dsc_areas"] = [code.upper() for code in self.area_codes]
        else:
            return ("FALSE", {})
        if not parts:
            return ("FALSE", {})
        return ("(" + " OR ".join(parts) + ")", params)

    def block_clause(self) -> tuple[str, dict, bool] | None:
        """Klausa pada query `master.blocks bl` (+ dv, es, co, dan `ar` bila perlu). None = bebas."""
        if self.unrestricted:
            return None
        parts, params = [], {}
        needs_area = False
        if self.area_codes:
            parts.append("upper(ar.code) = ANY(CAST(:dsc_areas AS text[]))")
            params["dsc_areas"] = [code.upper() for code in self.area_codes]
            needs_area = True
        id_parts, id_params = self._id_parts(
            "co.id = ANY(CAST(:dsc_companies AS bigint[]))",
            "es.id = ANY(CAST(:dsc_estates AS bigint[]))",
            "dv.id = ANY(CAST(:dsc_divisions AS bigint[]))",
        )
        parts.extend(id_parts)
        params.update(id_params)
        if not parts:
            return ("FALSE", {}, False)
        return ("(" + " OR ".join(parts) + ")", params, needs_area)


def resolve_scope(db: Session, user) -> DataScope:
    if is_superadmin(user):
        return DataScope(unrestricted=True)
    ids = _uuid_role_ids(user)
    rows: list[dict] = []
    if ids:
        try:
            with db.begin_nested():
                rows = access_service.expanded_scopes(db, ids)
        except Exception:
            rows = []
    areas, visible, companies, estates, divisions = [], [], [], [], []
    for row in rows:
        if row.get("area_code"):
            visible.append(row["area_code"])
        level = row.get("level")
        if level == "area" and row.get("area_code"):
            areas.append(row["area_code"])
        elif level == "company" and row.get("company_id") is not None:
            companies.append(row["company_id"])
        elif level == "estate" and row.get("estate_id") is not None:
            estates.append(row["estate_id"])
        elif level == "division" and row.get("division_id") is not None:
            divisions.append(row["division_id"])
    return DataScope(
        area_codes=_uniq_text(areas),
        visible_areas=_uniq_text(visible),
        companies=_uniq_int(companies),
        estates=_uniq_int(estates),
        divisions=_uniq_int(divisions),
    )


def hierarchy_clause(db: Session, user, level: str) -> tuple[str, dict] | None:
    return resolve_scope(db, user).hierarchy_clause(level)


def apply_data_scope(db: Session, user, flt: BlockFilter) -> BlockFilter:
    clause = resolve_scope(db, user).block_clause()
    if clause is None:
        return flt
    sql, params, needs_area = clause
    flt.extra_where.append(sql)
    flt.extra_params.update(params)
    if needs_area:
        flt.force_area_join = True
    return flt


def ensure_block_in_scope(db: Session, user, block_id: int) -> None:
    flt = apply_data_scope(db, user, BlockFilter())
    joins, where_sql, params = flt.sql()
    where = f"{where_sql} AND bl.id = :dsc_bid" if where_sql else "WHERE bl.id = :dsc_bid"
    params["dsc_bid"] = block_id
    found = db.execute(text(f"SELECT 1 FROM master.blocks bl {joins} {where}"), params).first()
    if found is None:
        raise not_found("Blok tidak termasuk wilayah yang boleh diakses.")


_FEATURE_TX = (
    ("areal_statement", "trx.area_statements"),
    ("produksi_tbs", "trx.block_productions"),
    ("rotasi_terakhir", "trx.harvest_rotations"),
)


def hidden_feature_keys(db: Session, user) -> tuple[str, ...]:
    """Key properti ringkasan transaksi di GeoJSON blok yang tidak boleh dilihat user."""
    allowed = transaction_keys(db, user)
    if allowed is None:
        return ()
    return tuple(key for key, table in _FEATURE_TX if table not in allowed)


def redact_block_detail(db: Session, user, payload: dict) -> dict:
    if transaction_keys(db, user) is None or not isinstance(payload, dict):
        return payload
    if not transaction_granted(db, user, "trx.area_statements"):
        payload["areal_statement"] = None
    if not transaction_granted(db, user, "trx.block_productions"):
        payload["produksi_tbs"] = None
    if not transaction_granted(db, user, "trx.harvest_rotations"):
        payload["rotasi_pusingan"] = None
    return payload
