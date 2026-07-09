from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any

# Schema Ringkas untuk data User di dalam Log (tetap UUID jika id user-mu UUID)
class UserInLog(BaseModel):
    id: UUID
    username: str
    nama_lengkap: str
    class Config:
        from_attributes = True

# Schema Utama untuk Response Activity Log
class ActivityLogResponse(BaseModel):
    id: int  # <--- GANTI DI SINI (Ubah dari UUID menjadi int)
    user_id: Optional[UUID]
    user: Optional[UserInLog] = None  
    aksi: str                        
    resource: str                    
    status: str                      
    detail: Optional[Any] = None     
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True