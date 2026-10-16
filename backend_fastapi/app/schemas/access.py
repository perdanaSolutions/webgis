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
    kode_grup: str | None = Field(None, description="Akses seluruh grup (semua PT di grup itu), mis. 'SGA'")
    kode_pt: str | None = None
    kode_est: str | None = None
    kode_area: list[str] | None = None
    kode_afd: list[str] | None = None


class AksesDataResponse(BaseModel):
    id: int
    role_id: str
    level: str = Field(description="group | area | company | estate | division")
    kode_grup: str | None = None
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


# Pohon akses struktur v2: Grup -> PT -> Area -> Estate -> Afdeling. `penuh` = seluruh node itu diberikan
# (anak-anaknya tidak dirinci); node tanpa `penuh` hanya jalur menuju akses yang lebih sempit.
class GroupTreeAfdeling(BaseModel):
    id_afdeling: str
    kode_afd: str | None = None


class GroupTreeEstate(BaseModel):
    id_estate: str
    kode_est: str | None = None
    nama_estate: str | None = None
    penuh: bool = False
    afdeling: list[GroupTreeAfdeling] = []


class GroupTreeArea(BaseModel):
    kode_area: str | None = None
    nama_area: str | None = None
    penuh: bool = False
    estate: list[GroupTreeEstate] = []


class GroupTreePerusahaan(BaseModel):
    id_perusahaan: str
    kode_pt: str | None = None
    nama_perusahaan: str | None = None
    penuh: bool = False
    area: list[GroupTreeArea] = []


class GroupTreeSchema(BaseModel):
    kode_grup: str | None = Field(None, description="null = PT yang belum punya grup")
    nama_grup: str | None = None
    penuh: bool = False
    perusahaan: list[GroupTreePerusahaan] = []


class GroupScopeInput(BaseModel):
    kode_grup: list[str] = Field(..., min_length=1, description="Kode/nama grup, mis. ['SGA']")
