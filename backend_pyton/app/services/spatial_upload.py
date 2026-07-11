import json
from sqlalchemy.orm import Session
from shapely.geometry import shape, MultiPolygon
from geoalchemy2.shape import from_shape
from fastapi import HTTPException

from app.models.spatial import Perusahaan, Estate, Afdeling, Blok, GeoBlok

def process_geojson_upload(db: Session, geojson_content: bytes, bulan: int, tahun: int) -> int:
    try:
        geojson_data = json.loads(geojson_content)
    except Exception:
        raise HTTPException(status_code=400, detail="Format file tidak valid atau bukan JSON.")

    if geojson_data.get("type") != "FeatureCollection":
        raise HTTPException(status_code=400, detail="GeoJSON harus bertipe 'FeatureCollection'.")

    record_count = 0
    features = geojson_data.get("features", [])
    
    print(f"--- MEMULAI PARSING GEOJSON: Ditemukan {len(features)} fitur/baris data ---")

    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        if not geometry or not properties:
            print(f"[Baris {index}] Dilewati: Geometri atau properti kosong.")
            continue

        # Gunakan SAVEPOINT (begin_nested) per baris data
        # Jika baris ini error, hanya baris ini yang di-rollback, bukan seluruh session database.
        nested_tx = db.begin_nested()

        try:
            # --- 1. HANDLE DATA PERUSAHAAN (PT) ---
            nama_pt = properties.get("PT")
            if not nama_pt:
                print(f"[Baris {index}] Dilewati: Properti 'PT' tidak ditemukan.")
                nested_tx.rollback()
                continue
                
            kode_pt = nama_pt.replace(".", "").replace(" ", "_").strip().upper()

            perusahaan = db.query(Perusahaan).filter_by(kode_pt=kode_pt).first()
            if not perusahaan:
                perusahaan = Perusahaan(nama_pt=nama_pt, kode_pt=kode_pt, bulan=bulan, tahun=tahun)
                db.add(perusahaan)
                db.flush()

            # --- 2. HANDLE DATA ESTATE ---
            kode_est = properties.get("Est")
            nama_estate = properties.get("Estate")
            if not kode_est:
                print(f"[Baris {index}] Dilewati: Properti 'Est' (Kode Estate) tidak ditemukan.")
                nested_tx.rollback()
                continue
                
            est_id = f"{kode_pt}_{kode_est}"

            estate = db.query(Estate).filter_by(est_id=est_id).first()
            if not estate:
                estate = Estate(
                    est_id=est_id, 
                    pt_id=perusahaan.pt_id, 
                    nama_estate=nama_estate if nama_estate else kode_est, 
                    kode_est=kode_est, 
                    bulan=bulan, 
                    tahun=tahun
                )
                db.add(estate)
                db.flush()

            # --- 3. HANDLE DATA AFDELING ---
            kode_afd = properties.get("Afdeling")
            if not kode_afd:
                print(f"[Baris {index}] Dilewati: Properti 'Afdeling' tidak ditemukan.")
                nested_tx.rollback()
                continue
                
            afd_id = f"{est_id}_{kode_afd}"

            afdeling = db.query(Afdeling).filter_by(afd_id=afd_id).first()
            if not afdeling:
                afdeling = Afdeling(afd_id=afd_id, est_id=estate.est_id, kode_afd=kode_afd, bulan=bulan, tahun=tahun)
                db.add(afdeling)
                db.flush()

            # --- 4. HANDLE DATA BLOK (UPSERT) ---
            kode_blok = properties.get("Blok")
            if not kode_blok:
                print(f"[Baris {index}] Dilewati: Properti 'Blok' tidak ditemukan.")
                nested_tx.rollback()
                continue
                
            nama_blok = f"Blok {kode_blok}"
            global_id = f"{afd_id}_{kode_blok}"

            # Ambil data atribut opsional (kosongkan atau buat default jika tidak ada di geojson)
            tipe_blok = properties.get("TipeBlok") or properties.get("Tipe")
            jenis_topografi = properties.get("Topografi")
            jenis_tanah = properties.get("Tanah")
            jenis_bibit = properties.get("Bibit") or properties.get("Komoditas")
            
            tahun_tanam_raw = properties.get("TahunTanam") or properties.get("ThnTanam")
            tahun_tanam = int(tahun_tanam_raw) if str(tahun_tanam_raw).isdigit() else None
            status_tanam = properties.get("Status")

            blok = db.query(Blok).filter_by(global_id=global_id).first()
            if blok:
                blok.nama_blok = nama_blok
                blok.kode_blok = kode_blok
                blok.tipe_blok = tipe_blok
                blok.jenis_topografi = jenis_topografi
                blok.jenis_tanah = jenis_tanah
                blok.jenis_bibit = jenis_bibit
                blok.tahun_tanam = tahun_tanam
                blok.status_tanam = status_tanam
                blok.bulan = bulan
                blok.tahun = tahun
            else:
                blok = Blok(
                    global_id=global_id,
                    afd_id=afdeling.afd_id,
                    nama_blok=nama_blok,
                    kode_blok=kode_blok,
                    tipe_blok=tipe_blok,
                    jenis_topografi=jenis_topografi,
                    jenis_tanah=jenis_tanah,
                    jenis_bibit=jenis_bibit,
                    tahun_tanam=tahun_tanam,
                    status_tanam=status_tanam,
                    bulan=bulan,
                    tahun=tahun
                )
                db.add(blok)
            db.flush()

            # --- 5. HANDLE DATA GEOMETRY (GEO_BLOK) ---
            if not geometry or "coordinates" not in geometry or not geometry.get("coordinates"):
                print(f"[Baris {index}] Dilewati: Koordinat Geometri Kosong.")
                nested_tx.rollback()
                continue

            # BYPASS SHAPELY: Ubah dictionary geometry langsung menjadi string JSON
            from sqlalchemy import text
            geometry_json_str = json.dumps(geometry)

            # Cek apakah data GeoBlok sudah ada
            geo_blok_exists = db.query(GeoBlok).filter_by(global_id=global_id).first()

            if geo_blok_exists:
                # Update menggunakan SQL Native PostGIS
                # ST_Multi memastikan output dipaksa menjadi MultiPolygon, ST_SetSRID mengatur ke EPSG 4326
                update_geom_query = text("""
                    UPDATE geo_blok 
                    SET geom_polygon = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)),
                        bulan = :bulan,
                        tahun = :tahun
                    WHERE global_id = :global_id
                """)
                db.execute(update_geom_query, {
                    "geom_json": geometry_json_str,
                    "bulan": bulan,
                    "tahun": tahun,
                    "global_id": global_id
                })
            else:
                # Insert menggunakan SQL Native PostGIS
                insert_geom_query = text("""
                    INSERT INTO geo_blok (global_id, geom_polygon, bulan, tahun)
                    VALUES (
                        :global_id, 
                        ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)), 
                        :bulan, 
                        :tahun
                    )
                """)
                db.execute(insert_geom_query, {
                    "global_id": global_id,
                    "geom_json": geometry_json_str,
                    "bulan": bulan,
                    "tahun": tahun
                })

            db.flush()
            
            # Selesai dengan sukses untuk baris ini
            nested_tx.commit()
            record_count += 1

        except Exception as item_error:
            # Batalkan hanya baris ini saja jika menabrak error database tak terduga
            nested_tx.rollback()
            print(f"[Baris {index}] GAGAL memasukkan data. Error: {str(item_error)}")
            continue

    # Commit permanen seluruh baris yang berhasil ke database
    db.commit()
    print(f"--- SELESAI PROSES: Berhasil menyimpan {record_count} data blok ---")
    return record_count