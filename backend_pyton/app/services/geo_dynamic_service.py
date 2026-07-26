"""
Service untuk sistem "jenis data geo dinamis": katalog `geo_jenis` -> tabel fisik,
di mana pembuatan jenis baru men-generate `CREATE TABLE` secara otomatis
berdasarkan skema hasil analisis sample GeoJSON.

=========================== PERINGATAN KEAMANAN ===========================
Modul ini membangun DDL (`CREATE TABLE`, `CREATE INDEX`) dan nama
tabel/kolom di SQL dari INPUT PENGGUNA (nama jenis, nama properti di
GeoJSON). Ini TIDAK BISA memakai bind parameter seperti query biasa
(Postgres tidak mengizinkan nama tabel/kolom sebagai parameter). Karena itu
SETIAP nama yang berakhir di SQL WAJIB melalui `sanitize_identifier`
(whitelist karakter ketat) dan `quote_ident` (double-quote + validasi ulang)
sebelum dipakai. Dua lapis ini adalah satu-satunya penghalang dari SQL
injection lewat jalur ini -- JANGAN pernah membangun SQL dengan f-string
langsung dari input mentah di luar dua fungsi ini.
=============================================================================

Alur:
  1. `analyze_sample_geojson`   -> deteksi tipe geometry & skema kolom dari 1 file contoh.
  2. `create_jenis`             -> user konfirmasi skema -> CREATE TABLE + simpan metadata.
  3. `analyze_generic_upload` / `execute_generic_upload`
                                 -> upload data aktual untuk jenis tsb (Tahap 1 & 2,
                                    memakai pola COPY + shapely yang sama seperti modul sawit).
  4. `get_generic_geojson` / `get_generic_list`
                                 -> tampilkan data untuk FE (peta / tabel).
"""

import io
import json
import logging
import re
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from shapely import wkb
from shapely.errors import ShapelyError
from shapely.geometry import shape
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SRID = 4326
DEFAULT_CHUNK_SIZE = 5000

DYNAMIC_TABLE_PREFIX = "geo_dyn_"
IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
FORBIDDEN_IDENTIFIER_PREFIXES = ("pg_", "sys_")

# Kolom sistem yang selalu ada di tiap tabel dinamis -- nama properti dari
# GeoJSON yang bentrok dengan ini akan otomatis diberi suffix "_attr".
RESERVED_COLUMN_NAMES = {"id", "blok_id", "bulan", "tahun", "geom", "created_at"}

GEOMETRY_TYPE_WHITELIST = {
    "POINT", "LINESTRING", "POLYGON",
    "MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON",
}

TYPE_SQL_MAP = {
    "boolean": "BOOLEAN",
    "integer": "INTEGER",
    "float": "DOUBLE PRECISION",
    "date": "DATE",
    "text": "TEXT",
}
# Urutan prioritas saat 2 tipe berbeda ditemukan untuk properti yang sama
# di sample yang berbeda-beda -> makin ke kanan makin "longgar"/aman.
TYPE_WIDENING_ORDER = ["boolean", "integer", "float", "date", "text"]

MAX_SAMPLE_FEATURES_ANALYZED = 500  # cukup untuk deteksi skema, tidak perlu baca semua fitur kalau sample besar


# =====================================================================
# 1. SANITASI IDENTIFIER (SQL-safe) -- lapisan pertahanan utama
# =====================================================================

def sanitize_identifier(raw: str, prefix: str = "") -> str:
    """
    Ubah string bebas (nama tema/jenis/kolom dari input pengguna) menjadi
    identifier SQL yang aman: huruf kecil, angka, underscore saja, diawali huruf,
    maksimal 63 karakter (limit identifier Postgres).
    """
    if not raw or not raw.strip():
        raise HTTPException(status_code=400, detail="Nama tidak boleh kosong.")

    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")

    if not s:
        raise HTTPException(status_code=400, detail=f"Nama '{raw}' tidak menghasilkan identifier valid setelah disanitasi.")

    if s[0].isdigit():
        s = f"c_{s}"

    if prefix:
        s = f"{prefix}{s}"

    s = s[:63].rstrip("_")
    if not s:
        s = f"{prefix}col" if prefix else "col"

    if not IDENTIFIER_PATTERN.match(s):
        raise HTTPException(status_code=400, detail=f"Identifier hasil sanitasi tidak valid: '{s}'.")

    if s.startswith(FORBIDDEN_IDENTIFIER_PREFIXES):
        raise HTTPException(status_code=400, detail=f"Identifier tidak boleh diawali {FORBIDDEN_IDENTIFIER_PREFIXES}.")

    return s


