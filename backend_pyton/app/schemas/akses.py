from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

# ==========================================
# 1. SCHEMAS LOG AKSES MENU
# ==========================================
class LogAksesMenuBase(BaseModel):
    role_id: Optional[str] = None
    menu_id: str

class LogAksesMenuCreate(LogAksesMenuBase):
    pass

class LogAksesMenuUpdate(BaseModel):
    role_id: Optional[str] = None
    menu_id: Optional[str] = None

class LogAksesMenuResponse(LogAksesMenuBase):
    id: int
    role_id: str
    created_date: datetime
    update_date: datetime

    class Config:
        from_attributes = True


# ==========================================
# 2. SCHEMAS LOG AKSES DATA (GIS)
# ==========================================
class LogAksesDataBase(BaseModel):
    role_id: Optional[str] = None
    kode_pt: Optional[str] = None
    kode_est: Optional[str] = None
    kode_area: Optional[str] = None
    kode_afd: Optional[str] = None

class LogAksesDataCreate(BaseModel):
    # Dibuat Optional agar saat Create Role, frontend tidak wajib mengirimkan role_id di tiap object
    role_id: Optional[str] = None
    kode_pt: str
    kode_est: Optional[str] = None
    # Menggunakan List agar frontend bisa mengirim banyak area atau afdeling sekaligus
    kode_area: Optional[List[str]] = None
    kode_afd: Optional[List[str]] = None

class LogAksesDataUpdate(BaseModel):
    role_id: Optional[str] = None
    kode_pt: Optional[str] = None
    kode_est: Optional[str] = None
    kode_area: Optional[str] = None
    kode_afd: Optional[str] = None

class LogAksesDataResponse(LogAksesDataBase):
    id: int
    role_id: str
    kode_pt: str
    created_date: datetime
    update_date: datetime

    class Config:
        from_attributes = True


# ==========================================
# 3. SCHEMAS LOG AKSES TRANSAKSI
# ==========================================
class LogAksesTransaksiBase(BaseModel):
    role_id: Optional[str] = None
    nama_table_transaksi: str

class LogAksesTransaksiCreate(LogAksesTransaksiBase):
    pass

class LogAksesTransaksiUpdate(BaseModel):
    role_id: Optional[str] = None
    nama_table_transaksi: Optional[str] = None

class LogAksesTransaksiResponse(LogAksesTransaksiBase):
    id: int
    role_id: str
    created_date: datetime
    update_date: datetime

    class Config:
        from_attributes = True

class AfdelingItem(BaseModel):
    id_afdeling: str
    nama_afdeling: Optional[str] = None

class EstateItem(BaseModel):
    id_estate: str
    nama_estate: Optional[str] = None
    afdeling: List[AfdelingItem] = []

class PerusahaanItem(BaseModel):
    id_perusahaan: str
    nama_perusahaan: Optional[str] = None
    estate: List[EstateItem] = []

class AreaTreeSchema(BaseModel):
    id_area: str
    nama_area: Optional[str] = None
    perusahaan: List[PerusahaanItem] = []

    class Config:
        from_attributes = True