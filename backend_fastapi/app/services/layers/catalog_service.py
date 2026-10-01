"""
Katalog jenis data geo (spatial.layer_types) + layer dinamis (handler GENERIC).

- LEGACY  : tabel & endpoint sudah ada (blok, tph, sawit, slope, ...). Katalog hanya
            menyimpan URL aslinya; FE memanggil URL itu langsung (prefix /spatial).
- GENERIC : dibuat lewat POST /geo/jenis -> CREATE TABLE spatial.geo_dyn_<kode>
            dengan pola kolom standar v3 (block_id, period, upload_batch_id, geom)
            + trigger audit yang sama seperti tabel spasial lain.

KEAMANAN: nama tabel/kolom dibangun dari input -> wajib lewat sanitize_identifier
dan quote_ident/quote_table (lihat app/utils/sql.py).
"""
import json
import re
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, not_found
from app.services.block_filter import BlockFilter
from app.services.map_service import resolve_period
from app.services.upload.batch import final_status, finish_batch, start_batch
from app.services.upload.copy import copy_rows
from app.services.upload.resolvers import BlockIndex, BlockMatchReport, geojson_block_keys, match_blocks
from app.utils.geojson import feature_collection, geometry_to_ewkb, make_feature, parse_features
from app.utils.pagination import page_response
from app.utils.parsing import clean_str, to_float, to_int
from app.utils.period import period_label, to_period
from app.utils.sql import quote_ident, quote_table, sanitize_identifier

DYNAMIC_PREFIX = "geo_dyn_"
GEOMETRY_TYPES = {"POINT", "LINESTRING", "POLYGON", "MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON"}
SYSTEM_COLUMNS = {"id", "block_id", "period", "upload_batch_id", "geom"}
RESERVED_PROPERTY_COLUMNS = SYSTEM_COLUMNS | {"blok_id", "bulan", "tahun", "created_at"}
TYPE_SQL = {"boolean": "BOOLEAN", "integer": "BIGINT", "float": "DOUBLE PRECISION", "date": "DATE", "text": "TEXT"}
TYPE_WIDENING = ["boolean", "integer", "float", "date", "text"]
REQUIRED_ENDPOINT_KEYS = {"upload_analyze", "upload_execute", "geojson"}
# column_schema lama (v2) memakai nama Indonesia; tabel v3 hasil migrasi memakai nama Inggris.
COLUMN_SYNONYMS = {"kategori": "category"}
MAX_SAMPLE = 500
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# =====================================================================
# KATALOG
# =====================================================================

def default_generic_endpoints(code: str) -> dict:
    return {
        "upload_analyze": f"/geo/{code}/upload-analyze",
        "upload_execute": f"/geo/{code}/upload-execute",
        "geojson": f"/geo/{code}/geojson",
        "list": f"/geo/{code}",
        "cleanup_period": f"/geo/{code}/cleanup-period",
    }


def _layer_dict(r) -> dict:
    endpoints = r["endpoints"]
    if isinstance(endpoints, str):
        endpoints = json.loads(endpoints)
    schema = r["column_schema"]
    if isinstance(schema, str):
        schema = json.loads(schema)
    return {
        "id": r["id"], "kode": r["code"], "nama": r["name"], "deskripsi": r["description"],
        "table_name": r["table_name"], "geometry_type": r["geometry_type"], "relasi_blok": r["has_block"],
        "handler_type": r["handler_type"], "skema_kolom": schema or [],
        "endpoints": endpoints or (default_generic_endpoints(r["code"]) if r["handler_type"] == "GENERIC" else None),
    }


_LAYER_COLUMNS = "id, code, name, description, table_name, geometry_type, has_block, column_schema, endpoints, handler_type"


def list_layers(db: Session, search: str | None = None) -> list[dict]:
    sql = f"SELECT {_LAYER_COLUMNS} FROM spatial.layer_types WHERE status = 'ACTIVE'"
    params = {}
    if search and search.strip():
        sql += " AND (name ILIKE :s OR code ILIKE :s)"
        params["s"] = f"%{search.strip()}%"
    return [_layer_dict(r) for r in db.execute(text(sql + " ORDER BY name"), params).mappings()]