def quote_ident(name: str) -> str:
    """
    Double-quote identifier untuk dipakai di SQL mentah. Selalu validasi ULANG
    lewat regex sebagai lapisan kedua -- fungsi ini TIDAK BOLEH dipanggil
    dengan string yang belum lolos `sanitize_identifier`.
    """
    if not IDENTIFIER_PATTERN.match(name):
        raise HTTPException(status_code=400, detail=f"Identifier tidak aman untuk dipakai di SQL: '{name}'.")
    return f'"{name}"'


def _dedupe_columns(kolom: list) -> list:
    """Kalau 2 nama properti berbeda sanitize jadi nama_kolom yang sama, beri suffix numerik."""
    seen: dict = {}
    for k in kolom:
        base = k["nama_kolom"]
        if base not in seen:
            seen[base] = 0
        else:
            seen[base] += 1
            candidate = f"{base}_{seen[base]}"
            while any(x["nama_kolom"] == candidate for x in kolom if x is not k):
                seen[base] += 1
                candidate = f"{base}_{seen[base]}"
            k["nama_kolom"] = candidate
    return kolom


# =====================================================================
# 2. ANALISIS SAMPLE GEOJSON -> USULAN SKEMA
# =====================================================================

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _infer_value_type(value) -> str:
    if value is None:
        return "text"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        if _DATE_PATTERN.match(value.strip()):
            return "date"
        return "text"
    return "text"


def _widen_type(a: str, b: str) -> str:
    if a == b:
        return a
    if {a, b} == {"integer", "float"}:
        return "float"
    # kombinasi lain (mis. integer vs text, date vs integer) -> paling aman jadi text
    ia, ib = TYPE_WIDENING_ORDER.index(a), TYPE_WIDENING_ORDER.index(b)
    return TYPE_WIDENING_ORDER[max(ia, ib)] if {a, b} <= {"boolean", "date"} else "text"


def analyze_sample_geojson(geojson_content: bytes) -> dict:
    """
    Tahap "buat jenis baru", langkah 1: baca 1 file GeoJSON contoh, deteksi
    tipe geometry (harus tunggal & konsisten) dan usulkan skema kolom dari
    union seluruh key di `properties`. Hasil ini BELUM disimpan -- pengguna
    mengonfirmasi/mengedit dulu sebelum dikirim ke `create_jenis`.
    """
    try:
        data = json.loads(geojson_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.") from exc

    features = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]
    if not features:
        raise HTTPException(status_code=400, detail="Sample tidak berisi fitur.")

    sample = features[:MAX_SAMPLE_FEATURES_ANALYZED]

    geometry_types = set()
    column_types: dict = {}
    column_order: list = []

    for feature in sample:
        geometry = feature.get("geometry") or {}
        geom_type = geometry.get("type")
        if geom_type:
            geometry_types.add(geom_type.upper())

        for key, value in (feature.get("properties") or {}).items():
            inferred = _infer_value_type(value)
            if key not in column_types:
                column_types[key] = inferred
                column_order.append(key)
            else:
                column_types[key] = _widen_type(column_types[key], inferred)

    if not geometry_types:
        raise HTTPException(status_code=400, detail="Tidak ditemukan geometry pada sample.")
    if len(geometry_types) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Sample berisi lebih dari satu tipe geometry ({', '.join(sorted(geometry_types))}). "
                "Satu jenis data harus punya tipe geometry yang tetap/konsisten."
            ),
        )
    geometry_type = geometry_types.pop()
    if geometry_type not in GEOMETRY_TYPE_WHITELIST:
        raise HTTPException(status_code=400, detail=f"Tipe geometry '{geometry_type}' tidak didukung.")

    kolom = []
    for key in column_order:
        nama_kolom = sanitize_identifier(key)
        if nama_kolom in RESERVED_COLUMN_NAMES:
            nama_kolom = f"{nama_kolom}_attr"
        kolom.append({
            "nama_properti": key,
            "nama_kolom": nama_kolom,
            "tipe": column_types[key],
            "nullable": True,
        })
    kolom = _dedupe_columns(kolom)

    return {
        "geometry_type": geometry_type,
        "jumlah_fitur_dianalisis": len(sample),
        "jumlah_fitur_total_di_file": len(features),
        "kolom": kolom,
    }


