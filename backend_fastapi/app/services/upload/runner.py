"""
Satu pintu untuk analisis (`analyze`) dan simpan (`execute`) upload GeoJSON semua jenis layer.

Dipakai endpoint sinkron lama (/spatial/.../upload-analyze|upload-execute) dan worker antrian
(audit.upload_jobs), sehingga bentuk respons keduanya sama persis. Bentuk respons memang
berbeda per jenis karena dipertahankan dari API lama dan sudah dibaca FE:

    blok     analyze: {...hasil}                 execute: {"status", "data"}
    sawit    analyze: {"status","message","data"} execute: {"status","message","detail"}
    bawaan   analyze: {"status","message","data"} execute: {"status","message","detail"}
    dinamis  analyze: {...hasil}                 execute: {"status", "data"}
"""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.services import block_upload_service
from app.services.layers import catalog_service, layer_service, sawit_service
from app.services.layers.specs import LAYER_SPECS, LayerSpec
from app.services.upload.progress import SILENT, Progress

Kind = Literal["analyze", "execute"]
ANALYZE: Kind = "analyze"
EXECUTE: Kind = "execute"
BLOK = "blok"
SAWIT = "sawit"


@dataclass(frozen=True)
class UploadInput:
    content: bytes
    filename: str | None
    bulan: int
    tahun: int
    user_id: UUID | None = None


def blok(db: Session, kind: Kind, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        return block_upload_service.analyze(db, data.content, data.bulan, data.tahun, progress)
    result = block_upload_service.execute(db, data.content, data.filename, data.bulan, data.tahun, data.user_id,
                                          progress)
    return {"status": "success", "data": result}


def sawit(db: Session, kind: Kind, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        result = sawit_service.analyze(db, data.content, data.bulan, data.tahun, progress)
        return {"status": "success", "message": "Analisis file GeoJSON sawit berhasil.", "data": result}
    stats = sawit_service.execute(db, data.content, data.filename, data.bulan, data.tahun, data.user_id, progress)
    return {"status": "success",
            "message": f"Proses bulk upload spasial sawit periode {data.bulan}-{data.tahun} selesai.", "detail": stats}


def builtin(db: Session, kind: Kind, spec: LayerSpec, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        result = layer_service.analyze(db, spec, data.content, data.bulan, data.tahun, progress)
        return {"status": "success", "message": f"Analisis file GeoJSON {spec.code} berhasil.", "data": result}
    stats = layer_service.execute(db, spec, data.content, data.filename, data.bulan, data.tahun, data.user_id,
                                  progress)
    return {"status": "success", "message": f"Proses upload spasial {spec.code} periode {data.bulan}-{data.tahun} selesai.",
            "detail": stats}


def generic(db: Session, kind: Kind, layer: dict, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        return catalog_service.analyze_generic(db, layer, data.content, data.bulan, data.tahun, progress)
    result = catalog_service.execute_generic(db, layer, data.content, data.filename, data.bulan, data.tahun,
                                             data.user_id, progress)
    return {"status": "success", "data": result}


def check_layer(db: Session, code: str) -> None:
    """Tolak kode layer yang tidak dikenal (404) sebelum job dibuat."""
    if code not in (BLOK, SAWIT) and code not in LAYER_SPECS:
        catalog_service.get_generic_layer(db, code)


def run(db: Session, kind: Kind, code: str, data: UploadInput, progress: Progress = SILENT) -> dict:
    """`code` = kode katalog (spatial.layer_types), sama dengan `value` kategori di halaman upload."""
    if code == BLOK:
        return blok(db, kind, data, progress)
    if code == SAWIT:
        return sawit(db, kind, data, progress)
    if code in LAYER_SPECS:
        return builtin(db, kind, LAYER_SPECS[code], data, progress)
    return generic(db, kind, catalog_service.get_generic_layer(db, code), data, progress)
