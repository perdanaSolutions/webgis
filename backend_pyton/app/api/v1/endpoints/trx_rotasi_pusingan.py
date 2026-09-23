import io
import zipfile
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api import deps

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


@router.post("/import-rotasi-pusingan", summary="Import Data Rotasi & Pusingan dari Excel")
async def import_rotasi_pusingan(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Format file harus Excel (.xlsx/.xls)")

    try:
        # 1. Baca file bytes
        await file.seek(0)
        contents = await file.read()
        standardized_bytes = convert_strict_to_standard_xlsx(contents)
        buffer = io.BytesIO(standardized_bytes)

        # 2. Baca dataframe
        df = pd.read_excel(buffer, engine='openpyxl')
        df = df.replace({np.nan: None})

        # Helper konversi data
        def to_float(val, default=0.0):
            try:
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def to_int(val, default=0):
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

        def to_date(val):
            if val is None or pd.isna(val):
                return None
            if isinstance(val, (datetime, date)):
                return val
            try:
                return pd.to_datetime(val).date()
            except Exception:
                return None

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
            b_val = to_int(row["bulan"], None)
            t_val = to_int(row["tahun"], None)
            target_blok_id = row["blok_id"]

            if k_blok:
                fallback_map[k_blok] = target_blok_id
                if b_val is not None and t_val is not None:
                    exact_map[(k_blok, b_val, t_val)] = target_blok_id

        # Counter statistik
        success_count = 0
        missing_blok_count = 0
        invalid_prop_count = 0
        failed_error_count = 0
        last_error_msg = ""
        sample_unmatched = []

        # ---------------------------------------------------------------------
        # 4. Looping Insert ke trx_rotasi_pusingan
        # ---------------------------------------------------------------------
        for index, row in df.iterrows():
            kode_blok_excel = row.get("Blok") or row.get("KodeBlok") or row.get("Kode Blok") or row.get("kode_blok")
            kode_blok_clean = clean_str(kode_blok_excel)

            if not kode_blok_clean:
                invalid_prop_count += 1
                continue

            bulan = to_int(row.get("Bulan") or row.get("Month") or row.get("bulan"), 1)
            tahun = to_int(row.get("Periode") or row.get("Tahun") or row.get("Year") or row.get("tahun"), 2025)
            tanggal = to_date(row.get("Tanggal") or row.get("tanggal"))

            # 4a. Matching Level 1 (Exact) -> Level 2 (Fallback)
            fetched_blok_id = exact_map.get((kode_blok_clean, bulan, tahun)) or fallback_map.get(kode_blok_clean)

            # 4b. Skip jika tidak ditemukan di tabel `blok`
            if not fetched_blok_id:
                missing_blok_count += 1
                if len(sample_unmatched) < 3:
                    sample_unmatched.append(f"Excel: '{kode_blok_clean}' (Bulan: {bulan}, Tahun: {tahun})")
                continue

            # 4c. Insert ke trx_rotasi_pusingan menggunakan nested transaction
            nested_tx = db.begin_nested()
            try:
                db.execute(
                    text("""
                        INSERT INTO trx_rotasi_pusingan (
                            blok_id, tanggal, tahun, bulan, 
                            rotasi_ke, pusingan_hari, status_pusingan, 
                            luas, pokok
                        ) VALUES (
                            :bid, :tgl, :t, :b, 
                            :rotasi, :pusingan, :status_pusingan, 
                            :luas, :pokok
                        )
                    """),
                    {
                        "bid": fetched_blok_id,
                        "tgl": tanggal,
                        "t": tahun,
                        "b": bulan,
                        "rotasi": to_float(row.get("Rotasi") or row.get("rotasi_ke")),
                        "pusingan": to_int(row.get("Pusingan") or row.get("pusingan_hari")),
                        "status_pusingan": row.get("Status Pusingan") or row.get("status_pusingan"),
                        "luas": to_float(row.get("Luas") or row.get("luas")),
                        "pokok": to_float(row.get("Pokok") or row.get("pokok"))
                    }
                )

                nested_tx.commit()
                success_count += 1

            except Exception as e:
                nested_tx.rollback()
                failed_error_count += 1
                last_error_msg = str(e)
                continue

        # Commit utama
        db.commit()

        return {
            "status": "success",
            "message": "Proses impor data rotasi & pusingan selesai.",
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