# =====================================================================
# 3. JENIS (KATALOG + PEMBUATAN TABEL FISIK)
#    Catatan: awalnya dirancang 2 level (tema -> jenis), tapi disederhanakan
#    jadi 1 tabel karena di kasus ini "tema" dan "jenis" memang konsep yang
#    sama, bukan hierarki 1-ke-banyak yang sesungguhnya.
# =====================================================================

def create_jenis(
    db: Session,
    kode: str,
    nama: str,
    geometry_type: str,
    relasi_blok: bool,
    kolom: list,
    deskripsi: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict:
    """
    Buat jenis data baru: validasi skema, generate `CREATE TABLE` + index,
    lalu simpan metadatanya ke `geo_jenis`. Kalau insert metadata gagal
    SETELAH tabel fisik berhasil dibuat, tabel akan di-drop lagi (best-effort)
    supaya tidak ada tabel "yatim" tanpa metadata.
    """
    geometry_type = geometry_type.upper().strip()
    if geometry_type not in GEOMETRY_TYPE_WHITELIST:
        raise HTTPException(status_code=400, detail=f"Tipe geometry '{geometry_type}' tidak didukung.")

    kode_clean = sanitize_identifier(kode)
    existing_jenis = db.execute(text("SELECT id FROM geo_jenis WHERE kode = :k"), {"k": kode_clean}).fetchone()
    if existing_jenis:
        raise HTTPException(status_code=409, detail=f"Jenis dengan kode '{kode_clean}' sudah ada.")

    if not kolom:
        raise HTTPException(status_code=400, detail="Skema kolom tidak boleh kosong.")

    kolom_clean = []
    for k in kolom:
        tipe = k.get("tipe")
        if tipe not in TYPE_SQL_MAP:
            raise HTTPException(status_code=400, detail=f"Tipe kolom tidak dikenal: '{tipe}'.")
        nama_kolom = sanitize_identifier(k.get("nama_kolom") or k.get("nama_properti"))
        if nama_kolom in RESERVED_COLUMN_NAMES:
            nama_kolom = f"{nama_kolom}_attr"
        kolom_clean.append({
            "nama_properti": k.get("nama_properti", nama_kolom),
            "nama_kolom": nama_kolom,
            "tipe": tipe,
            "nullable": bool(k.get("nullable", True)),
        })
    kolom_clean = _dedupe_columns(kolom_clean)

    table_name = sanitize_identifier(kode_clean, prefix=DYNAMIC_TABLE_PREFIX)
    table_exists = db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": table_name}).scalar()
    if table_exists:
        raise HTTPException(status_code=409, detail=f"Tabel fisik '{table_name}' sudah dipakai, pilih kode jenis lain.")

    # --- Bangun DDL. Semua identifier di sini SUDAH melalui sanitize_identifier
    #     di atas, dan di-quote lagi lewat quote_ident sebagai lapis kedua. ---
    column_defs = [f"{quote_ident(k['nama_kolom'])} {TYPE_SQL_MAP[k['tipe']]}" for k in kolom_clean]

    base_columns = ["id BIGSERIAL PRIMARY KEY"]
    if relasi_blok:
        base_columns.append("blok_id TEXT")
    base_columns += ["bulan INTEGER NOT NULL", "tahun INTEGER NOT NULL"]

    all_columns = base_columns + column_defs + [f"geom GEOMETRY({geometry_type}, {SRID})"]
    ddl = f"CREATE TABLE {quote_ident(table_name)} (\n  " + ",\n  ".join(all_columns) + "\n)"

    try:
        db.execute(text(ddl))
        db.execute(text(
            f'CREATE INDEX {quote_ident(table_name + "_geom_idx")} '
            f'ON {quote_ident(table_name)} USING GIST (geom)'
        ))
        db.execute(text(
            f'CREATE INDEX {quote_ident(table_name + "_periode_idx")} '
            f'ON {quote_ident(table_name)} (bulan, tahun)'
        ))
        if relasi_blok:
            db.execute(text(
                f'CREATE INDEX {quote_ident(table_name + "_blok_idx")} '
                f'ON {quote_ident(table_name)} (blok_id)'
            ))

        row = db.execute(
            text("""
                INSERT INTO geo_jenis (kode, nama, deskripsi, table_name, geometry_type, relasi_blok, skema_kolom, status, handler_type, created_by)
                VALUES (:kode, :nama, :deskripsi, :table_name, :geom_type, :relasi_blok, :skema, 'ACTIVE', 'GENERIC', :created_by)
                RETURNING id
            """),
            {
                "kode": kode_clean, "nama": nama, "deskripsi": deskripsi, "table_name": table_name,
                "geom_type": geometry_type, "relasi_blok": relasi_blok,
                "skema": json.dumps(kolom_clean), "created_by": created_by,
            },
        ).fetchone()
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        try:
            db.execute(text(f"DROP TABLE IF EXISTS {quote_ident(table_name)}"))
            db.commit()
        except Exception as cleanup_err:
            db.rollback()
            logger.error("Gagal cleanup tabel '%s' setelah create_jenis gagal: %s", table_name, cleanup_err)
        logger.error("Gagal membuat jenis '%s': %s", kode_clean, e)
        raise HTTPException(status_code=500, detail=f"Gagal membuat jenis baru: {e}")

    return {
        "id": row[0],
        "kode": kode_clean,
        "nama": nama,
        "table_name": table_name,
        "geometry_type": geometry_type,
        "relasi_blok": relasi_blok,
        "handler_type": "GENERIC",
        "kolom": kolom_clean,
    }


REQUIRED_ENDPOINT_KEYS = {"upload_analyze", "upload_execute", "geojson"}


def register_legacy_jenis(
    db: Session,
    kode: str,
    nama: str,
    table_name: str,
    geometry_type: str,
    relasi_blok: bool,
    endpoints: dict,
    deskripsi: Optional[str] = None,
    skema_kolom: Optional[list] = None,
) -> dict:
    """
    Daftarkan jenis data yang TABEL & ENDPOINT-nya SUDAH ADA (7 jenis lama:
    blok/tph/sawit/jalan/jembatan/landuse/slope) ke katalog `geo_jenis`,
    TANPA menjalankan CREATE TABLE apa pun (handler_type='LEGACY').

    Berbeda dengan `create_jenis` (jenis dinamis, endpoint dihitung otomatis
    mengikuti pola `/geo/{kode}/...`), di sini endpoint asli-nya DISIMPAN
    APA ADANYA -- karena tiap jenis lama polanya beda-beda (mis. blok pakai
    `/blok-geometry/upload-analyze`, tph pakai `/tph/upload-analyze`).
    `GET /geo/catalog` akan mengembalikan persis nilai `endpoints` ini,
    tanpa proxy/dispatch apa pun -- FE memanggil URL itu langsung.

    `skema_kolom` di sini opsional, murni dokumentasi (ditampilkan di FE),
    tidak dipakai untuk validasi atau membangun query.
    """
    geometry_type = geometry_type.upper().strip()
    if geometry_type not in GEOMETRY_TYPE_WHITELIST:
        raise HTTPException(status_code=400, detail=f"Tipe geometry '{geometry_type}' tidak didukung.")

    missing_keys = REQUIRED_ENDPOINT_KEYS - set(endpoints or {})
    if missing_keys:
        raise HTTPException(status_code=400, detail=f"`endpoints` wajib berisi key: {sorted(missing_keys)}.")

    kode_clean = sanitize_identifier(kode)
    existing = db.execute(text("SELECT id FROM geo_jenis WHERE kode = :k"), {"k": kode_clean}).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail=f"Jenis dengan kode '{kode_clean}' sudah terdaftar.")

    # `table_name` di sini adalah nama tabel yang SUDAH ADA (bukan dibangun
    # dari input bebas seperti di create_jenis), jadi tidak lewat
    # sanitize_identifier -- tapi tetap divalidasi harus benar-benar ada
    # di database lewat to_regclass, supaya tidak ada entri metadata yang
    # menunjuk ke tabel yang tidak eksis.
    table_ok = db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": table_name}).scalar()
    if not table_ok:
        raise HTTPException(status_code=400, detail=f"Tabel '{table_name}' tidak ditemukan di database.")

    row = db.execute(
        text("""
            INSERT INTO geo_jenis (kode, nama, deskripsi, table_name, geometry_type, relasi_blok, skema_kolom, endpoints, status, handler_type)
            VALUES (:kode, :nama, :deskripsi, :table_name, :geom_type, :relasi_blok, :skema, :endpoints, 'ACTIVE', 'LEGACY')
            RETURNING id
        """),
        {
            "kode": kode_clean, "nama": nama, "deskripsi": deskripsi, "table_name": table_name,
            "geom_type": geometry_type, "relasi_blok": relasi_blok,
            "skema": json.dumps(skema_kolom or []), "endpoints": json.dumps(endpoints),
        },
    ).fetchone()
    db.commit()

    return {
        "id": row[0], "kode": kode_clean, "nama": nama, "table_name": table_name,
        "geometry_type": geometry_type, "relasi_blok": relasi_blok, "handler_type": "LEGACY",
        "endpoints": endpoints,
    }


