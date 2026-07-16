from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 1. Schemas Log Akses Menu
class LogAksesMenuBase(BaseModel):
    user_id: str
    menu_id: str

class LogAksesMenuCreate(LogAksesMenuBase):
    pass

class LogAksesMenuResponse(LogAksesMenuBase):
    id: int
    created_date: datetime
    update_date: datetime
    class Config:
        from_attributes = True

# 2. Schemas Log Akses Data
class LogAksesDataBase(BaseModel):
    user_id: str
    kode_pt: str = None
    kode_est: str = None

class LogAksesDataCreate(LogAksesDataBase):
    pass

class LogAksesDataResponse(LogAksesDataBase):
    id: int
    created_date: datetime
    update_date: datetime
    class Config:
        from_attributes = True

# 3. Schemas Log Akses Transaksi
class LogAksesTransaksiBase(BaseModel):
    user_id: str # DIUBAH MENJADI STR
    nama_table_transaksi: str

class LogAksesTransaksiCreate(LogAksesTransaksiBase):
    pass

class LogAksesTransaksiResponse(LogAksesTransaksiBase):
    id: int
    created_date: datetime
    update_date: datetime
    class Config:
        from_attributes = True

# 1. Update Schema untuk Log Akses Menu
class LogAksesMenuUpdate(BaseModel):
    user_id: Optional[str] = None
    menu_id: Optional[str] = None

# 2. Update Schema untuk Log Akses Data
class LogAksesDataUpdate(BaseModel):
    user_id: Optional[str] = None
    kode_pt: Optional[str] = None
    kode_est: Optional[str] = None

# 3. Update Schema untuk Log Akses Transaksi
class LogAksesTransaksiUpdate(BaseModel):
    user_id: Optional[str] = None
    nama_table_transaksi: Optional[str] = None