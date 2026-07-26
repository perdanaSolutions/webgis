import io
import json
import logging
import uuid
from typing import Optional

from fastapi import HTTPException
from shapely import wkb
from shapely.geometry import shape
from shapely.errors import ShapelyError
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# =====================================================================
# MODUL UPLOAD & FETCH GEO_SAWIT (SPATIAL POINT SAWIT)
# =====================================================================
#
# CATATAN OPTIMASI TAHAP 2 (COPY + shapely):
#
# Versi sebelumnya (multi-row INSERT) sudah menekan jumlah round-trip ke DB,
# tapi tiap baris tetap memanggil fungsi SQL `ST_GeomFromGeoJSON(...)` yang
# di-parse ulang oleh planner untuk tiap statement. `COPY` tidak mendukung
# pemanggilan fungsi per baris -- ia hanya menerima nilai mentah per kolom.
# Karena itu geometry HARUS sudah dikonversi ke bentuk biner PostGIS (WKB,
# lebih tepatnya hex-encoded EWKB yang menyertakan SRID) di sisi Python
# SEBELUM dikirim. Library `shapely` dipakai untuk konversi ini:
#
#     GeoJSON dict --(shapely.geometry.shape)--> objek geometry Shapely
#                  --(shapely.wkb.dumps(hex=True, srid=4326))--> hex EWKB
#
# String hex EWKB ini bisa langsung dimuat PostGIS lewat `COPY` (format yang
# sama dipakai `pg_dump` saat mem-backup kolom geometry), atau lewat cast
# `'<hex>'::geometry` di SQL biasa untuk fallback per-baris.
#
# EFEK SAMPING YANG MENGUNTUNGKAN: karena geometry sekarang divalidasi/
# di-parse oleh shapely DI PYTHON sebelum insert, geometry yang rusak
# (misalnya koordinat tidak lengkap, ring polygon tidak tertutup, dsb.)
# akan ketahuan sebagai `data_geometri_invalid` SEBELUM menyentuh database,
# bukan baru gagal saat INSERT. Ini juga berlaku di tahap analisis
# (`analyze_geojson_sawit`), jadi pengguna sudah tahu dari Tahap 1.
#
# ALUR EKSEKUSI (Tahap 2):
#   1. Validasi semua fitur + konversi geometry ke hex EWKB, murni di Python
#      (tanpa hit DB), sekaligus memisahkan baris valid vs invalid.
#   2. Baris valid dikirim via `COPY` per CHUNK (default 5000 baris/chunk;
#      jauh lebih besar dari versi multi-row INSERT karena `COPY` streaming,
#      tidak dibatasi jumlah parameter SQL).
#   3. Kalau 1 chunk gagal (jarang -- misalnya nilai numerik di luar
#      jangkauan kolom), fallback otomatis ke INSERT satu-satu KHUSUS untuk
#      chunk itu supaya baris valid lain tetap masuk dan baris error
#      teridentifikasi.
#
# DEPENDENSI BARU: tambahkan `shapely` ke requirements.txt (`pip install shapely`).

DEFAULT_CHUNK_SIZE = 5000
SRID = 4326

INSERT_COLUMNS = "blok_id, objectid, diameter, jarak, kategori, geom_point, bulan, tahun"