def list_jenis(db: Session, search: Optional[str] = None) -> list:
    sql = "SELECT id, kode, nama, deskripsi, geometry_type, relasi_blok, handler_type, endpoints, status FROM geo_jenis WHERE status = 'ACTIVE'"
    params = {}
    if search:
        sql += " AND (nama ILIKE :s OR kode ILIKE :s)"
        params["s"] = f"%{search}%"
    sql += " ORDER BY nama"
    rows = db.execute(text(sql), params).fetchall()
    result = []
    for r in rows:
        endpoints = r.endpoints
        if endpoints is not None and not isinstance(endpoints, dict):
            endpoints = json.loads(endpoints)
        result.append({
            "id": r.id, "kode": r.kode, "nama": r.nama, "deskripsi": r.deskripsi,
            "geometry_type": r.geometry_type, "relasi_blok": r.relasi_blok,
            "handler_type": r.handler_type, "endpoints": endpoints,
        })
    return result


def get_jenis_or_404(db: Session, kode: str) -> dict:
    row = db.execute(
        text("""
            SELECT id, kode, nama, deskripsi, table_name, geometry_type, relasi_blok, skema_kolom, endpoints, status, handler_type
            FROM geo_jenis WHERE kode = :k
        """),
        {"k": kode},
    ).fetchone()
    if not row or row.status != "ACTIVE":
        raise HTTPException(status_code=404, detail=f"Jenis '{kode}' tidak ditemukan atau tidak aktif.")

    skema = row.skema_kolom if isinstance(row.skema_kolom, list) else json.loads(row.skema_kolom)
    endpoints = row.endpoints
    if endpoints is not None and not isinstance(endpoints, dict):
        endpoints = json.loads(endpoints)
    return {
        "id": row.id, "kode": row.kode, "nama": row.nama, "deskripsi": row.deskripsi,
        "table_name": row.table_name, "geometry_type": row.geometry_type,
        "relasi_blok": row.relasi_blok, "skema_kolom": skema, "handler_type": row.handler_type,
        "endpoints": endpoints,
    }



