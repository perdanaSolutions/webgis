import json
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

# =====================================================================
# 1. MODUL UPLOAD TPH (MASTER DATA: PT -> ESTATE -> AFDELING -> BLOK)
# =====================================================================

def analyze_geojson_tph(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 TPH: Menganalisis ringkasan data baru/lama serta menghitung 
    jumlah entitas unik (PT, Estate, Afdeling, Blok) dari GeoJSON.
    """
    try:
        geojson_data = json.loads(geojson_content)
    except Exception:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    
    total_data = len(features)
    data_baru = 0
    data_update = 0
    data_invalid = 0

    # Set untuk menampung entitas unik dari file geojson
    unique_pt = set()
    unique_estate = set()
    unique_afdeling = set()
    unique_blok = set()

    # Ambil blok_id dari DB khusus periode terpilih
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
        est_id = f"{kode_pt}_{kode_est}"
        afd_id = f"{est_id}_{kode_afd}"
        blok_id = f"{afd_id}_{kode_blok}"

        # Catat statistik unik
        unique_pt.add(kode_pt)
        unique_estate.add(est_id)
        unique_afdeling.add(afd_id)
        unique_blok.add(blok_id)

        if blok_id in existing_bloks:
            data_update += 1
        else:
            data_baru += 1

    return {
        "tipe_upload": "TPH_MASTER_DATA",
        "periode": f"{bulan}-{tahun}",
        "total_fitur": total_data,
        "data_baru_di_periode_ini": data_baru,
        "data_akan_ditimpa_di_periode_ini": data_update,
        "data_tidak_valid": data_invalid,
        "ringkasan_struktur_data": {
            "jumlah_perusahaan_pt": len(unique_pt),
            "jumlah_estate": len(unique_estate),
            "jumlah_afdeling": len(unique_afdeling),
            "jumlah_blok": len(unique_blok)
        }
    }


def execute_bulk_tph(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> int:
    """
    Tahap 2 TPH: Eksekusi pengisian master data (Mengecek eksistensi manual 
    untuk menghindari konflik Unique Constraint global).
    """
    geojson_data = json.loads(geojson_content)
    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    record_count = 0

    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not geometry or not properties:
            continue

        nested_tx = db.begin_nested()
        try:
            # =================================================================
            # 1. UPSERT PERUSAHAAN (PT)
            # =================================================================
            nama_pt = properties.get("PT")
            kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
            
            pt_row = db.execute(
                text("""
                    INSERT INTO perusahaan (nama_pt, kode_pt, bulan, tahun) 
                    VALUES (:nama, :kode, :b, :t) 
                    ON CONFLICT (kode_pt) DO UPDATE SET nama_pt = EXCLUDED.nama_pt 
                    RETURNING pt_id
                """), {"nama": nama_pt, "kode": kode_pt, "b": bulan, "t": tahun}
            ).fetchone()
            pt_id = pt_row[0]

            # =================================================================
            # 2. MANAGE ESTATE (Cek uq_estate_kode_est atau est_id)
            # =================================================================
            kode_est = properties.get("EstID") or properties.get("Estate")
            nama_estate = properties.get("Estate")
            est_id = f"{kode_pt}_{kode_est}"
            
            # Cek apakah kode_est atau est_id sudah pernah ada di database
            existing_estate = db.execute(
                text("SELECT est_id FROM estate WHERE kode_est = :kode OR est_id = :id"),
                {"kode": kode_est, "id": est_id}
            ).fetchone()

            if existing_estate:
                # Jika ada, lakukan UPDATE ke baris tersebut
                db.execute(
                    text("""
                        UPDATE estate 
                        SET nama_estate = :nama, pt_id = :pt, bulan = :b, tahun = :t
                        WHERE est_id = :target_id
                    """), {"nama": nama_estate, "pt": pt_id, "b": bulan, "t": tahun, "target_id": existing_estate[0]}
                )
                actual_est_id = existing_estate[0]
            else:
                # Jika benar-benar baru, silakan INSERT
                db.execute(
                    text("""
                        INSERT INTO estate (est_id, pt_id, nama_estate, kode_est, bulan, tahun) 
                        VALUES (:id, :pt, :nama, :kode, :b, :t)
                    """), {"id": est_id, "pt": pt_id, "nama": nama_estate, "kode": kode_est, "b": bulan, "t": tahun}
                )
                actual_est_id = est_id

            # =================================================================
            # 3. UPSERT AFDELING
            # =================================================================
            kode_afd = properties.get("Afdeling")
            afd_id = f"{actual_est_id}_{kode_afd}"
            
            db.execute(
                text("""
                    INSERT INTO afdeling (afd_id, est_id, kode_afd, bulan, tahun) 
                    VALUES (:id, :est, :kode, :b, :t) 
                    ON CONFLICT (afd_id) DO NOTHING
                """), {"id": afd_id, "est": actual_est_id, "kode": kode_afd, "b": bulan, "t": tahun}
            )

            # =================================================================
            # 4. MANAGE BLOK (Cek uq_blok_kode_blok atau blok_id)
            # =================================================================
            kode_blok = properties.get("Blok")
            blok_id = f"{afd_id}_{kode_blok}"
            
            existing_blok = db.execute(
                text("SELECT blok_id FROM blok WHERE kode_blok = :kode OR blok_id = :gid"),
                {"kode": kode_blok, "gid": blok_id}
            ).fetchone()

            if existing_blok:
                # Jika kode blok bentrok, update data blok yang sudah ada
                db.execute(
                    text("""
                        UPDATE blok 
                        SET afd_id = :aid, nama_blok = :nama, tipe_blok = :tipe, bulan = :b, tahun = :t
                        WHERE blok_id = :target_gid
                    """), {
                        "aid": afd_id, "nama": f"Blok {kode_blok}", "tipe": properties.get("Kategori"),
                        "b": bulan, "t": tahun, "target_gid": existing_blok[0]
                    }
                )
                actual_blok_id = existing_blok[0]
            else:
                # Jika blok baru, insert langsung
                db.execute(
                    text("""
                        INSERT INTO blok (blok_id, afd_id, nama_blok, kode_blok, tipe_blok, bulan, tahun) 
                        VALUES (:gid, :aid, :nama, :kode, :tipe, :b, :t)
                    """), {
                        "gid": blok_id, "aid": afd_id, "nama": f"Blok {kode_blok}", 
                        "kode": kode_blok, "tipe": properties.get("Kategori"), "b": bulan, "t": tahun
                    }
                )
                actual_blok_id = blok_id

            # =================================================================
            # 5. INSERT GEOMETRI POINT TPH (MENDUKUNG MULTI-POINT PER BLOK)
            # =================================================================
            geometry_json_str = json.dumps(geometry)
            
            # Kita biarkan id_tph terisi secara otomatis (auto-increment)
            # Langsung INSERT tanpa melakukan UPDATE berdasarkan blok_id
            db.execute(
                text("""
                    INSERT INTO geo_tph (blok_id, geom_point, kategori, bulan, tahun)
                    VALUES (:gid, ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326), :kat, :b, :t)
                """), 
                {
                    "gid": actual_blok_id, 
                    "geom_json": geometry_json_str, 
                    "kat": properties.get("Kategori"),
                    "b": bulan,
                    "t": tahun
                }
            )

            nested_tx.commit()
            record_count += 1
        except Exception as e:
            nested_tx.rollback()
            # TAMBAHKAN INI: Untuk mencetak detail error aslinya dari database
            import traceback
            print(f"--- ERROR PADA INDEKS {index} ---")
            print(f"Gid yang bermasalah: {actual_blok_id}")
            traceback.print_exc() 
            print("---------------------------------")
            continue

    db.commit()
    return record_count


# =====================================================================
# 2. MODUL UPLOAD GEOMETRI BLOK (SPATIAL ENRICHMENT: GEOM_POLYGON)
# =====================================================================

def analyze_geojson_geometry_blok(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 Geometri Blok: Menganalisis statistik polygon peta.
    """
    try:
        geojson_data = json.loads(geojson_content)
    except Exception:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    
    total_data = len(features)
    geom_baru = 0
    geom_update = 0
    blok_missing = 0 

    existing_bloks = set(r[0] for r in db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"), 
        {"b": bulan, "t": tahun}
    ).fetchall())
    
    existing_geoms = set(r[0] for r in db.execute(
        text("SELECT blok_id FROM geo_blok WHERE bulan = :b AND tahun = :t"),
        {"b": bulan, "t": tahun}
    ).fetchall())

    for feature in features:
        properties = feature.get("properties", {})
        kode_blok = properties.get("Blok")
        kode_afd = properties.get("Afdeling")
        kode_est = properties.get("Est") or properties.get("Estate")
        nama_pt = properties.get("PT")

        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            blok_missing += 1
            continue

        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        blok_id = f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"

        if blok_id not in existing_bloks:
            blok_missing += 1  
        elif blok_id in existing_geoms:
            geom_update += 1
        else:
            geom_baru += 1

    return {
        "tipe_upload": "SPATIAL_GEOMETRY_BLOK",
        "periode": f"{bulan}-{tahun}",
        "total_fitur": total_data,
        "geometri_baru_terpetakan": geom_baru,
        "geometri_diperbarui": geom_update,
        "induk_blok_belum_ada_di_periode_ini": blok_missing
    }


