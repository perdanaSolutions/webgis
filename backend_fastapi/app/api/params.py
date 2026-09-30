"""Parameter query & upload yang dipakai berulang oleh banyak endpoint."""
from typing import Annotated

from fastapi import Depends, File, Query, UploadFile

from app.core.config import settings
from app.core.exceptions import bad_request
from app.services.block_filter import BlockFilter

Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
Bulan = Annotated[int | None, Query(ge=1, le=12, description="Bulan (1-12)")]
Tahun = Annotated[int | None, Query(ge=1900, le=2100, description="Tahun")]
UploadedFile = Annotated[UploadFile, File(description="File yang diunggah")]
BulanWajib = Annotated[int, Query(ge=1, le=12, description="Bulan periode (1-12)")]
TahunWajib = Annotated[int, Query(ge=1900, le=2100, description="Tahun periode")]


def block_filter(
    area_id: Annotated[str | None, Query(description="Kode/ID area (mis. BERAU)")] = None,
    kode_pt: Annotated[str | None, Query(description="Kode/ID PT")] = None,
    kode_est: Annotated[str | None, Query(description="Kode/ID estate")] = None,
    kode_afd: Annotated[str | None, Query(description="Kode/ID afdeling")] = None,
    kode_blok: Annotated[str | None, Query(description="ID blok (numerik), kode blok, atau ID blok lama v2")] = None,
    ownership: Annotated[str | None, Query(description="Tipe blok / kepemilikan. Kosong = semua")] = None,
    tahun_tanam: Annotated[int | None, Query(ge=0, le=2100, description="Tahun tanam. Kosong = semua")] = None,
) -> BlockFilter:
    return BlockFilter(
        area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok,
        ownership=ownership, tahun_tanam=None if tahun_tanam is None else str(tahun_tanam),
    )


BlockFilterDep = Annotated[BlockFilter, Depends(block_filter)]


def read_upload(file: UploadFile) -> bytes:
    """Baca file upload (dipanggil dari endpoint sync -> berjalan di threadpool, tidak memblok event loop)."""
    limit = settings.UPLOAD_MAX_MB * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise bad_request(f"Ukuran file melebihi {settings.UPLOAD_MAX_MB} MB.", field="file")
    if not content:
        raise bad_request("File kosong.", field="file")
    return content
