"""
Modul upload data spasial (TPH, Geometri Blok, dan Cleanup periode).

CATATAN REFACTOR:
1. BUG UTAMA (data area hilang, mis. "KUTIM1" hilang saat upload ke-2/ke-3):
   Query pengecekan area lama memakai `WHERE area_id = :aid OR kode_area = :kode`.
   `kode_area` diambil dari 3 huruf pertama nama area, sehingga "KUTIM1" dan
   "KUTIM2" sama-sama menghasilkan "KUT". Akibatnya salah satu area bisa
   dianggap "sudah ada" hanya karena kode_area-nya sama dengan area lain,
   padahal area_id-nya berbeda -> insert-nya di-skip.
   FIX: pengecekan "apakah sudah ada" sekarang HANYA berdasarkan area_id
   (identitas asli & deterministik), bukan kode_area. kode_area tetap
   disimpan sebagai kolom informatif, tapi tidak lagi dipakai sebagai kunci
   pencocokan sehingga tidak ada lagi collision antar-area yang beda nama
   tapi kebetulan 3 huruf awalnya sama.

2. BUG STATISTIK: sebelumnya `success_area/pt/estate/afdeling/blok` dicatat
   SEBELUM tahap-tahap berikutnya (PT/Estate/Afdeling/Blok/Geometry) selesai.
   Jika salah satu tahap gagal dan nested transaction di-rollback, statistik
   tetap melaporkan "sukses" walau datanya batal masuk DB. FIX: semua
   pencatatan sukses dipindah ke SETELAH `nested_tx.commit()` berhasil.

3. Dead code di delete_spatial_data_by_period (`{"t": towns} if False else ...`)
   dibersihkan.

4. Query `existing_bloks` (dipakai di 3 fungsi) diekstrak jadi helper
   `_get_existing_blok_ids`, begitu juga pembentukan ID hierarki
   (`_build_hierarchy_ids`) dan parsing GeoJSON (`_parse_features`).

5. `print()` diganti `logging`.

Perilaku publik (nama fungsi, parameter, bentuk dict hasil) DIPERTAHANKAN
sama seperti kode asli supaya tidak perlu mengubah router FastAPI yang
memanggilnya.
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =====================================================================
# HELPERS BERSAMA
# =====================================================================

def _parse_features(geojson_content: bytes) -> list:
    """Parse isi file GeoJSON menjadi list of features. Melempar HTTPException 400 jika format tidak valid."""
    try:
        geojson_data = json.loads(geojson_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.") from exc

    if geojson_data.get("type") == "FeatureCollection":
        return geojson_data.get("features", [])
    return [geojson_data]


def _get_existing_blok_ids(db: Session, bulan: int, tahun: int) -> set:
    """Ambil seluruh blok_id yang sudah terdaftar untuk periode (bulan, tahun) tertentu."""
    rows = db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun},
    ).fetchall()
    return {r[0] for r in rows}


def _build_hierarchy_ids(properties: dict, require_area: bool) -> Optional[dict]:
    """
    Bangun ID hierarki (area_id, kode_pt, est_id, afd_id, blok_id) dari properti feature.
    Mengembalikan None jika properti wajib tidak lengkap.
    """
    nama_pt = properties.get("PT")
    kode_est = properties.get("EstID") or properties.get("Estate") or properties.get("Est")
    kode_afd = properties.get("Afdeling")
    kode_blok = properties.get("Blok")
    nama_area = properties.get("Area")

    wajib = [nama_pt, kode_est, kode_afd, kode_blok]
    if require_area:
        wajib.append(nama_area)

    if not all(wajib):
        return None

    kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
    est_id = f"{kode_pt}_{kode_est}"
    afd_id = f"{est_id}_{kode_afd}"
    blok_id = f"{afd_id}_{kode_blok}"

    result = {
        "nama_pt": nama_pt,
        "kode_pt": kode_pt,
        "kode_est": kode_est,
        "kode_afd": kode_afd,
        "kode_blok": kode_blok,
        "est_id": est_id,
        "afd_id": afd_id,
        "blok_id": blok_id,
        "area_id": None,
        "nama_area_clean": None,
        "kode_area": None,
    }

    if nama_area:
        nama_area_clean = nama_area.strip().upper()
        result["nama_area_clean"] = nama_area_clean
        result["area_id"] = f"AR_{nama_area_clean.replace(' ', '_')}"
        # kode_area hanya untuk keperluan tampilan/referensi, TIDAK dipakai
        # sebagai kunci pencocokan "sudah ada / belum" karena beberapa nama
        # area berbeda bisa punya 3-huruf-awal yang sama (mis. KUTIM1 & KUTIM2).
        result["kode_area"] = nama_area_clean[:3]

    return result


# =====================================================================
# 1. MODUL UPLOAD TPH (PURE SPATIAL INSERTS TO GEO_TPH)
# =====================================================================

def analyze_geojson_tph(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 TPH: Memeriksa validitas titik TPH terhadap data induk blok
    yang seharusnya sudah di-upload terlebih dahulu lewat Geo_Blok.
    """
    features = _parse_features(geojson_content)

    total_data = len(features)
    tph_siap_insert = 0
    induk_blok_missing = 0
    data_invalid = 0

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun)

    for feature in features:
        ids = _build_hierarchy_ids(feature.get("properties", {}), require_area=False)
        if ids is None:
            data_invalid += 1
            continue

        if ids["blok_id"] in existing_bloks:
            tph_siap_insert += 1
        else:
            induk_blok_missing += 1

    return {
        "tipe_upload": "SPATIAL_POINT_TPH",
        "periode": f"{bulan}-{tahun}",
        "total_fitur_tph": total_data,
        "tph_siap_diunggah": tph_siap_insert,
        "tph_tertahan_karena_blok_belum_ada": induk_blok_missing,
        "data_properti_invalid": data_invalid,
    }