def execute_bulk_geometry_blok(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> int:
    """
    Tahap 2 Geometri Blok: Menyimpan polygon koordinat ke PostGIS geo_blok.
    """
    geojson_data = json.loads(geojson_content)
    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    record_count = 0

    existing_bloks = set(r[0] for r in db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"), 
        {"b": bulan, "t": tahun}
    ).fetchall())

    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not geometry or not properties:
            continue

        kode_blok = properties.get("Blok")
        kode_afd = properties.get("Afdeling")
        kode_est = properties.get("Est") or properties.get("Estate")
        nama_pt = properties.get("PT")

        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            continue

        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        blok_id = f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"

        if blok_id not in existing_bloks:
            continue

        nested_tx = db.begin_nested()
        try:
            geometry_json_str = json.dumps(geometry)
            db.execute(
                text("""
                    INSERT INTO geo_blok (blok_id, geom_polygon, bulan, tahun)
                    VALUES (:blok_id, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)), :bulan, :tahun)
                    ON CONFLICT (blok_id) DO UPDATE SET 
                        geom_polygon = EXCLUDED.geom_polygon
                """), {"blok_id": blok_id, "geom_json": geometry_json_str, "bulan": bulan, "tahun": tahun}
            )
            nested_tx.commit()
            record_count += 1
        except Exception as e:
            nested_tx.rollback()
            print(f"Gagal mengunggah geometri blok {blok_id}: {str(e)}")
            continue

    db.commit()
    return record_count