def get_layer(db: Session, code: str) -> dict:
    row = db.execute(
        text(f"SELECT {_LAYER_COLUMNS}, status FROM spatial.layer_types WHERE code = :c"), {"c": code}
    ).mappings().first()
    if row is None or row["status"] != "ACTIVE":
        raise not_found(f"Jenis '{code}' tidak ditemukan atau tidak aktif.")
    return _layer_dict(row)


def get_generic_layer(db: Session, code: str) -> dict:
    layer = get_layer(db, code)
    if layer["handler_type"] != "GENERIC":
        raise bad_request(
            f"Jenis '{code}' adalah LEGACY; endpoint /geo/{{kode}}/... tidak berlaku. "
            "Pakai URL di field 'endpoints' dari GET /geo/catalog."
        )
    return layer


def generic_tables(db: Session) -> list[tuple[str, str]]:
    """(label, tabel) semua layer GENERIC berperiode -- dipakai cleanup periode global."""
    rows = db.execute(text("""
        SELECT lt.code, lt.table_name FROM spatial.layer_types lt
        JOIN information_schema.columns c
          ON c.table_schema || '.' || c.table_name = lt.table_name AND c.column_name = 'period'
        WHERE lt.handler_type = 'GENERIC'
    """)).all()
    return [(f"geo_{code}", table) for code, table in rows]


# =====================================================================
# ANALISIS SAMPLE & PEMBUATAN LAYER DINAMIS
# =====================================================================

def _infer_type(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str) and _DATE.match(value.strip()):
        return "date"
    return "text"


def _widen(a: str, b: str) -> str:
    if a == b:
        return a
    if {a, b} == {"integer", "float"}:
        return "float"
    return "text"


def _dedupe(columns: list[dict]) -> list[dict]:
    used: set[str] = set()
    for col in columns:
        name, n = col["nama_kolom"], 1
        while name in used:
            name = f"{col['nama_kolom']}_{n}"
            n += 1
        col["nama_kolom"] = name
        used.add(name)
    return columns


def _column_name(raw: str) -> str:
    name = sanitize_identifier(raw)
    return f"{name}_attr" if name in RESERVED_PROPERTY_COLUMNS else name


def analyze_sample(content: bytes) -> dict:
    features = parse_features(content)
    if not features:
        raise bad_request("Sample tidak berisi fitur.", field="file")
    sample = features[:MAX_SAMPLE]
    geometry_types, types, order = set(), {}, []
    for feature in sample:
        if gtype := (feature.get("geometry") or {}).get("type"):
            geometry_types.add(gtype.upper())
        for key, value in (feature.get("properties") or {}).items():
            if value is None:
                types.setdefault(key, None)
            else:
                inferred = _infer_type(value)
                types[key] = inferred if types.get(key) is None else _widen(types[key], inferred)
            if key not in order:
                order.append(key)

    if len(geometry_types) != 1:
        raise bad_request(
            "Sample harus berisi tepat satu tipe geometry." if geometry_types else "Tidak ditemukan geometry pada sample.",
            field="file",
        )
    geometry_type = geometry_types.pop()
    if geometry_type not in GEOMETRY_TYPES:
        raise bad_request(f"Tipe geometry '{geometry_type}' tidak didukung.", field="file")

    columns = _dedupe([
        {"nama_properti": key, "nama_kolom": _column_name(key), "tipe": types[key] or "text", "nullable": True}
        for key in order
    ])
    return {
        "geometry_type": geometry_type,
        "jumlah_fitur_dianalisis": len(sample),
        "jumlah_fitur_total_di_file": len(features),
        "kolom": columns,
    }


