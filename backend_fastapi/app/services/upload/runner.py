"""
Satu pintu untuk analisis (`analyze`) dan simpan (`execute`) upload GeoJSON semua jenis layer.

Dipakai endpoint sinkron lama (/spatial/.../upload-analyze|upload-execute) dan worker antrian
(audit.upload_jobs), sehingga bentuk respons keduanya sama persis. Bentuk respons memang
sama untuk semua jenis pada analyze (lihat part_response), sedangkan execute dipertahankan dari API lama:

    semua    analyze: {"kategori","bulan","tahun","part","total_part","data":{table_preview,analisa_aman,analisa_gagal,ringkasan}}
    blok     execute: {"status", "data"}
    sawit    execute: {"status","message","detail"}
    bawaan   execute: {"status","message","detail"}
    dinamis  execute: {"status", "data"}
"""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.services import block_upload_service
from app.services.layers import catalog_service, layer_service, sawit_service
from app.services.layers.specs import LAYER_SPECS, LayerSpec
from app.services.upload import context as part_context
from app.services.upload import part_response
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
    part_index: int = 1
    part_total: int = 1
    feature_offset: int = 0  # jumlah feature sebelum part ini di file asli
    protected_batch_ids: tuple[str, ...] = ()  # batch simpan part lain dari grup upload yang sama

    def context(self) -> part_context.PartContext:
        return part_context.PartContext(self.feature_offset, self.part_index, self.part_total,
                                        tuple(self.protected_batch_ids))


def _wrap(code: str, data: UploadInput, result: dict) -> dict:
    return part_response.build(result, kategori=code, bulan=data.bulan, tahun=data.tahun, part=data.part_index,
                               total_part=data.part_total, offset=data.feature_offset)


def blok(db: Session, kind: Kind, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        return _wrap(BLOK, data, block_upload_service.analyze(db, data.content, data.bulan, data.tahun, progress))
    with part_context.use(data.context()):
        result = block_upload_service.execute(db, data.content, data.filename, data.bulan, data.tahun, data.user_id,
                                              progress)
    return {"status": "success", "data": result}


def sawit(db: Session, kind: Kind, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        return _wrap(SAWIT, data, sawit_service.analyze(db, data.content, data.bulan, data.tahun, progress))
    with part_context.use(data.context()):
        stats = sawit_service.execute(db, data.content, data.filename, data.bulan, data.tahun, data.user_id, progress)
    return {"status": "success",
            "message": f"Proses bulk upload spasial sawit periode {data.bulan}-{data.tahun} selesai.", "detail": stats}


def builtin(db: Session, kind: Kind, spec: LayerSpec, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        return _wrap(spec.code, data, layer_service.analyze(db, spec, data.content, data.bulan, data.tahun, progress))
    with part_context.use(data.context()):
        stats = layer_service.execute(db, spec, data.content, data.filename, data.bulan, data.tahun, data.user_id,
                                      progress)
    return {"status": "success", "message": f"Proses upload spasial {spec.code} periode {data.bulan}-{data.tahun} selesai.",
            "detail": stats}


def generic(db: Session, kind: Kind, layer: dict, data: UploadInput, progress: Progress = SILENT) -> dict:
    if kind == ANALYZE:
        return _wrap(layer["kode"], data,
                     catalog_service.analyze_generic(db, layer, data.content, data.bulan, data.tahun, progress))
    with part_context.use(data.context()):
        result = catalog_service.execute_generic(db, layer, data.content, data.filename, data.bulan, data.tahun,
                                                 data.user_id, progress)
    return {"status": "success", "data": result}


def check_layer(db: Session, code: str) -> None:
    """Tolak kode layer yang tidak dikenal (404) sebelum job dibuat."""
    from app.services.upload import trx_runner  # lazy: trx_runner mengimpor modul ini (circular)

    if trx_runner.is_trx_layer(code):
        return
    if code not in (BLOK, SAWIT) and code not in LAYER_SPECS:
        catalog_service.get_generic_layer(db, code)


def run(db: Session, kind: Kind, code: str, data: UploadInput, progress: Progress = SILENT) -> dict:
    """`code` = kode katalog (spatial.layer_types), sama dengan `value` kategori di halaman upload."""
    from app.services.upload import trx_runner  # lazy: trx_runner mengimpor modul ini (circular)

    if trx_runner.is_trx_layer(code):
        return trx_runner.run(db, kind, code, data, progress)
    if code == BLOK:
        return blok(db, kind, data, progress)
    if code == SAWIT:
        return sawit(db, kind, data, progress)
    if code in LAYER_SPECS:
        return builtin(db, kind, LAYER_SPECS[code], data, progress)
    return generic(db, kind, catalog_service.get_generic_layer(db, code), data, progress)
