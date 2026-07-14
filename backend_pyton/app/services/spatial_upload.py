import json
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

# =====================================================================
# 1. MODUL UPLOAD TPH (PURE SPATIAL INSERTS TO GEO_TPH)
# =====================================================================

def analyze_geojson_tph(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 TPH: Memeriksa validitas titik TPH terhadap data induk blok 
    yang seharusnya sudah di-upload terlebih dahulu lewat Geo_Blok.
    """
    try:
        geojson_data = json.loads(geojson_content)
    except Exception:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    
    total_data = len(features)
    tph_siap_insert = 0
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

        # Validasi kelengkapan properti pembentuk blok_id
        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            data_invalid += 1
            continue
            
        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        blok_id = f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"

        # TPH hanya bisa masuk jika blok induknya sudah di-upload via geo_blok
        if blok_id in existing_bloks:
            tph_siap_insert += 1
        else:
            induk_blok_missing += 1

    return {
        "tipe_upload": "SPATIAL_POINT_TPH",
        "periode": f"{bulan}-{tahun}",
        "total_fitur_tph": total_data,
        "tph_siap_diunggah": tph_siap_insert,
        "tph_tertahan_karena_blok_belum_ada": induk_blok_missing,
        "data_properti_invalid": data_invalid
    }


def execute_bulk_tph(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 2 TPH: Eksekusi pengisian titik spasial TPH secara massal dengan respons statistik spesifik.
    Menolak/skip jika blok induk tidak ditemukan untuk menjaga integritas relasi.
    """
    geojson_data = json.loads(geojson_content)
    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    
    # Inisialisasi counter statistik spesifik
    total_input = len(features)
    success_count = 0
    missing_blok_count = 0
    invalid_prop_count = 0
    failed_error_count = 0

    # Ambil daftar induk blok yang valid di DB untuk periode terpilih
    existing_bloks = set(r[0] for r in db.execute(
        text("SELECT blok_id FROM blok WHERE bulan = :b AND tahun = :t"), 
        {"b": bulan, "t": tahun}
    ).fetchall())

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

        # Validasi kelengkapan data properti
        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            invalid_prop_count += 1
            continue
            
        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        blok_id = f"{kode_pt}_{kode_est}_{kode_afd}_{kode_blok}"

        # Cek apakah blok induk sudah tersedia di DB pada periode ini
        if blok_id not in existing_bloks:
            missing_blok_count += 1
            continue

        nested_tx = db.begin_nested()
        try:
            geometry_json_str = json.dumps(geometry)
            
            # Eksekusi penyimpanan koordinat point TPH
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
                    "t": tahun
                }
            )

            nested_tx.commit()
            success_count += 1
        except Exception as e:
            nested_tx.rollback()
            failed_error_count += 1
            print(f"--- ERROR INSERT TPH INDEKS {index} ---")
            print(f"Blok ID bermasalah: {blok_id}, Detail: {str(e)}")
            continue

    db.commit()
    
    # Mengembalikan dictionary berisi detail hasil pemrosesan data
    return {
        "total_fitur_tph_diproses": total_input,
        "detail_status": {
            "tph_berhasil_diunggah": success_count,
            "tph_tertahan_karena_blok_belum_ada": missing_blok_count,
            "data_properti_tidak_lengkap": invalid_prop_count,
            "gagal_sistem_error": failed_error_count
        }
    }


# =====================================================================
# 2. MODUL UPLOAD GEOMETRI BLOK (MASTER DATA & SPATIAL POLYGON)
# =====================================================================

