import json
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

# =====================================================================
# MODUL UPLOAD & FETCH GEO_JALAN (SPATIAL MULTILINESTRING ROAD)
# =====================================================================

def analyze_geojson_jalan(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 Jalan: Menganalisis validitas fitur garis jalan terhadap master blok
    pada periode bulan & tahun terpilih sebelum eksekusi insert dilakukan.
    """
    try:
        geojson_data = json.loads(geojson_content)
    except Exception:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    
    total_data = len(features)
    jalan_siap_insert = 0
    induk_blok_missing = 0
    data_invalid = 0

    # Ambil daftar blok_id yang valid di DB untuk periode terpilih
    existing_bloks = set(r[0] for r in db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"), 
        {"b": bulan, "t": tahun}
    ).fetchall())

    for feature in features:
        properties = feature.get("properties", {})
        nama_pt = properties.get("PT")
        kode_est = properties.get("EstID") or properties.get("Estate")
        kode_afd = properties.get("Afdeling")
        kode_blok = properties.get("Blok")

        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            data_invalid += 1
            continue
            
        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        blok_id = f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"

        if blok_id in existing_bloks:
            jalan_siap_insert += 1
        else:
            induk_blok_missing += 1

    return {
        "tipe_upload": "SPATIAL_MULTILINESTRING_JALAN",
        "periode": f"{bulan}-{tahun}",
        "total_fitur_jalan": total_data,
        "jalan_siap_diunggah": jalan_siap_insert,
        "jalan_tertahan_karena_blok_belum_ada": induk_blok_missing,
        "data_properti_invalid": data_invalid
    }


def execute_bulk_jalan(db: Session, geojson_content: bytes, filename: str, bulan: int, tahun: int, user_id: str = None) -> dict:
    """
    Tahap 2 Jalan: Eksekusi pengisian jaringan garis jalan secara massal,
    dilengkapi validasi anti-duplikat periode dan penulisan ke sys_upload_log.
    """
    batch_id = str(uuid.uuid4())
    
    # 1. Inisialisasi Log Awal (IN_PROGRESS)
    try:
        db.execute(
            text("""
                INSERT INTO sys_upload_log (
                    upload_batch_id, source_type, target_table, source_name, 
                    uploaded_by, record_count, status, meta_data, started_at
                ) VALUES (
                    :batch_id, 'GEOJSON_UPLOAD', 'geo_jalan', :filename, 
                    :user_id, 0, 'IN_PROGRESS', :meta, NOW()
                )
            """),
            {
                "batch_id": batch_id,
                "filename": filename,
                "user_id": user_id,
                "meta": json.dumps({"periode": f"{bulan}-{tahun}", "step": "initialization"})
            }
        )
        db.commit()
    except Exception as log_err:
        print(f"Gagal inisialisasi sys_upload_log: {str(log_err)}")

    # 2. Parsing GeoJSON Berkas
    try:
        geojson_data = json.loads(geojson_content)
        features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    except Exception as parse_err:
        db.execute(
            text("""
                UPDATE sys_upload_log 
                SET status = 'FAILED', error_message = :err, finished_at = NOW() 
                WHERE upload_batch_id = :batch_id
            """), {"err": f"Format GeoJSON rusak: {str(parse_err)}", "batch_id": batch_id}
        )
        db.commit()
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    # 3. Pembersihan Data Lama (Anti-Duplikat Periode)
    db.execute(
        text("DELETE FROM geo_jalan WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun}
    )

    total_input = len(features)
    success_count = 0
    missing_blok_count = 0
    invalid_prop_count = 0
    failed_error_count = 0
    last_error_msg = None

    existing_bloks = set(r[0] for r in db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"), 
        {"b": bulan, "t": tahun}
    ).fetchall())

    # 4. Looping Insert Garis Jalan (MultiLineString)
    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        if not geometry or not properties:
            invalid_prop_count += 1
            continue

        nama_pt = properties.get("PT")
        kode_est = properties.get("EstID") or properties.get("Estate")
        kode_afd = properties.get("Afdeling")
        kode_blok = properties.get("Blok")

        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            invalid_prop_count += 1
            continue
            
        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        blok_id = f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"

        if blok_id not in existing_bloks:
            missing_blok_count += 1
            continue

        nested_tx = db.begin_nested()
        try:
            geometry_json_str = json.dumps(geometry)
            
            # Memasukkan data jalan menggunakan ST_Multi untuk memaksa konversi ke MultiLineString jika tipenya LineString tunggal
            db.execute(
                text("""
                    INSERT INTO geo_jalan (
                        blok_id, objectid, ownership, kategori, lebar, 
                        panjang, geom_line, bulan, tahun
                    ) VALUES (
                        :bid, :obj_id, :ownership, :kategori, :lebar, 
                        :panjang, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)), :b, :t
                    )
                """), 
                {
                    "bid": blok_id,
                    "obj_id": properties.get("OBJECTID"),
                    "ownership": properties.get("Ownership"),
                    "kategori": properties.get("Kategori"),
                    "lebar": properties.get("Lebar"),
                    "panjang": properties.get("Panjang"),
                    "geom_json": geometry_json_str,
                    "b": bulan,
                    "t": tahun
                }
            )

            nested_tx.commit()
            success_count += 1
        except Exception as e:
            nested_tx.rollback()
            failed_error_count += 1
            last_error_msg = str(e)
            continue

    # 5. Hitung Status Akhir & Update Audit Log
    total_gagal = missing_blok_count + invalid_prop_count + failed_error_count
    
    if success_count == total_input and total_input > 0:
        final_status = "SUCCESS"
    elif success_count > 0 and total_gagal > 0:
        final_status = "PARTIAL_SUCCESS"
        if not last_error_msg:
            last_error_msg = f"{missing_blok_count} data rute jalan tertahan karena blok induk belum ada."
    else:
        final_status = "FAILED"
        if not last_error_msg:
            last_error_msg = "Seluruh data jaringan jalan gagal dimasukkan."

    meta_payload = {
        "periode_target": f"{bulan}-{tahun}",
        "detail_statistik": {
            "sukses_terunggah": success_count,
            "tertahan_blok_missing": missing_blok_count,
            "properti_invalid": invalid_prop_count,
            "sistem_error": failed_error_count
        }
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
                "rec_count": success_count,
                "status": final_status,
                "err": last_error_msg,
                "meta": json.dumps(meta_payload),
                "batch_id": batch_id
            }
        )
    except Exception as log_upd_err:
        print(f"Gagal memperbarui status sys_upload_log: {str(log_upd_err)}")

    db.commit()
    
    return {
        "batch_id": batch_id,
        "total_fitur_jalan_diproses": total_input,
        "status_proses": final_status,
        "detail_status": meta_payload["detail_statistik"]
    }


def get_geo_jalan_by_period(db: Session, bulan: int, tahun: int, blok_id: str = None) -> list:
    """
    Menampilkan data geo_jalan dalam bentuk list dictionary standar 
    termasuk melakukan konversi koordinat spasial MultiLineString PostGIS ke format JSON.
    """
    query_str = """
        SELECT 
            id, id_jalan, blok_id, objectid, ownership, kategori, lebar,
            panjang, ST_AsGeoJSON(geom_line) as geometry_json
        FROM geo_jalan
        WHERE bulan = :b AND tahun = :t
    """
    params = {"b": bulan, "t": tahun}
    
    if blok_id:
        query_str += " AND blok_id = :bid"
        params["bid"] = blok_id

    result = db.execute(text(query_str), params).fetchall()
    
    list_jalan = []
    for r in result:
        list_jalan.append({
            "id": r.id,
            "id_jalan": r.id_jalan,
            "blok_id": r.blok_id,
            "objectid": r.objectid,
            "ownership": r.ownership,
            "kategori": r.kategori,
            "lebar": r.lebar,
            "panjang": r.panjang,
            "geometry": json.loads(r.geometry_json) if r.geometry_json else None
        })
        
    return list_jalan