def execute_bulk_tph(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 2 TPH: Eksekusi pengisian titik spasial TPH secara massal dengan respons statistik spesifik.
    Menolak/skip jika blok induk tidak ditemukan untuk menjaga integritas relasi.
    """
    features = _parse_features(geojson_content)

    total_input = len(features)
    success_count = 0
    missing_blok_count = 0
    invalid_prop_count = 0
    failed_error_count = 0

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun)

    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        if not geometry or not properties:
            invalid_prop_count += 1
            continue

        ids = _build_hierarchy_ids(properties, require_area=False)
        if ids is None:
            invalid_prop_count += 1
            continue

        blok_id = ids["blok_id"]
        if blok_id not in existing_bloks:
            missing_blok_count += 1
            continue

        nested_tx = db.begin_nested()
        try:
            geometry_json_str = json.dumps(geometry)

            db.execute(
                text("""
                    INSERT INTO geo_tph (blok_id, geom_point, kategori, bulan, tahun)
                    VALUES (:bid, ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326), :kat, :b, :t)
                """),
                {
                    "bid": blok_id,
                    "geom_json": geometry_json_str,
                    "kat": properties.get("Kategori"),
                    "b": bulan,
                    "t": tahun,
                },
            )

            nested_tx.commit()
            success_count += 1
        except Exception as e:
            nested_tx.rollback()
            failed_error_count += 1
            logger.error("Gagal insert TPH indeks %s (blok_id=%s): %s", index, blok_id, e)
            continue

    db.commit()

    return {
        "total_fitur_tph_diproses": total_input,
        "detail_status": {
            "tph_berhasil_diunggah": success_count,
            "tph_tertahan_karena_blok_belum_ada": missing_blok_count,
            "data_properti_tidak_lengkap": invalid_prop_count,
            "gagal_sistem_error": failed_error_count,
        },
    }


# =====================================================================
# 2. MODUL UPLOAD GEOMETRI BLOK (MASTER DATA, AREA & SPATIAL POLYGON)
# =====================================================================

def analyze_geojson_geometry_blok(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 Geometri Blok: Menganalisis ringkasan master data baru/lama
    serta menghitung jumlah entitas unik termasuk master AREA dari GeoJSON.
    """
    features = _parse_features(geojson_content)

    total_data = len(features)
    data_baru = 0
    data_update = 0
    data_invalid = 0

    unique_area = set()
    unique_pt = set()
    unique_estate = set()
    unique_afdeling = set()
    unique_blok = set()

    existing_bloks = _get_existing_blok_ids(db, bulan, tahun)

    for feature in features:
        ids = _build_hierarchy_ids(feature.get("properties", {}), require_area=True)
        if ids is None:
            data_invalid += 1
            continue

        unique_area.add(ids["area_id"])
        unique_pt.add(ids["kode_pt"])
        unique_estate.add(ids["est_id"])
        unique_afdeling.add(ids["afd_id"])
        unique_blok.add(ids["blok_id"])

        if ids["blok_id"] in existing_bloks:
            data_update += 1
        else:
            data_baru += 1

    return {
        "tipe_upload": "GEOMETRI_BLOK_AND_MASTER_DATA",
        "periode": f"{bulan}-{tahun}",
        "total_fitur": total_data,
        "data_baru_di_periode_ini": data_baru,
        "data_akan_ditimpa_di_periode_ini": data_update,
        "data_tidak_valid": data_invalid,
        "ringkasan_struktur_data": {
            "jumlah_master_area": len(unique_area),
            "jumlah_perusahaan_pt": len(unique_pt),
            "jumlah_estate": len(unique_estate),
            "jumlah_afdeling": len(unique_afdeling),
            "jumlah_blok": len(unique_blok),
        },
    }


