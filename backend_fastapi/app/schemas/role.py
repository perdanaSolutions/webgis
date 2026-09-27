from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.access import (
    AksesDataInput,
    AksesDataResponse,
    AksesMenuResponse,
    AksesTransaksiResponse,
    AreaTreeSchema,
)

AksesDataItem = Union[AreaTreeSchema, AksesDataInput]


def parse_akses_data_list(value) -> list:
    """Terima pohon wilayah (bulk) atau payload kode lama, dalam satu list."""
    if not isinstance(value, list):
        raise ValueError("akses_data harus berupa list")
    parsed: list = []
    for item in value:
        raw = item.model_dump() if isinstance(item, BaseModel) else item
        if not isinstance(raw, dict):
            raise ValueError("item akses_data tidak valid")
        if "id_area" in raw:
            parsed.append(AreaTreeSchema.model_validate(raw))
        else:
            parsed.append(AksesDataInput.model_validate(raw))
    return parsed


class RoleBase(BaseModel):
    nama: str
    deskripsi: Optional[str] = None


class RoleCreate(RoleBase):
    """Satu payload: menu, pohon wilayah, dan tabel transaksi sekaligus."""

    akses_menu: List[str] = Field(default_factory=list)
    akses_data: List[AksesDataItem] = Field(default_factory=list)
    akses_transaksi: List[str] = Field(default_factory=list)

    @field_validator("akses_data", mode="before")
    @classmethod
    def _parse_akses_data(cls, value):
        if value is None:
            return []
        return parse_akses_data_list(value)


class RoleUpdate(BaseModel):
    """Field akses yang tidak dikirim tidak diubah. List kosong mengosongkan akses itu."""

    nama: str
    deskripsi: Optional[str] = None
    akses_menu: Optional[List[str]] = None
    akses_data: Optional[List[AksesDataItem]] = None
    akses_transaksi: Optional[List[str]] = None

    @field_validator("akses_data", mode="before")
    @classmethod
    def _parse_akses_data(cls, value):
        if value is None:
            return None
        return parse_akses_data_list(value)


class RoleResponse(RoleBase):
    id: UUID
    created_at: datetime

    # Diisi dari auth.role_menus, auth.role_data_scopes, dan auth.role_permissions.
    akses_menu: List[AksesMenuResponse] = []
    akses_data: List[AksesDataResponse] = []
    akses_wilayah: List[AreaTreeSchema] = []
    akses_transaksi: List[AksesTransaksiResponse] = []

    class Config:
        from_attributes = True