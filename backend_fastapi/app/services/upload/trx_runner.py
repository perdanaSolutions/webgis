"""Antrian upload Excel transaksi (areal statement, rotasi) — bentuk respons analyze sama dengan GeoJSON per part."""
from sqlalchemy.orm import Session

from app.services import trx_import_analysis, trx_import_service
from app.services.trx_import_service import AREA_STATEMENT, ROTATION
from app.services.upload import part_response
from app.services.upload.progress import Progress, SILENT
from app.services.upload.runner import ANALYZE, EXECUTE, Kind, UploadInput

TRX_LAYER_CODES = frozenset({"areal-statement", "rotasi-pusingan"})

_KIND_BY_CODE = {
    "areal-statement": AREA_STATEMENT,
    "rotasi-pusingan": ROTATION,
}


def is_trx_layer(code: str) -> bool:
    return code in TRX_LAYER_CODES


def run(db: Session, kind: Kind, code: str, data: UploadInput, progress: Progress = SILENT) -> dict:
    if code == "areal-statement":
        trx_kind = AREA_STATEMENT
    elif code == "rotasi-pusingan":
        trx_kind = ROTATION
    else:
        raise ValueError(f"Layer transaksi tidak dikenal: {code}")

    if kind == ANALYZE:
        progress.stage("membaca_file")
        progress.stage("validasi")
        progress.stage("menyusun_laporan")
        raw = trx_import_analysis.analyze_excel(db, trx_kind, data.filename, data.content)
        return part_response.build(
            raw,
            kategori=code,
            bulan=data.bulan,
            tahun=data.tahun,
            part=data.part_index,
            total_part=data.part_total,
            offset=data.feature_offset,
        )

    progress.stage("membaca_file")
    progress.stage("menyimpan")
    progress.stage("karantina")
    progress.stage("menyelesaikan")
    if code == "areal-statement":
        return trx_import_service.import_area_statements(db, data.filename, data.content, data.user_id)
    return trx_import_service.import_rotations(db, data.filename, data.content, data.user_id)