def execute_bulk_geometry_blok(
    db: Session, geojson_content: bytes, filename: str, bulan: int, tahun: int, user_id: str = None
) -> dict:
    """
    Tahap 2 Geometri Blok: Melakukan pendaftaran/update master data (Area, PT, Estate, Afdeling, Blok),
    menyisipkan koordinat Polygon ke tabel geo_blok, dan mencatat riwayat ke sys_upload_log.
    """
    batch_id = str(uuid.uuid4())

    # 1. INISIALISASI LOG AWAL (IN_PROGRESS)
    try:
        db.execute(
            text("""
                INSERT INTO sys_upload_log (
                    upload_batch_id, source_type, target_table, source_name,
                    uploaded_by, record_count, status, meta_data, started_at
                ) VALUES (
                    :batch_id, 'GEOJSON_UPLOAD', 'geo_blok', :filename,
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

    # 2. PARSING GEOJSON BERKAS
    try:
        features = _parse_features(geojson_content)
    except HTTPException:
        db.execute(
            text("""
                UPDATE sys_upload_log
                SET status = 'FAILED', error_message = :err, finished_at = NOW()
                WHERE upload_batch_id = :batch_id
            """),
            {"err": "Format GeoJSON rusak / bukan JSON valid.", "batch_id": batch_id},
        )
        db.commit()
        raise

    # 3. SET UNIK & COUNTER UNTUK STATISTIK
    # Catatan: set ini HANYA diisi setelah nested_tx.commit() berhasil,
    # supaya statistik selalu merepresentasikan data yang benar-benar
    # tersimpan di DB (lihat catatan bug #2 di docstring modul).
    success_area = set()
    success_pt = set()
    success_estate = set()
    success_afdeling = set()
    success_blok = set()
    success_geo_blok = 0

    failed_count = 0
    last_error_msg = None

    # 4. LOOPING PROSES DATA
    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not geometry or not properties:
            failed_count += 1
            continue

        ids = _build_hierarchy_ids(properties, require_area=True)
        if ids is None:
            failed_count += 1
            continue

        area_id = ids["area_id"]
        nama_area_clean = ids["nama_area_clean"]
        kode_area = ids["kode_area"]
        kode_pt = ids["kode_pt"]
        nama_pt = ids["nama_pt"]
        kode_est = ids["kode_est"]
        kode_afd = ids["kode_afd"]
        kode_blok = ids["kode_blok"]
        est_id = ids["est_id"]
        afd_id = ids["afd_id"]
        blok_id = ids["blok_id"]

        nested_tx = db.begin_nested()
        try:
            # =================================================================
            # A. MANAGE MASTER AREA
            # FIX: pencocokan HANYA berdasarkan area_id (identitas asli),
            # bukan lagi "area_id OR kode_area". kode_area bisa sama untuk
            # dua area yang berbeda (mis. KUTIM1 & KUTIM2 -> "KUT"), dan
            # dulu itu menyebabkan salah satu area di-skip secara keliru.
            # =================================================================
            existing_area = db.execute(
                text("""
                    SELECT id FROM area
                    WHERE area_id = :aid AND bulan = :b AND tahun = :t
                """),
                {"aid": area_id, "b": bulan, "t": tahun},
            ).fetchone()

            if existing_area:
                actual_area_pk_id = existing_area[0]
                logger.info("AREA eksis (skip insert): %s untuk periode %s-%s", area_id, bulan, tahun)
            else:
                area_row = db.execute(
                    text("""
                        INSERT INTO area (area_id, nama, kode_area, bulan, tahun)
                        VALUES (:aid, :nama, :kode, :b, :t)
                        RETURNING id
                    """),
                    {"aid": area_id, "nama": nama_area_clean, "kode": kode_area, "b": bulan, "t": tahun},
                ).fetchone()
                actual_area_pk_id = area_row[0]

            # =================================================================
            # B. MANAGE PERUSAHAAN (DENGAN RELASI AREA_ID)
            # Catatan: pengecekan ini masih GLOBAL lintas periode (tidak
            # difilter bulan/tahun), sama seperti kode asli. Ini dianggap
            # perilaku yang disengaja (PT = master data lintas periode),
            # tapi mohon dikonfirmasi -- jika ternyata harus per-periode,
            # tinggal tambahkan filter AND bulan = :b AND tahun = :t di sini.
            # =================================================================
            existing_pt = db.execute(
                text("SELECT pt_id FROM perusahaan WHERE kode_pt = :kode"),
                {"kode": kode_pt},
            ).fetchone()

            if existing_pt:
                actual_pt_id = existing_pt[0]
                db.execute(
                    text("UPDATE perusahaan SET nama_pt = :nama, area_id = :aid WHERE pt_id = :id"),
                    {"nama": nama_pt, "aid": area_id, "id": actual_pt_id},
                )
            else:
                pt_row = db.execute(
                    text("""
                        INSERT INTO perusahaan (nama_pt, kode_pt, area_id, bulan, tahun)
                        VALUES (:nama, :kode, :aid, :b, :t)
                        RETURNING pt_id
                    """),
                    {"nama": nama_pt, "kode": kode_pt, "aid": area_id, "b": bulan, "t": tahun},
                ).fetchone()
                actual_pt_id = pt_row[0]

            # =================================================================
            # C. MANAGE ESTATE
            # =================================================================
            nama_estate = properties.get("Estate") or kode_est
            existing_estate = db.execute(
                text("SELECT est_id FROM estate WHERE est_id = :id AND bulan = :b AND tahun = :t"),
                {"id": est_id, "b": bulan, "t": tahun},
            ).fetchone()

            if existing_estate:
                db.execute(
                    text("UPDATE estate SET nama_estate = :nama, pt_id = :pt WHERE est_id = :id AND bulan = :b AND tahun = :t"),
                    {"nama": nama_estate, "pt": actual_pt_id, "id": est_id, "b": bulan, "t": tahun},
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO estate (est_id, pt_id, nama_estate, kode_est, bulan, tahun)
                        VALUES (:id, :pt, :nama, :kode, :b, :t)
                    """),
                    {"id": est_id, "pt": actual_pt_id, "nama": nama_estate, "kode": kode_est, "b": bulan, "t": tahun},
                )

            # =================================================================
            # D. MANAGE AFDELING
            # =================================================================
            existing_afd = db.execute(
                text("SELECT afd_id FROM afdeling WHERE afd_id = :id AND bulan = :b AND tahun = :t"),
                {"id": afd_id, "b": bulan, "t": tahun},
            ).fetchone()

            if not existing_afd:
                db.execute(
                    text("""
                        INSERT INTO afdeling (afd_id, est_id, kode_afd, bulan, tahun)
                        VALUES (:id, :est, :kode, :b, :t)
                    """),
                    {"id": afd_id, "est": est_id, "kode": kode_afd, "b": bulan, "t": tahun},
                )

            # =================================================================
            # E. MANAGE BLOK
            # =================================================================
            existing_blok = db.execute(
                text("SELECT blok_id FROM blok WHERE blok_id = :bid AND bulan = :b AND tahun = :t"),
                {"bid": blok_id, "b": bulan, "t": tahun},
            ).fetchone()

            if existing_blok:
                db.execute(
                    text("""
                        UPDATE blok
                        SET afd_id = :aid, nama_blok = :nama, tipe_blok = :tipe
                        WHERE blok_id = :bid AND bulan = :b AND tahun = :t
                    """),
                    {
                        "aid": afd_id, "nama": f"Blok {kode_blok}", "tipe": properties.get("Kategori"),
                        "bid": blok_id, "b": bulan, "t": tahun,
                    },
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO blok (blok_id, afd_id, nama_blok, kode_blok, tipe_blok, bulan, tahun)
                        VALUES (:bid, :aid, :nama, :kode, :tipe, :b, :t)
                    """),
                    {
                        "bid": blok_id, "aid": afd_id, "nama": f"Blok {kode_blok}",
                        "kode": kode_blok, "tipe": properties.get("Kategori"), "b": bulan, "t": tahun,
                    },
                )

            # =================================================================
            # F. INSERT / UPDATE GEOMETRI POLYGON (geo_blok)
            # =================================================================
            geometry_json_str = json.dumps(geometry)
            db.execute(
                text("""
                    DELETE FROM geo_blok
                    WHERE blok_id = :blok_id AND bulan = :bulan AND tahun = :tahun
                """),
                {"blok_id": blok_id, "bulan": bulan, "tahun": tahun},
            )

            db.execute(
                text("""
                    INSERT INTO geo_blok (blok_id, geom_polygon, bulan, tahun)
                    VALUES (:blok_id, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)), :bulan, :tahun)
                """),
                {"blok_id": blok_id, "geom_json": geometry_json_str, "bulan": bulan, "tahun": tahun},
            )

            nested_tx.commit()

            # Statistik dicatat setelah commit sukses -> mencerminkan data
            # yang benar-benar tersimpan.
            success_area.add(area_id)
            success_pt.add(kode_pt)
            success_estate.add(est_id)
            success_afdeling.add(afd_id)
            success_blok.add(blok_id)
            success_geo_blok += 1

        except Exception as e:
            nested_tx.rollback()
            failed_count += 1
            last_error_msg = str(e)
            logger.error("Gagal mengunggah struktur & geometri blok %s: %s", blok_id, e)
            continue

    # 5. EVALUASI STATUS AKHIR & SIMPAN LOG METADATA
    total_input = len(features)

    if success_geo_blok == total_input and total_input > 0:
        final_status = "SUCCESS"
    elif success_geo_blok > 0 and failed_count > 0:
        final_status = "PARTIAL_SUCCESS"
    else:
        final_status = "FAILED"
        if not last_error_msg:
            last_error_msg = "Seluruh data struktur atau geometri blok gagal dimasukkan."

    meta_payload = {
        "periode_target": f"{bulan}-{tahun}",
        "detail_statistik": {
            "sukses_master_area": len(success_area),
            "sukses_master_perusahaan": len(success_pt),
            "sukses_master_estate": len(success_estate),
            "sukses_master_afdeling": len(success_afdeling),
            "sukses_master_blok": len(success_blok),
            "sukses_geometri_polygon_blok": success_geo_blok,
            "sistem_error_baris": failed_count,
        },
    }

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
                "rec_count": success_geo_blok,
                "status": final_status,
                "err": last_error_msg,
                "meta": json.dumps(meta_payload),
                "batch_id": batch_id,
            },
        )
    except Exception as log_upd_err:
        logger.error("Gagal memperbarui status sys_upload_log: %s", log_upd_err)

    db.commit()

    return {
        "batch_id": batch_id,
        "total_fitur_diproses": total_input,
        "status_proses": final_status,
        "detail_status": meta_payload["detail_statistik"],
    }


# =====================================================================
# 4. MODUL HAPUS DATA (CLEANUP UPLOAD BERDASARKAN BULAN & TAHUN)
# =====================================================================

def delete_spatial_data_by_period(db: Session, bulan: int, tahun: int) -> dict:
    """Menghapus seluruh rekaman data spasial (Geom) dan master data termasuk AREA pada periode terpilih."""
    params = {"b": bulan, "t": tahun}
    try:
        # Cascade manual sesuai urutan constraint database
        deleted_geo_blok = db.execute(text("DELETE FROM geo_blok WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_geo_tph = db.execute(text("DELETE FROM geo_tph WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_geo_jalan = db.execute(text("DELETE FROM geo_jalan WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_geo_jembatan = db.execute(text("DELETE FROM geo_jembatan WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_geo_landuse = db.execute(text("DELETE FROM geo_landuse WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_geo_sawit = db.execute(text("DELETE FROM geo_sawit WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_geo_slope = db.execute(text("DELETE FROM geo_slope WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_blok = db.execute(text("DELETE FROM blok WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_afd = db.execute(text("DELETE FROM afdeling WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_est = db.execute(text("DELETE FROM estate WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_pt = db.execute(text("DELETE FROM perusahaan WHERE bulan = :b AND tahun = :t"), params).rowcount
        deleted_area = db.execute(text("DELETE FROM area WHERE bulan = :b AND tahun = :t"), params).rowcount

        db.commit()
        return {
            "status": "success",
            "periode": f"{bulan}-{tahun}",
            "detail_terhapus": {
                "geometri_polygon_blok": deleted_geo_blok,
                "geometri_point_tph": deleted_geo_tph,
                "geo_jalan": deleted_geo_jalan,
                "geo_jembatan": deleted_geo_jembatan,
                "geo_landuse": deleted_geo_landuse,
                "geo_sawit": deleted_geo_sawit,
                "geo_slope": deleted_geo_slope,
                "data_master_blok": deleted_blok,
                "data_afdeling": deleted_afd,
                "data_estate": deleted_est,
                "data_perusahaan": deleted_pt,
                "data_master_area": deleted_area,
            },
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal membersihkan data periode: {str(e)}")