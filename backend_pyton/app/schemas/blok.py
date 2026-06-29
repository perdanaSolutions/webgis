from pydantic import BaseModel
from typing import List, Optional

# Response untuk dropdown filters
class EstateFilterResponse(BaseModel):
    kodeest: Optional[str]
    estate: Optional[str]

class AfdelingFilterResponse(BaseModel):
    kodeafd: Optional[str]
    afdeling: Optional[str]

# Response ringkas data blok (Tanpa data spatial yang berat, cocok untuk tabel/list)
class BlokSummaryResponse(BaseModel):
    objectid: int
    kode_blok: Optional[str]
    blok: Optional[str]
    status: Optional[str]
    ltanah: Optional[float]
    ltanam: Optional[float]
    pokok: Optional[float]

    class Config:
        from_attributes = True