# =====================================================================
# 4. MODUL HAPUS DATA (CLEANUP UPLOAD BERDASARKAN BULAN & TAHUN)
# =====================================================================

def delete_spatial_data_by_period(db: Session, bulan: int, tahun: int) -> dict:
    """Menghapus seluruh rekaman data spasial (Geom) dan master data pada periode terpilih."""
    try:
        # Cascade manual sesuai urutan constraint database
        deleted_geo_blok = db.execute(text("DELETE FROM geo_blok WHERE bulan = :b AND tahun = :t"), {"b": bulan, "t": tahun}).rowcount
        deleted_geo_tph = db.execute(text("DELETE FROM geo_tph WHERE bulan = :b AND tahun = :t"), {"b": bulan, "t": tahun}).rowcount
        deleted_blok = db.execute(text("DELETE FROM blok WHERE bulan = :b AND tahun = :t"), {"b": bulan, "t": tahun}).rowcount
        deleted_afd = db.execute(text("DELETE FROM afdeling WHERE bulan = :b AND tahun = :t"), {"b": bounds, "t": tahun} if False else {"b": bulan, "t": tahun}).rowcount
        deleted_est = db.execute(text("DELETE FROM estate WHERE bulan = :b AND tahun = :t"), {"b": bulan, "t": tahun}).rowcount
        deleted_pt = db.execute(text("DELETE FROM perusahaan WHERE bulan = :b AND tahun = :t"), {"b": bulan, "t": tahun}).rowcount
        
        db.commit()
        return {
            "status": "success",
            "periode": f"{bulan}-{tahun}",
            "detail_terhapus": {
                "geometri_polygon_blok": deleted_geo_blok,
                "geometri_point_tph": deleted_geo_tph,
                "data_master_blok": deleted_blok,
                "data_afdeling": deleted_afd,
                "data_estate": deleted_est,
                "data_perusahaan": deleted_pt
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal membersihkan data periode: {str(e)}")

