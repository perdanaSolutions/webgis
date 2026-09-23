import io
import zipfile
import logging
import pandas as pd
import numpy as np
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


@router.post("/import-produksi-tbs", summary="Import Data Produksi TBS dari Excel")
async def import_produksi_tbs(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Format file harus Excel (.xlsx/.xls)")

    try:
        # 1. Read file bytes & convert format if necessary
        await file.seek(0)
        contents = await file.read()
        standardized_bytes = convert_strict_to_standard_xlsx(contents)
        buffer = io.BytesIO(standardized_bytes)

        # 2. Read with pandas
        df = pd.read_excel(buffer, engine='openpyxl')
        df = df.replace({np.nan: None})

        # Helper functions
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

        # ---------------------------------------------------------------------
        # 3. Fetch Mapping from Table `blok`
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

        # Counters
        success_count = 0
        missing_blok_count = 0
        invalid_prop_count = 0
        failed_error_count = 0
        last_error_msg = ""
        sample_unmatched = []

        # ---------------------------------------------------------------------
        # 4. Looping Insert to trx_produksi_tbs
        # ---------------------------------------------------------------------
        for index, row in df.iterrows():
            kode_blok_excel = row.get("KodeBlok") or row.get("Kode Blok") or row.get("Blok") or row.get("kode_blok")
            kode_blok_clean = clean_str(kode_blok_excel)

            if not kode_blok_clean:
                invalid_prop_count += 1
                continue

            bulan = to_int(row.get("Month") or row.get("Bulan") or row.get("bulan"), 1)
            tahun = to_int(row.get("Year") or row.get("Tahun") or row.get("tahun"), 2025)

            # 4a. Matching Level 1 (Exact) -> Level 2 (Fallback)
            fetched_blok_id = exact_map.get((kode_blok_clean, bulan, tahun)) or fallback_map.get(kode_blok_clean)

            # 4b. Skip if not found in table `blok`
            if not fetched_blok_id:
                missing_blok_count += 1
                if len(sample_unmatched) < 3:
                    sample_unmatched.append(f"Excel: '{kode_blok_clean}' (Bulan: {bulan}, Tahun: {tahun})")
                continue

            # 4c. Insert into trx_produksi_tbs using nested transaction
            nested_tx = db.begin_nested()
            try:
                db.execute(
                    text("""
                        INSERT INTO trx_produksi_tbs (
                            blok_id, tahun, bulan,
                            tbs_aktual, tbs_budget, tbs_sensus,
                            janjang_aktual, janjang_budget, janjang_sensus,
                            bjr_aktual, bjr_budget, bjr_sensus
                        ) VALUES (
                            :bid, :t, :b,
                            :tbs_aktual, :tbs_budget, :tbs_sensus,
                            :janjang_aktual, :janjang_budget, :janjang_sensus,
                            :bjr_aktual, :bjr_budget, :bjr_sensus
                        )
                    """),
                    {
                        "bid": fetched_blok_id,
                        "t": tahun,
                        "b": bulan,
                        "tbs_aktual": to_float(row.get("TbsAktual") or row.get("tbs_aktual")),
                        "tbs_budget": to_float(row.get("TbsBudget") or row.get("tbs_budget")),
                        "tbs_sensus": to_float(row.get("TbsSensus") or row.get("tbs_sensus")),
                        "janjang_aktual": to_int(row.get("JanjangAktual") or row.get("janjang_aktual")),
                        "janjang_budget": to_int(row.get("JanjangBudget") or row.get("janjang_budget")),
                        "janjang_sensus": to_int(row.get("JanjangSensus") or row.get("janjang_sensus")),
                        "bjr_aktual": to_float(row.get("BjrAktual") or row.get("bjr_aktual")),
                        "bjr_budget": to_float(row.get("BjrBudget") or row.get("bjr_budget")),
                        "bjr_sensus": to_float(row.get("BjrSensus") or row.get("bjr_sensus")),
                    }
                )

                nested_tx.commit()
                success_count += 1

            except Exception as e:
                nested_tx.rollback()
                failed_error_count += 1
                last_error_msg = str(e)
                continue

        # Final Commit
        db.commit()

        return {
            "status": "success",
            "message": "Proses impor data produksi TBS selesai.",
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