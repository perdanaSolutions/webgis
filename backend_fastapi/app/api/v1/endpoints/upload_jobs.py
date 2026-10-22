"""
Upload GeoJSON lewat antrian: POST membalas 202 + job_id setelah file disimpan, worker
mengerjakan analisis/simpan, FE membaca status tiap 1-2 detik.

FE boleh memecah FeatureCollection menjadi beberapa part (mis. 1.000 feature/part) dan
mengirim beruntun dengan upload_group_id + part_index/part_total. Tiap part = satu job.

Sengaja TIDAK di bawah /spatial: semua GET /spatial/... di-cache Redis per user
(app/core/map_cache.py), sehingga status job yang di-poll akan terbaca basi.
"""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Form, status

from app.api.deps import CanUploadGeojson, DbSession
from app.api.params import UploadedFile, read_upload
from app.services.upload import jobs, runner

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED, summary="Antrekan analisis/simpan file GeoJSON")
def create_job(
    db: DbSession,
    user: CanUploadGeojson,
    file: UploadedFile,
    kind: Annotated[Literal["analyze", "execute"], Form(description="analyze = TAHAP 1, execute = TAHAP 2 (simpan)")],
    layer: Annotated[str, Form(description="Kode jenis dari GET /spatial/geo/catalog (blok, sawit, jalan, ...)")],
    bulan: Annotated[int, Form(ge=1, le=12)],
    tahun: Annotated[int, Form(ge=1900, le=2100)],
    upload_group_id: Annotated[
        UUID | None,
        Form(description="ID grup bila FE memecah file jadi beberapa part Feature"),
    ] = None,
    part_index: Annotated[
        int | None,
        Form(ge=1, description="Nomor part (1-based). Wajib bersama part_total."),
    ] = None,
    part_total: Annotated[
        int | None,
        Form(ge=1, description="Jumlah total part Feature untuk grup ini."),
    ] = None,
    feature_offset: Annotated[
        int,
        Form(ge=0, description="Jumlah feature sebelum part ini di file asli (0 untuk part 1). "
                               "no_preview hasil = feature_offset + nomor feature di part."),
    ] = 0,
):
    content = read_upload(file)
    runner.check_layer(db, layer)
    return jobs.create(
        db,
        user_id=user.id,
        kind=kind,
        layer=layer,
        bulan=bulan,
        tahun=tahun,
        filename=file.filename,
        content=content,
        upload_group_id=upload_group_id,
        part_index=part_index,
        part_total=part_total,
        feature_offset=feature_offset,
    )


@router.get("/active", summary="Job antre/berjalan milik user (untuk melanjutkan setelah pindah halaman)")
def active_jobs(db: DbSession, user: CanUploadGeojson):
    return jobs.active(db, user.id)


@router.get("/{job_id}", summary="Status job; `result` berisi respons upload-analyze/upload-execute setelah selesai")
def get_job(job_id: UUID, db: DbSession, user: CanUploadGeojson):
    return jobs.get(db, job_id, user.id)


@router.post("/{job_id}/cancel", summary="Batalkan job (data tidak disimpan)")
def cancel_job(job_id: UUID, db: DbSession, user: CanUploadGeojson):
    return jobs.cancel(db, job_id, user.id)