# =====================================================================
# 4. UPLOAD DATA GENERIK (Tahap 1 Analisis & Tahap 2 Eksekusi via COPY)
#    Pola sama seperti modul sawit (shapely -> hex EWKB -> COPY per chunk),
#    tapi diparametrisasi lewat metadata `jenis` alih-alih hardcode.
# =====================================================================

def _parse_features(geojson_content: bytes) -> list:
    try:
        data = json.loads(geojson_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.") from exc
    return data.get("features", []) if data.get("type") == "FeatureCollection" else [data]


def _resolve_blok_id(properties: dict) -> Optional[str]:
    nama_pt = properties.get("PT")
    kode_est = properties.get("EstID") or properties.get("Estate")
    kode_afd = properties.get("Afdeling")
    kode_blok = properties.get("Blok")
    if not all([nama_pt, kode_est, kode_afd, kode_blok]):
        return None
    kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
    return f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"


def _get_existing_blok_ids(db: Session, bulan: int, tahun: int) -> set:
    rows = db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun},
    ).fetchall()
    return {r[0] for r in rows}


def _geometry_to_hex_ewkb(geometry: dict, expected_type: Optional[str] = None) -> Optional[str]:
    """Konversi GeoJSON geometry -> hex EWKB, sekaligus cek kecocokan tipe kalau `expected_type` diisi."""
    if not geometry:
        return None
    try:
        geom = shape(geometry)
        if geom.is_empty:
            return None
        if expected_type and geom.geom_type.upper() != expected_type.upper():
            return None
        return wkb.dumps(geom, hex=True, srid=SRID)
    except (ShapelyError, ValueError, TypeError) as exc:
        logger.debug("Geometry tidak valid, dilewati: %s", exc)
        return None


