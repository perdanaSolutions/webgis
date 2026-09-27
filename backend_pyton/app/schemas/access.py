"""
Hak akses role: menu, data wilayah (scope), dan tabel transaksi.

Di gis_db_v3 ketiganya disimpan di auth.role_menus, auth.role_data_scopes,
dan auth.permissions (resource = nama tabel, action = 'read'). Nama field
response mengikuti API lama (log_akses_*) supaya FE tidak perlu berubah.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class AksesMenuCreate(BaseModel):
    role_id: str
    menu_id: str


class AksesMenuUpdate(BaseModel):
    role_id: str | None = None
    menu_id: str | None = None


class AksesMenuResponse(BaseModel):
    id: str = Field(description="Gabungan '<role_id>:<menu_id>' (tabel role_menus tidak punya id tunggal)")
    role_id: str
    menu_id: str
    created_date: datetime | None = None
    update_date: datetime | None = None


class AksesDataInput(BaseModel):
    """Payload lama saat create role: satu PT dengan daftar area/afdeling."""

    role_id: str | None = None
    kode_pt: str | None = None
    kode_est: str | None = None
    kode_area: list[str] | None = None
    kode_afd: list[str] | None = None


class AksesDataResponse(BaseModel):
    id: int
    role_id: str
    level: str = Field(description="area | company | estate | division")
    kode_pt: str | None = None
    kode_est: str | None = None
    kode_area: str | None = None
    kode_afd: str | None = None
    created_date: datetime | None = None
    update_date: datetime | None = None


class AksesTransaksiCreate(BaseModel):
    role_id: str
    nama_table_transaksi: str


class AksesTransaksiUpdate(BaseModel):
    role_id: str | None = None
    nama_table_transaksi: str | None = None


class AksesTransaksiResponse(BaseModel):
    id: str = Field(description="Gabungan '<role_id>:<permission_id>'")
    role_id: str
    nama_table_transaksi: str
    created_date: datetime | None = None
    update_date: datetime | None = None


class AfdelingItem(BaseModel):
    id_afdeling: str
    nama_afdeling: str | None = None


class EstateItem(BaseModel):
    id_estate: str
    nama_estate: str | None = None
    afdeling: list[AfdelingItem] = []


class PerusahaanItem(BaseModel):
    id_perusahaan: str
    nama_perusahaan: str | None = None
    estate: list[EstateItem] = []


class AreaTreeSchema(BaseModel):
    id_area: str
    nama_area: str | None = None
    perusahaan: list[PerusahaanItem] = []