def create_layer(db: Session, *, kode: str, nama: str, deskripsi: str | None, geometry_type: str, relasi_blok: bool,
                 kolom: list[dict], created_by: str | None) -> dict:
    geometry_type = geometry_type.upper().strip()
    if geometry_type not in GEOMETRY_TYPES:
        raise bad_request(f"Tipe geometry '{geometry_type}' tidak didukung.", field="geometry_type")
    code = sanitize_identifier(kode)
    if db.execute(text("SELECT 1 FROM spatial.layer_types WHERE code = :c"), {"c": code}).first():
        raise conflict(f"Jenis dengan kode '{code}' sudah ada.", field="kode")
    if not kolom:
        raise bad_request("Skema kolom tidak boleh kosong.", field="kolom")

    columns = []
    for col in kolom:
        if col.get("tipe") not in TYPE_SQL:
            raise bad_request(f"Tipe kolom tidak dikenal: '{col.get('tipe')}'.", field="kolom")
        columns.append({
            "nama_properti": col.get("nama_properti") or col.get("nama_kolom"),
            "nama_kolom": _column_name(col.get("nama_kolom") or col.get("nama_properti")),
            "tipe": col["tipe"], "nullable": bool(col.get("nullable", True)),
        })
    columns = _dedupe(columns)

    table = sanitize_identifier(code, prefix=DYNAMIC_PREFIX)
    qualified = f"spatial.{table}"
    if db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": qualified}).scalar():
        raise conflict(f"Tabel '{qualified}' sudah dipakai, pilih kode jenis lain.", field="kode")

    q_table = quote_table(qualified)
    definitions = ["id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY"]
    if relasi_blok:
        definitions.append("block_id bigint NOT NULL REFERENCES master.blocks(id)")
    definitions += [
        "period ref.month_period NOT NULL",
        *(f"{quote_ident(c['nama_kolom'])} {TYPE_SQL[c['tipe']]}" for c in columns),
        f"geom public.geometry({geometry_type}, 4326) NOT NULL",
        "upload_batch_id uuid REFERENCES audit.upload_batches(id)",
    ]
    statements = [
        f"CREATE TABLE {q_table} (\n  " + ",\n  ".join(definitions) + "\n)",
        f"CREATE INDEX {quote_ident(table + '_geom_idx')} ON {q_table} USING gist (geom)",
        f"CREATE INDEX {quote_ident(table + '_period_idx')} ON {q_table} "
        + ("(block_id, period)" if relasi_blok else "(period)"),
        f"CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON {q_table} FOR EACH ROW EXECUTE FUNCTION audit.log_row_change()",
        f"CREATE TRIGGER audit_row_update AFTER UPDATE ON {q_table} FOR EACH ROW WHEN (old.* IS DISTINCT FROM new.*) "
        "EXECUTE FUNCTION audit.log_row_change()",
        f"CREATE TRIGGER audit_truncate AFTER TRUNCATE ON {q_table} FOR EACH STATEMENT EXECUTE FUNCTION audit.log_truncate()",
    ]
    for statement in statements:
        db.execute(text(statement))
    layer_id = db.execute(
        text("""
            INSERT INTO spatial.layer_types (code, name, description, table_name, geometry_type, has_block,
                                             column_schema, handler_type, status, created_by)
            VALUES (:code, :name, :desc, :table, :gtype, :has_block, CAST(:schema AS jsonb), 'GENERIC', 'ACTIVE', :by)
            RETURNING id
        """),
        {"code": code, "name": nama, "desc": deskripsi, "table": qualified, "gtype": geometry_type,
         "has_block": relasi_blok, "schema": json.dumps(columns), "by": created_by},
    ).scalar_one()
    db.commit()  # DDL Postgres transaksional: gagal di mana pun -> tidak ada tabel yatim
    return {"id": layer_id, "kode": code, "nama": nama, "table_name": qualified, "geometry_type": geometry_type,
            "relasi_blok": relasi_blok, "handler_type": "GENERIC", "kolom": columns,
            "endpoints": default_generic_endpoints(code)}