def _cast_value(value, tipe: str):
    if value is None:
        return None
    if tipe == "boolean":
        return "t" if bool(value) else "f"
    if tipe == "date" and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _escape_copy_value(val) -> str:
    if val is None:
        return "\\N"
    s = str(val)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def analyze_generic_upload(db: Session, jenis: dict, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    features = _parse_features(geojson_content)
    total = len(features)

    siap = 0
    missing_blok = 0
    invalid_prop = 0
    invalid_geom = 0

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun) if jenis["relasi_blok"] else None

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}

        if jenis["relasi_blok"]:
            blok_id = _resolve_blok_id(properties)
            if blok_id is None:
                invalid_prop += 1
                continue
            if blok_id not in existing_bloks:
                missing_blok += 1
                continue

        if _geometry_to_hex_ewkb(geometry, expected_type=jenis["geometry_type"]) is None:
            invalid_geom += 1
            continue

        siap += 1

    return {
        "jenis": jenis["kode"],
        "periode": f"{bulan}-{tahun}",
        "total_fitur": total,
        "siap_diunggah": siap,
        "tertahan_karena_blok_belum_ada": missing_blok if jenis["relasi_blok"] else None,
        "data_properti_invalid": invalid_prop,
        "data_geometri_invalid": invalid_geom,
    }