def analyze_geojson_geometry_blok(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 1 Geometri Blok: Menganalisis ringkasan master data baru/lama 
    serta menghitung jumlah entitas unik (PT, Estate, Afdeling, Blok) dari GeoJSON.
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
        kode_est = properties.get("EstID") or properties.get("Estate") or properties.get("Est")
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
        "tipe_upload": "GEOMETRI_BLOK_AND_MASTER_DATA",
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


def execute_bulk_geometry_blok(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> dict:
    """
    Tahap 2 Geometri Blok: Melakukan pendaftaran/update master data (PT, Estate, Afdeling, Blok) 
    sekaligus menyisipkan data koordinat spasial Polygon ke tabel geo_blok.
    """
    geojson_data = json.loads(geojson_content)
    features = geojson_data.get("features", []) if geojson_data.get("type") == "FeatureCollection" else [geojson_data]
    
    # Set unik untuk melacak data yang BERHASIL diinput/di-update
    success_pt = set()
    success_estate = set()
    success_afdeling = set()
    success_blok = set()
    success_geo_blok = 0
    
    # Counter untuk mencatat data yang GAGAL karena exception
    failed_count = 0

    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not geometry or not properties:
            failed_count += 1
            continue

        nama_pt = properties.get("PT")
        kode_est = properties.get("EstID") or properties.get("Estate") or properties.get("Est")
        kode_afd = properties.get("Afdeling")
        kode_blok = properties.get("Blok")

        if not all([nama_pt, kode_est, kode_afd, kode_blok]):
            failed_count += 1
            continue

        kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()
        est_id = f"{kode_pt}_{kode_est}"
        afd_id = f"{est_id}_{kode_afd}"
        blok_id = f"{afd_id}_{kode_blok}"

        nested_tx = db.begin_nested()
        try:
            # =================================================================
            # 1. MANAGE PERUSAHAAN
            # =================================================================
            existing_pt = db.execute(
                text("SELECT pt_id FROM perusahaan WHERE kode_pt = :kode"),
                {"kode": kode_pt}
            ).fetchone()

            if existing_pt:
                actual_pt_id = existing_pt[0]
                db.execute(
                    text("UPDATE perusahaan SET nama_pt = :nama WHERE pt_id = :id"),
                    {"nama": nama_pt, "id": actual_pt_id}
                )
            else:
                pt_row = db.execute(
                    text("""
                        INSERT INTO perusahaan (nama_pt, kode_pt, bulan, tahun) 
                        VALUES (:nama, :kode, :b, :t) 
                        RETURNING pt_id
                    """), {"nama": nama_pt, "kode": kode_pt, "b": bulan, "t": tahun}
                ).fetchone()
                actual_pt_id = pt_row[0]
            
            success_pt.add(kode_pt)

            # =================================================================
            # 2. MANAGE ESTATE
            # =================================================================
            nama_estate = properties.get("Estate") or kode_est
            
            existing_estate = db.execute(
                text("SELECT est_id FROM estate WHERE est_id = :id AND bulan = :b AND tahun = :t"),
                {"id": est_id, "b": bulan, "t": tahun}
            ).fetchone()

            if existing_estate:
                db.execute(
                    text("UPDATE estate SET nama_estate = :nama, pt_id = :pt WHERE est_id = :id AND bulan = :b AND tahun = :t"),
                    {"nama": nama_estate, "pt": actual_pt_id, "id": est_id, "b": bulan, "t": tahun}
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO estate (est_id, pt_id, nama_estate, kode_est, bulan, tahun) 
                        VALUES (:id, :pt, :nama, :kode, :b, :t)
                    """), {"id": est_id, "pt": actual_pt_id, "nama": nama_estate, "kode": kode_est, "b": bulan, "t": tahun}
                )
            
            success_estate.add(est_id)

            # =================================================================
            # 3. MANAGE AFDELING
            # =================================================================
            existing_afd = db.execute(
                text("SELECT afd_id FROM afdeling WHERE afd_id = :id AND bulan = :b AND tahun = :t"),
                {"id": afd_id, "b": bulan, "t": tahun}
            ).fetchone()

            if not existing_afd:
                db.execute(
                    text("""
                        INSERT INTO afdeling (afd_id, est_id, kode_afd, bulan, tahun) 
                        VALUES (:id, :est, :kode, :b, :t)
                    """), {"id": afd_id, "est": est_id, "kode": kode_afd, "b": bulan, "t": tahun}
                )
            
            success_afdeling.add(afd_id)

            # =================================================================
            # 4. MANAGE BLOK
            # =================================================================
            existing_blok = db.execute(
                text("SELECT blok_id FROM blok WHERE blok_id = :bid AND bulan = :b AND tahun = :t"),
                {"bid": blok_id, "b": bulan, "t": tahun}
            ).fetchone()

            if existing_blok:
                db.execute(
                    text("""
                        UPDATE blok 
                        SET afd_id = :aid, nama_blok = :nama, tipe_blok = :tipe
                        WHERE blok_id = :bid AND bulan = :b AND tahun = :t
                    """), {
                        "aid": afd_id, "nama": f"Blok {kode_blok}", "tipe": properties.get("Kategori"),
                        "bid": blok_id, "b": bulan, "t": tahun
                    }
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO blok (blok_id, afd_id, nama_blok, kode_blok, tipe_blok, bulan, tahun) 
                        VALUES (:bid, :aid, :nama, :kode, :tipe, :b, :t)
                    """), {
                        "bid": blok_id, "aid": afd_id, "nama": f"Blok {kode_blok}",
                        "kode": kode_blok, "tipe": properties.get("Kategori"), "b": bulan, "t": tahun
                    }
                )
            
            success_blok.add(blok_id)

            # =================================================================
            # 5. INSERT / UPDATE GEOMETRI POLYGON (geo_blok)
            # =================================================================
            geometry_json_str = json.dumps(geometry)
            
            db.execute(
                text("""
                    DELETE FROM geo_blok 
                    WHERE blok_id = :blok_id AND bulan = :bulan AND tahun = :tahun
                """), {"blok_id": blok_id, "bulan": bulan, "tahun": tahun}
            )

            db.execute(
                text("""
                    INSERT INTO geo_blok (blok_id, geom_polygon, bulan, tahun)
                    VALUES (:blok_id, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)), :bulan, :tahun)
                """), {"blok_id": blok_id, "geom_json": geometry_json_str, "bulan": bulan, "tahun": tahun}
            )

            nested_tx.commit()
            success_geo_blok += 1

        except Exception as e:
            nested_tx.rollback()
            failed_count += 1
            print(f"Gagal mengunggah struktur & geometri blok {blok_id}: {str(e)}")
            continue

    db.commit()
    
    # Kembalikan dictionary statistik lengkap
    return {
        "total_fitur_diproses": len(features),
        "jumlah_sukses": {
            "perusahaan_pt": len(success_pt),
            "estate": len(success_estate),
            "afdeling": len(success_afdeling),
            "blok": len(success_blok),
            "geometri_polygon_blok": success_geo_blok
        },
        "jumlah_gagal": failed_count
    }

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