def register_legacy(db: Session, *, kode: str, nama: str, deskripsi: str | None, table_name: str, geometry_type: str,
                    relasi_blok: bool, endpoints: dict) -> dict:
    geometry_type = geometry_type.upper().strip()
    if geometry_type not in GEOMETRY_TYPES:
        raise bad_request(f"Tipe geometry '{geometry_type}' tidak didukung.", field="geometry_type")
    if missing := REQUIRED_ENDPOINT_KEYS - set(endpoints or {}):
        raise bad_request(f"`endpoints` wajib berisi key: {sorted(missing)}.", field="endpoints")
    code = sanitize_identifier(kode)
    if db.execute(text("SELECT 1 FROM spatial.layer_types WHERE code = :c"), {"c": code}).first():
        raise conflict(f"Jenis dengan kode '{code}' sudah terdaftar.", field="kode")
    quote_table(table_name)  # validasi format schema.tabel
    if not db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": table_name}).scalar():
        raise bad_request(f"Tabel '{table_name}' tidak ditemukan di database.", field="table_name")

    layer_id = db.execute(
        text("""
            INSERT INTO spatial.layer_types (code, name, description, table_name, geometry_type, has_block,
                                             endpoints, handler_type, status)
            VALUES (:code, :name, :desc, :table, :gtype, :has_block, CAST(:endpoints AS jsonb), 'LEGACY', 'ACTIVE')
            RETURNING id
        """),
        {"code": code, "name": nama, "desc": deskripsi, "table": table_name, "gtype": geometry_type,
         "has_block": relasi_blok, "endpoints": json.dumps(endpoints)},
    ).scalar_one()
    db.commit()
    return {"id": layer_id, "kode": code, "nama": nama, "table_name": table_name, "geometry_type": geometry_type,
            "relasi_blok": relasi_blok, "handler_type": "LEGACY", "endpoints": endpoints}


DEFAULT_LEGACY_LAYERS = [
    {"kode": "blok", "nama": "Blok Kebun", "table_name": "spatial.block_boundaries", "geometry_type": "MULTIPOLYGON",
     "relasi_blok": False, "deskripsi": "Master data & geometri polygon blok kebun.",
     "endpoints": {"upload_analyze": "/blok-geometry/upload-analyze", "upload_execute": "/blok-geometry/upload-execute",
                   "geojson": "/geojson", "list": "/blok", "cleanup_period": "/cleanup-period"}},
    *[
        {"kode": code, "nama": name, "table_name": table, "geometry_type": gtype, "relasi_blok": True, "deskripsi": name,
         "endpoints": {"upload_analyze": f"/{code}/upload-analyze", "upload_execute": f"/{code}/upload-execute",
                       "geojson": f"/{code}/geojson", "list": f"/{code}/list", "cleanup_period": f"/{code}/cleanup-period"}}
        for code, name, table, gtype in (
            ("tph", "TPH", "spatial.tph_points", "POINT"),
            ("sawit", "Pokok Sawit", "spatial.tree_censuses", "POINT"),
            ("slope", "Slope", "spatial.slope_polygons", "MULTIPOLYGON"),
            ("landuse", "Land Use", "spatial.landuse_polygons", "MULTIPOLYGON"),
            ("jalan", "Jalan", "spatial.roads", "MULTILINESTRING"),
            ("jembatan", "Jembatan", "spatial.bridges", "POINT"),
        )
    ],
]


def seed_legacy(db: Session) -> list[dict]:
    """Idempoten: jenis yang kodenya sudah ada dilewati."""
    result = []
    for item in DEFAULT_LEGACY_LAYERS:
        if db.execute(text("SELECT 1 FROM spatial.layer_types WHERE code = :c"), {"c": item["kode"]}).first():
            result.append({"kode": item["kode"], "status": "sudah_terdaftar"})
            continue
        register_legacy(db, **item)
        result.append({"kode": item["kode"], "status": "berhasil_didaftarkan"})
    return result


# =====================================================================
# UPLOAD & QUERY LAYER GENERIC
# =====================================================================

def _physical_columns(db: Session, qualified: str) -> dict[str, str]:
    schema, _, table = qualified.partition(".")
    return dict(db.execute(
        text("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = :s AND table_name = :t"),
        {"s": schema, "t": table},
    ).all())


def _attribute_columns(db: Session, layer: dict) -> list[dict]:
    """Kolom skema yang benar-benar ada di tabel (nama_kolom atau sinonimnya), beserta tipe fisiknya."""
    physical = _physical_columns(db, layer["table_name"])
    result, used = [], set()
    for col in layer["skema_kolom"]:
        name = col.get("nama_kolom")
        name = name if name in physical else COLUMN_SYNONYMS.get(name)
        if not name or name not in physical or name in SYSTEM_COLUMNS or name in used:
            continue
        used.add(name)
        result.append({"property": col.get("nama_properti") or name, "column": name, "data_type": physical[name]})
    return result