def analyze_geojson_sawit(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 Sawit: Menganalisis validitas titik pohon sawit terhadap data master blok,
    SEKALIGUS memvalidasi geometry-nya lewat shapely supaya fitur dengan geometry
    rusak sudah ketahuan di tahap analisis, bukan baru gagal saat upload.
    """
    try:
        geojson_data = json.loads(geojson_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.") from exc

    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]

    total_data = len(features)
    sawit_siap_insert = 0
    induk_blok_missing = 0
    data_invalid = 0
    data_geometri_invalid = 0

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun)

    for feature in features:
        blok_id = _resolve_blok_id(feature.get("properties", {}))
        if blok_id is None:
            data_invalid += 1
            continue

        if _geometry_to_hex_ewkb(feature.get("geometry", {})) is None:
            data_geometri_invalid += 1
            continue

        if blok_id in existing_bloks:
            sawit_siap_insert += 1
        else:
            induk_blok_missing += 1

    return {
        "tipe_upload": "SPATIAL_POINT_SAWIT",
        "periode": f"{bulan}-{tahun}",
        "total_fitur_sawit": total_data,
        "sawit_siap_diunggah": sawit_siap_insert,
        "sawit_tertahan_karena_blok_belum_ada": induk_blok_missing,
        "data_properti_invalid": data_invalid,
        "data_geometri_invalid": data_geometri_invalid,
    }


def execute_bulk_sawit(
    db: Session,
    geojson_content: bytes,
    filename: str,
    bulan: int,
    tahun: int,
    user_id: str = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict:
    """
    Tahap 2 Sawit: Eksekusi pengisian titik spasial pokok sawit secara massal
    memakai PostgreSQL `COPY` (lihat catatan optimasi di atas), dengan
    validasi pencegahan data duplikat (menghapus data periode sama sebelum insert).
    """
    batch_id = str(uuid.uuid4())

    # 1. BUAT LOG AWAL (IN_PROGRESS)
    try:
        db.execute(
            text("""
                INSERT INTO sys_upload_log (
                    upload_batch_id, source_type, target_table, source_name,
                    uploaded_by, record_count, status, meta_data, started_at
                ) VALUES (
                    :batch_id, 'GEOJSON_UPLOAD', 'geo_sawit', :filename,
                    :user_id, 0, 'IN_PROGRESS', :meta, NOW()
                )
            """),
            {
                "batch_id": batch_id,
                "filename": filename,
                "user_id": user_id,
                "meta": json.dumps({"periode": f"{bulan}-{tahun}", "step": "initialization"}),
            },
        )
        db.commit()
    except Exception as log_err:
        logger.error("Gagal inisialisasi sys_upload_log: %s", log_err)

    # 2. PARSING GEOJSON
    try:
        geojson_data = json.loads(geojson_content)
        features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    except Exception as parse_err:
        db.execute(
            text("""
                UPDATE sys_upload_log
                SET status = 'FAILED', error_message = :err, finished_at = NOW()
                WHERE upload_batch_id = :batch_id
            """),
            {"err": f"Format GeoJSON rusak: {parse_err}", "batch_id": batch_id},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    total_input = len(features)

    if total_input == 0:
        detail_statistik = _empty_detail_statistik()
        _finalize_log(db, batch_id, "FAILED", "File tidak berisi fitur GeoJSON.", detail_statistik)
        return {
            "batch_id": batch_id,
            "total_fitur_sawit_diproses": 0,
            "status_proses": "FAILED",
            "detail_status": detail_statistik,
        }

    # =====================================================================
    # ANTI-DUPLIKAT PERIODE: hapus semua titik sawit periode ini sebelum insert
    # =====================================================================
    db.execute(text("DELETE FROM geo_sawit WHERE bulan = :b AND tahun = :t"), {"b": bulan, "t": tahun})

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun)

    # 3. VALIDASI SEMUA FITUR + KONVERSI GEOMETRY KE HEX EWKB (murni Python, tanpa hit DB)
    valid_rows = []
    missing_blok_count = 0
    invalid_prop_count = 0
    invalid_geom_count = 0

    for feature in features:
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        if not geometry or not properties:
            invalid_prop_count += 1
            continue

        blok_id = _resolve_blok_id(properties)
        if blok_id is None:
            invalid_prop_count += 1
            continue

        if blok_id not in existing_bloks:
            missing_blok_count += 1
            continue

        geom_hex = _geometry_to_hex_ewkb(geometry)
        if geom_hex is None:
            invalid_geom_count += 1
            continue

        valid_rows.append({
            "bid": blok_id,
            "obj_id": properties.get("OBJECTID"),
            "dia": properties.get("Diameter"),
            "jarak": properties.get("Jarak"),
            "kat": properties.get("Kategori"),
            "geom_hex": geom_hex,
            "b": bulan,
            "t": tahun,
        })

    # 4. BULK INSERT PER CHUNK PAKAI COPY
    success_count = 0
    failed_error_count = 0
    last_error_msg = None

    for chunk in _chunked(valid_rows, chunk_size):
        chunk_tx = db.begin_nested()
        try:
            _copy_insert_geo_sawit(db, chunk)
            chunk_tx.commit()
            success_count += len(chunk)
        except Exception as chunk_err:
            chunk_tx.rollback()
            logger.warning(
                "Chunk COPY gagal (%s baris), fallback ke insert satu-satu: %s",
                len(chunk), chunk_err,
            )
            # Fallback: retry satu-satu HANYA untuk chunk yang gagal, supaya
            # baris valid tetap masuk dan baris bermasalah tetap teridentifikasi.
            for row in chunk:
                row_tx = db.begin_nested()
                try:
                    db.execute(
                        text(f"""
                            INSERT INTO geo_sawit ({INSERT_COLUMNS})
                            VALUES (:bid, :obj_id, :dia, :jarak, :kat, :geom_hex::geometry, :b, :t)
                        """),
                        row,
                    )
                    row_tx.commit()
                    success_count += 1
                except Exception as row_err:
                    row_tx.rollback()
                    failed_error_count += 1
                    last_error_msg = str(row_err)
                    logger.error("Gagal insert 1 titik sawit (blok_id=%s): %s", row["bid"], row_err)

    # 5. EVALUASI STATUS AKHIR & SIMPAN LOG METADATA
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
        "total_fitur_sawit_diproses": total_input,
        "status_proses": final_status,
        "detail_status": detail_statistik,
    }


def get_geo_sawit_by_period(db: Session, bulan: int, tahun: int, blok_id: str = None) -> list:
    """
    Menampilkan data geo_sawit dalam bentuk list dictionary standar
    termasuk melakukan konversi koordinat spasial PostGIS ke format lintang/bujur JSON.

    Catatan: untuk periode dengan puluhan ribu titik, pertimbangkan menambah
    parameter page/limit di endpoint pemanggil supaya payload JSON tidak
    terlalu besar sekali kirim ke client.
    """
    query_str = """
        SELECT
            id, id_sawit, blok_id, objectid, diameter, jarak, kategori,
            ST_AsGeoJSON(geom_point) as geometry_json
        FROM geo_sawit
        WHERE bulan = :b AND tahun = :t
    """
    params = {"b": bulan, "t": tahun}

    if blok_id:
        query_str += " AND blok_id = :bid"
        params["bid"] = blok_id

    result = db.execute(text(query_str), params).fetchall()

    return [
        {
            "id": r.id,
            "id_sawit": r.id_sawit,
            "blok_id": r.blok_id,
            "objectid": r.objectid,
            "diameter": r.diameter,
            "jarak": r.jarak,
            "kategori": r.kategori,
            "geometry": json.loads(r.geometry_json) if r.geometry_json else None,
        }
        for r in result
    ]


# =====================================================================
# HELPERS INTERNAL
# =====================================================================

def _resolve_blok_id(properties: dict) -> Optional[str]:
    """Bangun blok_id dari properti feature. Mengembalikan None jika properti wajib tidak lengkap."""
    nama_pt = properties.get("PT")
    kode_est = properties.get("EstID") or properties.get("Estate")
    kode_afd = properties.get("Afdeling")
    kode_blok = properties.get("Blok")

    if not all([nama_pt, kode_est, kode_afd, kode_blok]):
        return None

    kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
    return f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"


def _geometry_to_hex_ewkb(geometry: dict) -> Optional[str]:
    """
    Konversi dict geometry GeoJSON menjadi hex EWKB (siap dimuat PostGIS lewat
    COPY atau cast `::geometry`). Mengembalikan None kalau geometry kosong
    atau tidak valid secara struktural (ditangkap shapely).
    """
    if not geometry:
        return None
    try:
        geom = shape(geometry)
        if geom.is_empty:
            return None
        return wkb.dumps(geom, hex=True, srid=SRID)
    except (ShapelyError, ValueError, TypeError) as exc:
        logger.debug("Geometry tidak valid, dilewati: %s", exc)
        return None


def _get_existing_blok_ids(db: Session, bulan: int, tahun: int) -> set:
    rows = db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun},
    ).fetchall()
    return {r[0] for r in rows}


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _escape_copy_value(val) -> str:
    """Escape 1 nilai sesuai aturan format TEXT dari PostgreSQL COPY."""
    if val is None:
        return "\\N"
    s = str(val)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _copy_insert_geo_sawit(db: Session, rows: list) -> None:
    """
    Insert `rows` (list of dict dengan key bid/obj_id/dia/jarak/kat/geom_hex/b/t)
    ke geo_sawit lewat PostgreSQL COPY -- jauh lebih cepat dari INSERT biasa
    untuk data dalam jumlah besar karena tidak ada overhead parsing SQL per baris.
    """
    if not rows:
        return

    buffer = io.StringIO()
    for row in rows:
        line = "\t".join([
            _escape_copy_value(row["bid"]),
            _escape_copy_value(row["obj_id"]),
            _escape_copy_value(row["dia"]),
            _escape_copy_value(row["jarak"]),
            _escape_copy_value(row["kat"]),
            _escape_copy_value(row["geom_hex"]),
            _escape_copy_value(row["b"]),
            _escape_copy_value(row["t"]),
        ])
        buffer.write(line + "\n")
    buffer.seek(0)

    # Ambil koneksi DBAPI mentah (psycopg2) dari session SQLAlchemy yang sedang
    # aktif, supaya COPY ikut serta dalam transaksi/SAVEPOINT yang sama dengan
    # sisa operasi di `db` (bisa di-rollback bersama kalau chunk ini gagal).
    raw_cursor = db.connection().connection.cursor()
    try:
        raw_cursor.copy_expert(
            f"COPY geo_sawit ({INSERT_COLUMNS}) FROM STDIN WITH (FORMAT text)",
            buffer,
        )
    finally:
        raw_cursor.close()


def _empty_detail_statistik() -> dict:
    return {
        "sukses_terunggah": 0,
        "tertahan_blok_missing": 0,
        "properti_invalid": 0,
        "geometri_invalid": 0,
        "sistem_error": 0,
    }


def _finalize_log(db: Session, batch_id: str, status: str, error_msg: Optional[str], detail_statistik: dict) -> None:
    meta_payload = {"detail_statistik": detail_statistik}
    try:
        db.execute(
            text("""
                UPDATE sys_upload_log
                SET record_count = :rec_count,
                    status = :status,
                    error_message = :err,
                    meta_data = :meta,
                    finished_at = NOW()
                WHERE upload_batch_id = :batch_id
            """),
            {
                "rec_count": detail_statistik.get("sukses_terunggah", 0),
                "status": status,
                "err": error_msg,
                "meta": json.dumps(meta_payload),
                "batch_id": batch_id,
            },
        )
    except Exception as log_upd_err:
        logger.error("Gagal memperbarui status sys_upload_log: %s", log_upd_err)

    db.commit()