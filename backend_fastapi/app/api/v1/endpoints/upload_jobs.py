"""
Upload GeoJSON atau Excel transaksi lewat antrian: POST membalas 202 + job_id setelah file disimpan,
worker mengerjakan analisis/simpan, FE membaca status tiap 1-2 detik.

FE boleh memecah file jadi beberapa part (GeoJSON: feature/part; Excel transaksi: baris/part) dan
mengirim beruntun dengan upload_group_id + part_index/part_total. Tiap part = satu job.

Sengaja TIDAK di bawah /spatial: semua GET /spatial/... di-cache Redis per user
(app/core/map_cache.py), sehingga status job yang di-poll akan terbaca basi.
"""
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Form, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession, user_has_permission
from app.api.params import UploadedFile, read_upload
from app.core.exceptions import not_found
from app.services.upload import failed_export, jobs, runner
from app.services.upload.trx_runner import is_trx_layer

router = APIRouter()
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _ensure_upload_access(db, user, layer: str) -> None:
    if is_trx_layer(layer):
        return
    if not user_has_permission(db, user, "upload:geojson"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki hak akses (upload:geojson) untuk fitur ini",
        )


def group_uuid(value: str | None) -> UUID | None:
    """UUID apa adanya; ID non-UUID dari FE lama (mis. `grp-<waktu>-<acak>` saat crypto.randomUUID tidak ada
    karena halaman dibuka lewat HTTP) dipetakan stabil ke UUIDv5 sehingga semua part tetap satu grup."""
    text_value = (value or "").strip()
    if not text_value:
        return None
    try:
        return UUID(text_value)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"webgis-upload-group:{text_value}")


@router.post("", status_code=status.HTTP_202_ACCEPTED, summary="Antrekan analisis/simpan upload (GeoJSON atau Excel transaksi)")
def create_job(
    db: DbSession,
    user: CurrentUser,
    file: UploadedFile,
    kind: Annotated[Literal["analyze", "execute"], Form(description="analyze = TAHAP 1, execute = TAHAP 2 (simpan)")],
    layer: Annotated[
        str,
        Form(description="GeoJSON: kode katalog spatial (blok, sawit, ...). "
                           "Excel transaksi: areal-statement | rotasi-pusingan"),
    ],
    bulan: Annotated[int, Form(ge=1, le=12)] = 1,
    tahun: Annotated[int, Form(ge=1900, le=2100)] = 2000,
    upload_group_id: Annotated[
        str | None,
        Form(max_length=200, description="ID grup (UUID) bila FE memecah file jadi beberapa part. "
                                         "ID lama non-UUID (grp-...) diubah deterministik ke UUIDv5."),
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
    _ensure_upload_access(db, user, layer)
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
        upload_group_id=group_uuid(upload_group_id),
        part_index=part_index,
        part_total=part_total,
        feature_offset=feature_offset,
    )


@router.get("/active", summary="Job antre/berjalan milik user (untuk melanjutkan setelah pindah halaman)")
def active_jobs(db: DbSession, user: CurrentUser):
    return jobs.active(db, user.id)


@router.get("/{job_id}", summary="Status job; `result` berisi respons upload-analyze/upload-execute setelah selesai")
def get_job(job_id: UUID, db: DbSession, user: CurrentUser):
    return jobs.get(db, job_id, user.id)


@router.get(
    "/{job_id}/data-gagal.xlsx",
    summary="Unduh SEMUA data gagal (semua part) hasil analisis/simpan sebagai Excel",
    response_class=Response,
    responses={200: {"content": {XLSX_MEDIA_TYPE: {}}}, 404: {"description": "Job tidak ada / tidak ada data gagal"}},
)
def download_failed_rows(job_id: UUID, db: DbSession, user: CurrentUser):
    """Job milik user (sama seperti GET status job). Semua part dalam grup upload yang sama digabung.
    analyze: data gagal + atribut & geometri asli; execute: data karantina (termasuk GAGAL_DISIMPAN)."""
    info = failed_export.collect(db, job_id, user.id)
    if not info["rows"]:
        raise not_found("Tidak ada data gagal pada proses upload ini.")
    content = failed_export.build_workbook(info)
    filename = failed_export.export_filename(info)
    return Response(content, media_type=XLSX_MEDIA_TYPE, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Cache-Control": "no-store",
    })


@router.post("/{job_id}/cancel", summary="Batalkan job (data tidak disimpan)")
def cancel_job(job_id: UUID, db: DbSession, user: CurrentUser):
    return jobs.cancel(db, job_id, user.id)