def _cast(value, data_type: str):
    if data_type in ("bigint", "integer", "smallint"):
        return to_int(value)
    if data_type in ("double precision", "real", "numeric"):
        return to_float(value)
    if data_type == "boolean":
        return None if value is None else bool(value)
    if data_type == "date":
        return value.isoformat() if isinstance(value, (date, datetime)) else clean_str(value)
    return clean_str(value) if not isinstance(value, (dict, list)) else json.dumps(value)


def _prepare(db: Session, layer: dict, content: bytes) -> dict:
    features = parse_features(content)
    columns = _attribute_columns(db, layer)
    has_block = layer["relasi_blok"]
    has_objectid = any(c["column"] == "objectid" for c in columns)
    stats = {"total": len(features), "invalid_props": 0, "invalid_geom": 0, "duplicates": 0}

    candidates: list[tuple[tuple | None, dict]] = []
    for feature in features:
        props = feature.get("properties") or {}
        keys = geojson_block_keys(props) if has_block else None
        if has_block and keys is None:
            stats["invalid_props"] += 1
            continue
        geom = geometry_to_ewkb(feature.get("geometry"), layer["geometry_type"])
        if geom is None:
            stats["invalid_geom"] += 1
            continue
        row = {"geom": geom, **{col["column"]: _cast(props.get(col["property"]), col["data_type"]) for col in columns}}
        candidates.append((keys, row))

    match = BlockMatchReport()
    if has_block:
        block_ids, match = match_blocks(db, BlockIndex.load(db), [(k, r["geom"]) for k, r in candidates])
        for (_, row), block_id in zip(candidates, block_ids):
            row["block_id"] = block_id

    rows, by_objectid = [], {}
    for _, row in candidates:
        if has_block and row["block_id"] is None:
            continue
        if has_objectid and row.get("objectid") is not None:
            stats["duplicates"] += row["objectid"] in by_objectid
            by_objectid[row["objectid"]] = row
        else:
            rows.append(row)
    rows.extend(by_objectid.values())
    stats["missing_block"] = match.missing
    return {"rows": rows, "columns": columns, "stats": stats, "has_objectid": has_objectid, "match": match}


