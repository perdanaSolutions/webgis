import io
import pandas as pd
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.models.areal_statement import TrxArealStatement
# from app.models.blok import Blok
from sqlalchemy import text
import zipfile
import logging

router = APIRouter()

logger = logging.getLogger("uvicorn")

def convert_strict_to_standard_xlsx(file_bytes: bytes) -> bytes:
    try:
        input_zip = zipfile.ZipFile(io.BytesIO(file_bytes), 'r')
        output_buffer = io.BytesIO()
        with zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED) as output_zip:
            for item in input_zip.infolist():
                content = input_zip.read(item.filename)
                if item.filename.endswith('.xml') or item.filename.endswith('.rels'):
                    content = content.replace(
                        b'http://purl.oclc.org/ooxml/spreadsheetml/main',
                        b'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
                    ).replace(
                        b'http://purl.oclc.org/ooxml/officeDocument/relationships',
                        b'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
                    ).replace(
                        b'conformance="strict"',
                        b''
                    )
                output_zip.writestr(item, content)
        return output_buffer.getvalue()
    except Exception:
        return file_bytes


@router.post("/import-excel", summary="Import Data Areal Statement dari Excel")
async def import_areal_statement(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Format file harus Excel (.xlsx/.xls)")

    try:
        # 1. Baca file
        await file.seek(0)
        contents = await file.read()
        standardized_bytes = convert_strict_to_standard_xlsx(contents)
        buffer = io.BytesIO(standardized_bytes)

        # 2. Baca dengan pandas
        df = pd.read_excel(buffer, engine='openpyxl')
        df = df.replace({np.nan: None})

        # Helper konversi data tipe aman
        def to_float(val, default=0.0):
            try:
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def to_int(val, default=None):
            try:
                if val is None or pd.isna(val):
                    return default
                return int(float(val))
            except (ValueError, TypeError):
                return default

        def clean_str(val):
            if val is None or pd.isna(val):
                return ""
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            return str(val).strip().upper()

        # ---------------------------------------------------------------------
        # 3. Fetch Mapping dari Tabel `blok`
        # ---------------------------------------------------------------------
        query_result = db.execute(
            text("SELECT kode_blok, bulan, tahun, blok_id FROM blok WHERE kode_blok IS NOT NULL")
        ).mappings().all()

        exact_map = {}     # Key: (kode_blok, bulan, tahun) -> blok_id
        fallback_map = {}  # Key: kode_blok -> blok_id

        for row in query_result:
            k_blok = clean_str(row["kode_blok"])
            b_val = to_int(row["bulan"])
            t_val = to_int(row["tahun"])
            target_blok_id = row["blok_id"]

            if k_blok:
                # Simpan di fallback map (kode_blok saja)
                fallback_map[k_blok] = target_blok_id

                # Simpan di exact map jika bulan & tahun tersedia
                if b_val is not None and t_val is not None:
                    exact_map[(k_blok, b_val, t_val)] = target_blok_id

        # LOG DEBUGGING DATABASE: Cetak 3 contoh data dari DB ke terminal server
        sample_db_keys = list(exact_map.keys())[:3]
        sample_db_fallback = list(fallback_map.keys())[:3]
        logger.info(f"[DEBUG IMPORT] Sample DB Exact Map: {sample_db_keys}")
        logger.info(f"[DEBUG IMPORT] Sample DB Fallback Map (kode_blok saja): {sample_db_fallback}")

        # Counter statistik
        success_count = 0
        missing_blok_count = 0
        invalid_prop_count = 0
        failed_error_count = 0
        last_error_msg = ""
        sample_unmatched = []

        # ---------------------------------------------------------------------
        # 4. Looping Insert ke trx_areal_statement
        # ---------------------------------------------------------------------
        for index, row in df.iterrows():
            kode_blok_excel = row.get("KodeBlok") or row.get("Kode Blok") or row.get("Blok") or row.get("kode_blok")
            kode_blok_clean = clean_str(kode_blok_excel)

            if not kode_blok_clean:
                invalid_prop_count += 1
                continue

            bulan = to_int(row.get("Month") or row.get("Bulan") or row.get("bulan"), 1)
            tahun = to_int(row.get("Year") or row.get("Tahun") or row.get("tahun"), 2025)

            # 4a. PENCARIAN 2 TINGKAT:
            # Tingkat 1: Match persis (kode_blok, bulan, tahun)
            fetched_blok_id = exact_map.get((kode_blok_clean, bulan, tahun))

            # Tingkat 2 (Fallback): Cari berdasarkan kode_blok saja jika exact tidak ketemu
            if not fetched_blok_id:
                fetched_blok_id = fallback_map.get(kode_blok_clean)

            # 4b. Jika masih tidak ditemukan -> skip
            if not fetched_blok_id:
                missing_blok_count += 1
                if len(sample_unmatched) < 3:
                    sample_unmatched.append(f"Excel: '{kode_blok_clean}' (Bulan: {bulan}, Tahun: {tahun})")
                continue

            # 4c. Insert `fetched_blok_id` ke tabel trx_areal_statement
            nested_tx = db.begin_nested()
            try:
                db.execute(
                    text("""
                        INSERT INTO trx_areal_statement (
                            id_areal_statement, blok_id, bulan, tahun, luas_tanam, luas_tanah, 
                            total_pokok, sph, pct_tanah_datar, pct_berbukit, 
                            pct_gelombang, pct_curam
                        ) VALUES (
                            :atid, :bid, :b, :t, :luas_tanam, :luas_tanah,
                            :total_pokok, :sph, :pct_tanah_datar, :pct_berbukit,
                            :pct_gelombang, :pct_curam
                        )
                    """),
                    {
                        "atid": row.get("AreaCode"),
                        "bid": fetched_blok_id,
                        "b": bulan,
                        "t": tahun,
                        "luas_tanam": to_float(row.get("LuasTanam") or row.get("Luas Tanam")),
                        "luas_tanah": to_float(row.get("LuasTanah") or row.get("Luas Tanam")),
                        "total_pokok": to_int(row.get("TotalPokok") or row.get("Total Pokok")),
                        "sph": to_float(row.get("SPH")),
                        "pct_tanah_datar": to_int(row.get("TanahDatar") or row.get("Pct Datar")),
                        "pct_berbukit": to_int(row.get("Berbukit") or row.get("Pct Berbukit")),
                        "pct_gelombang": to_int(row.get("Gelombang") or row.get("Pct Gelombang")),
                        "pct_curam": to_int(row.get("Curam") or row.get("Pct Curam")),
                    }
                )

                nested_tx.commit()
                success_count += 1

            except Exception as e:
                nested_tx.rollback()
                failed_error_count += 1
                last_error_msg = str(e)
                continue

        # Commit utama di akhir
        db.commit()

        return {
            "status": "success",
            "message": "Proses impor selesai.",
            "details": {
                "success_count": success_count,
                "missing_blok_count": missing_blok_count,
                "invalid_prop_count": invalid_prop_count,
                "failed_error_count": failed_error_count,
                "sample_unmatched_excel": sample_unmatched,
                "last_error_msg": last_error_msg if failed_error_count > 0 else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memproses file: {str(e)}")