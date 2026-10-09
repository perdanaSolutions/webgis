from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class Uploader(BaseModel):
    id: UUID
    nama_lengkap: str
    username: str


class UploadHistoryResponse(BaseModel):
    id: UUID
    jenis_sumber: str
    tabel_tujuan: str
    layer: str | None = None
    nama_file: str | None = None
    periode: date | None = None
    jumlah_data: int
    status: str
    pesan_error: str | None = None
    diupload_oleh: Uploader | None = None
    mulai: datetime
    selesai: datetime | None = None
    durasi_detik: float | None = None


class UploadHistoryDetail(UploadHistoryResponse):
    metadata: dict[str, Any] | None = None