def analyze_generic(db: Session, layer: dict, content: bytes, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    prepared = _prepare(db, layer, content)
    s = prepared["stats"]
    return {
        "jenis": layer["kode"], "periode": period_label(period), "total_fitur": s["total"],
        "siap_diunggah": len(prepared["rows"]),
        "tertahan_karena_blok_belum_ada": s["missing_block"] if layer["relasi_blok"] else None,
        "data_properti_invalid": s["invalid_props"], "data_geometri_invalid": s["invalid_geom"],
        "duplikat_objectid_dalam_file": s["duplicates"],
        **prepared["match"].as_dict(),
        "contoh_blok_tidak_ditemukan": prepared["match"].unmatched_samples,
        "kolom_tersimpan": [c["column"] for c in prepared["columns"]],
    }


def execute_generic(db: Session, layer: dict, content: bytes, filename: str | None, bulan: int, tahun: int,
                    user_id: UUID | None) -> dict:
    period = to_period(bulan, tahun)
    q_table = quote_table(layer["table_name"])
    batch_id = start_batch(db, source_type="GEOJSON_UPLOAD", target_table=layer["table_name"], source_name=filename,
                           user_id=user_id, period=period, metadata={"layer": layer["kode"]})
    try:
        prepared = _prepare(db, layer, content)
        rows, stats = prepared["rows"], prepared["stats"]
        replaced = 0
        if rows:
            clauses, params = [], {"p": period}
            if layer["relasi_blok"]:
                clauses.append("block_id = ANY(:blocks)")
                params["blocks"] = sorted({r["block_id"] for r in rows})
            if prepared["has_objectid"]:
                clauses.append("objectid = ANY(:oids)")
                params["oids"] = sorted({r["objectid"] for r in rows if r.get("objectid") is not None})
            condition = f" AND ({' OR '.join(clauses)})" if clauses else ""
            replaced = db.execute(text(f"DELETE FROM {q_table} WHERE period = :p{condition}"), params).rowcount
            attr = [c["column"] for c in prepared["columns"]]
            columns = (["block_id"] if layer["relasi_blok"] else []) + ["period", *attr, "geom", "upload_batch_id"]
            copy_rows(db, q_table, columns, (
                [*([r["block_id"]] if layer["relasi_blok"] else []), period, *(r.get(c) for c in attr), r["geom"], batch_id]
                for r in rows
            ))
        db.commit()
    except Exception as exc:
        db.rollback()
        finish_batch(db, batch_id, "FAILED", 0, str(exc)[:2000], {"layer": layer["kode"]})
        raise

    success = len(rows)
    status = final_status(success, stats["total"])
    detail = {
        "sukses_terunggah": success, "tertahan_blok_missing": stats["missing_block"],
        "properti_invalid": stats["invalid_props"], "geometri_invalid": stats["invalid_geom"],
        "duplikat_dalam_file": stats["duplicates"], "data_lama_diganti": replaced,
        **prepared["match"].as_dict(), "sistem_error": 0,
    }
    finish_batch(db, batch_id, status, success,
                 None if status == "SUCCESS" else f"{stats['total'] - success} fitur tidak diunggah.", {"detail_statistik": detail})
    return {"batch_id": str(batch_id), "jenis": layer["kode"], "total_fitur_diproses": stats["total"],
            "status_proses": status, "detail_status": detail}


def _select(db: Session, layer: dict) -> tuple[str, list[str]]:
    attr = [c["column"] for c in _attribute_columns(db, layer)]
    cols = ["t.id", *(["t.block_id AS blok_id"] if layer["relasi_blok"] else []), *(f"t.{quote_ident(c)}" for c in attr)]
    return ", ".join(cols), attr


def _where(layer: dict, period: date | None, blok: str | None) -> tuple[str, str, dict]:
    joins, clauses, params = "", [], {}
    if period:
        clauses.append("t.period = :p")
        params["p"] = period
    if blok and layer["relasi_blok"]:
        b_joins, b_where, b_params = BlockFilter(blok=blok).sql()
        joins = f"JOIN master.blocks bl ON bl.id = t.block_id {b_joins}"
        clauses.append(b_where.removeprefix("WHERE "))
        params.update(b_params)
    return joins, ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def generic_list(db: Session, layer: dict, page: int, limit: int, bulan: int | None, tahun: int | None,
                 blok: str | None) -> dict:
    q_table = quote_table(layer["table_name"])
    period = resolve_period(db, q_table, bulan, tahun)
    select_sql, _ = _select(db, layer)
    joins, where_sql, params = _where(layer, period, blok)
    base = f"FROM {q_table} t {joins} {where_sql}"
    total = db.execute(text(f"SELECT count(*) {base}"), params).scalar_one()
    rows = db.execute(
        text(f"SELECT {select_sql}, t.period {base} ORDER BY t.id LIMIT :limit OFFSET :offset"),
        {**params, "limit": limit, "offset": (page - 1) * limit},
    ).mappings()
    data = [{**{k: v for k, v in r.items() if k != "period"}, "bulan": r["period"].month, "tahun": r["period"].year}
            for r in rows]
    return page_response(total, page, limit, data)


def generic_geojson(db: Session, layer: dict, bulan: int | None, tahun: int | None, blok: str | None):
    q_table = quote_table(layer["table_name"])
    period = resolve_period(db, q_table, bulan, tahun)
    if period is None:
        return feature_collection([])
    select_sql, _ = _select(db, layer)
    joins, where_sql, params = _where(layer, period, blok)
    rows = db.execute(
        text(f"SELECT {select_sql}, ST_AsGeoJSON(t.geom, 6) AS geojson_geom FROM {q_table} t {joins} {where_sql} ORDER BY t.id"),
        params,
    ).mappings()
    features = []
    for r in rows:
        properties = {k: v for k, v in r.items() if k != "geojson_geom"}
        properties.update({"bulan": period.month, "tahun": period.year})
        if feature := make_feature(properties, r["geojson_geom"]):
            features.append(feature)
    return feature_collection(features)


def generic_cleanup(db: Session, layer: dict, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    deleted = db.execute(
        text(f"DELETE FROM {quote_table(layer['table_name'])} WHERE period = :p"), {"p": period}
    ).rowcount
    db.commit()
    return {"jenis": layer["kode"], "periode": period_label(period), "data_terhapus": deleted}