def execute_generic_upload(
    db: Session,
    jenis: dict,
    geojson_content: bytes,
    filename: str,
    bulan: int,
    tahun: int,
    user_id: Optional[str] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict:
    table_name = jenis["table_name"]
    kolom = jenis["skema_kolom"]
    relasi_blok = jenis["relasi_blok"]

    batch_id = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO sys_upload_log (
                    upload_batch_id, source_type, target_table, source_name,
                    uploaded_by, record_count, status, meta_data, started_at
                ) VALUES (
                    :batch_id, 'GEOJSON_UPLOAD', :target_table, :filename,
                    :user_id, 0, 'IN_PROGRESS', :meta, NOW()
                )
            """),
            {
                "batch_id": batch_id, "target_table": table_name, "filename": filename, "user_id": user_id,
                "meta": json.dumps({"jenis": jenis["kode"], "periode": f"{bulan}-{tahun}", "step": "initialization"}),
            },
        )
        db.commit()
    except Exception as log_err:
        logger.error("Gagal inisialisasi sys_upload_log: %s", log_err)

    features = _parse_features(geojson_content)
    total_input = len(features)

    if total_input == 0:
        stats = {"sukses_terunggah": 0, "tertahan_blok_missing": 0, "properti_invalid": 0, "geometri_invalid": 0, "sistem_error": 0}
        _finalize_log(db, batch_id, "FAILED", "File tidak berisi fitur GeoJSON.", stats)
        return {"batch_id": batch_id, "total_fitur_diproses": 0, "status_proses": "FAILED", "detail_status": stats}

    db.execute(
        text(f"DELETE FROM {quote_ident(table_name)} WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun},
    )

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun) if relasi_blok else None

    valid_rows = []
    missing_blok_count = 0
    invalid_prop_count = 0
    invalid_geom_count = 0

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}

        if not geometry or not properties:
            invalid_prop_count += 1
            continue

        row = {"bulan": bulan, "tahun": tahun}

        if relasi_blok:
            blok_id = _resolve_blok_id(properties)
            if blok_id is None:
                invalid_prop_count += 1
                continue
            if blok_id not in existing_bloks:
                missing_blok_count += 1
                continue
            row["blok_id"] = blok_id

        geom_hex = _geometry_to_hex_ewkb(geometry, expected_type=jenis["geometry_type"])
        if geom_hex is None:
            invalid_geom_count += 1
            continue
        row["geom"] = geom_hex

        for k in kolom:
            row[k["nama_kolom"]] = _cast_value(properties.get(k["nama_properti"]), k["tipe"])

        valid_rows.append(row)

    copy_columns = (["blok_id"] if relasi_blok else []) + [k["nama_kolom"] for k in kolom] + ["geom", "bulan", "tahun"]

    success_count = 0
    failed_error_count = 0
    last_error_msg = None

    for chunk in _chunked(valid_rows, chunk_size):
        chunk_tx = db.begin_nested()
        try:
            _copy_insert_generic(db, table_name, copy_columns, chunk)
            chunk_tx.commit()
            success_count += len(chunk)
        except Exception as chunk_err:
            chunk_tx.rollback()
            logger.warning("Chunk COPY gagal untuk jenis '%s' (%s baris), fallback per-baris: %s", jenis["kode"], len(chunk), chunk_err)
            for row in chunk:
                row_tx = db.begin_nested()
                try:
                    _insert_single_generic(db, table_name, copy_columns, row)
                    row_tx.commit()
                    success_count += 1
                except Exception as row_err:
                    row_tx.rollback()
                    failed_error_count += 1
                    last_error_msg = str(row_err)
                    logger.error("Gagal insert 1 baris jenis '%s': %s", jenis["kode"], row_err)

    total_gagal = missing_blok_count + invalid_prop_count + invalid_geom_count + failed_error_count

    if success_count == total_input and total_input > 0:
        final_status = "SUCCESS"
    elif success_count > 0 and total_gagal > 0:
        final_status = "PARTIAL_SUCCESS"
        if not last_error_msg:
            last_error_msg = f"{missing_blok_count} data tertahan karena blok induk belum terdaftar."
    else:
        final_status = "FAILED"
        if not last_error_msg:
            last_error_msg = "Seluruh data gagal diinputkan."

    detail_statistik = {
        "sukses_terunggah": success_count,
        "tertahan_blok_missing": missing_blok_count,
        "properti_invalid": invalid_prop_count,
        "geometri_invalid": invalid_geom_count,
        "sistem_error": failed_error_count,
    }

    _finalize_log(db, batch_id, final_status, last_error_msg, detail_statistik)

    return {
        "batch_id": batch_id,
        "jenis": jenis["kode"],
        "total_fitur_diproses": total_input,
        "status_proses": final_status,
        "detail_status": detail_statistik,
    }


def _copy_insert_generic(db: Session, table_name: str, columns: list, rows: list) -> None:
    if not rows:
        return
    buffer = io.StringIO()
    for row in rows:
        line = "\t".join(_escape_copy_value(row.get(c)) for c in columns)
        buffer.write(line + "\n")
    buffer.seek(0)

    cols_sql = ", ".join(quote_ident(c) for c in columns)
    raw_cursor = db.connection().connection.cursor()
    try:
        raw_cursor.copy_expert(
            f"COPY {quote_ident(table_name)} ({cols_sql}) FROM STDIN WITH (FORMAT text)",
            buffer,
        )
    finally:
        raw_cursor.close()


def _insert_single_generic(db: Session, table_name: str, columns: list, row: dict) -> None:
    col_sql = ", ".join(quote_ident(c) for c in columns)
    placeholders = []
    params = {}
    for c in columns:
        placeholders.append(f":{c}::geometry" if c == "geom" else f":{c}")
        params[c] = row.get(c)
    sql = f"INSERT INTO {quote_ident(table_name)} ({col_sql}) VALUES ({', '.join(placeholders)})"
    db.execute(text(sql), params)


def _finalize_log(db: Session, batch_id: str, status: str, error_msg: Optional[str], detail_statistik: dict) -> None:
    try:
        db.execute(
            text("""
                UPDATE sys_upload_log
                SET record_count = :rec_count, status = :status, error_message = :err,
                    meta_data = :meta, finished_at = NOW()
                WHERE upload_batch_id = :batch_id
            """),
            {
                "rec_count": detail_statistik.get("sukses_terunggah", 0),
                "status": status, "err": error_msg,
                "meta": json.dumps({"detail_statistik": detail_statistik}),
                "batch_id": batch_id,
            },
        )
    except Exception as log_err:
        logger.error("Gagal memperbarui status sys_upload_log: %s", log_err)
    db.commit()


# =====================================================================
# 5. QUERY GENERIK (list & GeoJSON) UNTUK FE
# =====================================================================

def _resolve_period(db: Session, table_name: str, bulan: Optional[int], tahun: Optional[int]) -> tuple:
    """Fallback ke periode (bulan, tahun) paling terbaru di tabel kalau tidak diisi."""
    if bulan is not None and tahun is not None:
        return bulan, tahun
    row = db.execute(
        text(f"SELECT bulan, tahun FROM {quote_ident(table_name)} ORDER BY tahun DESC, bulan DESC LIMIT 1")
    ).fetchone()
    if not row:
        return bulan, tahun
    return (bulan if bulan is not None else row.bulan), (tahun if tahun is not None else row.tahun)


def get_generic_list(db: Session, jenis: dict, page: int, limit: int, bulan: Optional[int], tahun: Optional[int], blok_id: Optional[str] = None) -> dict:
    table_name = jenis["table_name"]
    kolom = jenis["skema_kolom"]
    bulan, tahun = _resolve_period(db, table_name, bulan, tahun)

    select_cols = ["id"] + (["blok_id"] if jenis["relasi_blok"] else []) + [k["nama_kolom"] for k in kolom] + ["bulan", "tahun"]
    select_sql = ", ".join(quote_ident(c) for c in select_cols)

    where_clauses = []
    params = {}
    if bulan is not None:
        where_clauses.append("bulan = :b")
        params["b"] = bulan
    if tahun is not None:
        where_clauses.append("tahun = :t")
        params["t"] = tahun
    if blok_id and jenis["relasi_blok"]:
        where_clauses.append("blok_id = :bid")
        params["bid"] = blok_id
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total = db.execute(text(f"SELECT COUNT(*) FROM {quote_ident(table_name)} {where_sql}"), params).scalar()

    offset = (page - 1) * limit
    rows = db.execute(
        text(f"SELECT {select_sql} FROM {quote_ident(table_name)} {where_sql} ORDER BY id LIMIT :limit OFFSET :offset"),
        {**params, "limit": limit, "offset": offset},
    ).fetchall()

    import math
    return {
        "total_data": total,
        "page": page,
        "limit": limit,
        "total_page": math.ceil(total / limit) if total else 1,
        "data": [dict(r._mapping) for r in rows],
    }


def get_generic_geojson(db: Session, jenis: dict, bulan: Optional[int], tahun: Optional[int], blok_id: Optional[str] = None) -> dict:
    table_name = jenis["table_name"]
    kolom = jenis["skema_kolom"]
    bulan, tahun = _resolve_period(db, table_name, bulan, tahun)

    select_cols = ["id"] + (["blok_id"] if jenis["relasi_blok"] else []) + [k["nama_kolom"] for k in kolom] + ["bulan", "tahun"]
    select_sql = ", ".join(quote_ident(c) for c in select_cols)

    where_clauses = []
    params = {}
    if bulan is not None:
        where_clauses.append("bulan = :b")
        params["b"] = bulan
    if tahun is not None:
        where_clauses.append("tahun = :t")
        params["t"] = tahun
    if blok_id and jenis["relasi_blok"]:
        where_clauses.append("blok_id = :bid")
        params["bid"] = blok_id
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"SELECT {select_sql}, ST_AsGeoJSON(geom) AS geojson_geom FROM {quote_ident(table_name)} {where_sql}"
    rows = db.execute(text(sql), params).fetchall()

    features = []
    for r in rows:
        row_dict = dict(r._mapping)
        geom_json = row_dict.pop("geojson_geom")
        if not geom_json:
            continue
        features.append({"type": "Feature", "properties": row_dict, "geometry": json.loads(geom_json)})

    return {"type": "FeatureCollection", "features": features}


def delete_generic_period(db: Session, jenis: dict, bulan: int, tahun: int) -> dict:
    table_name = jenis["table_name"]
    deleted = db.execute(
        text(f"DELETE FROM {quote_ident(table_name)} WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun},
    ).rowcount
    db.commit()
    return {"jenis": jenis["kode"], "periode": f"{bulan}-{tahun}", "data_terhapus": deleted}