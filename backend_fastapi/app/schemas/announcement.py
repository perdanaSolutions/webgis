from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

StatusPengumuman = Literal["aktif", "terjadwal", "kedaluwarsa", "nonaktif"]


def _clean(value):
    return value.strip() if isinstance(value, str) else value


class AnnouncementBase(BaseModel):
    judul: str = Field(min_length=1, max_length=200)
    isi: str = Field(min_length=1)
    is_active: bool = True
    tanggal_mulai: datetime | None = None
    tanggal_berakhir: datetime | None = None

    _strip = field_validator("judul", "isi", mode="before")(_clean)

    @model_validator(mode="after")
    def check_period(self):
        if self.tanggal_mulai and self.tanggal_berakhir and self.tanggal_berakhir < self.tanggal_mulai:
            raise ValueError("tanggal_berakhir tidak boleh lebih awal dari tanggal_mulai")
        return self


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    """Field yang tidak dikirim tidak diubah. tanggal_* = null menghapus batas tanggal."""

    judul: str | None = Field(default=None, min_length=1, max_length=200)
    isi: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    tanggal_mulai: datetime | None = None
    tanggal_berakhir: datetime | None = None

    _strip = field_validator("judul", "isi", mode="before")(_clean)


class AnnouncementResponse(BaseModel):
    id: UUID
    judul: str
    isi: str
    is_active: bool
    status: StatusPengumuman
    tanggal_mulai: datetime | None = None
    tanggal_berakhir: datetime | None = None
    dibuat_oleh: str | None = None
    created_at: datetime
    updated_at: datetime
