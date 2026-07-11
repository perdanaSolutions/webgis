from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any

# Konfigurasi dasar Pydantic v2 agar bisa membaca objek ORM SQLAlchemy otomatis
class SpatialBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 1. RESPONSE UNTUK PT / PERUSAHAAN
# ==========================================
class PTResponse(SpatialBase):
    id: int
    nama_pt: str
    kode_pt: str
    bulan: Optional[int] = None
    tahun: Optional[int] = None

# ==========================================
# 2. RESPONSE UNTUK ESTATE
# ==========================================
class EstateResponse(SpatialBase):
    id: str
    pt_id: int
    nama_estate: str
    kode_estate: str
    bulan: Optional[int] = None
    tahun: Optional[int] = None

# ==========================================
# 3. RESPONSE UNTUK BLOK / BLOCKS
# ==========================================
class BlokResponse(SpatialBase):
    id: str
    estate_id: str
    nama_blok: str
    kode_blok: str
    luas_ha: float
    status_tanaman: Optional[str] = None
    komoditas: Optional[str] = None
    bulan: Optional[int] = None
    tahun: Optional[int] = None

# ==========================================
# 4. RESPONSE STRUKTUR PAGINATION (Bawaan Sistem Kamu)
# ==========================================
class PaginatedResponse(BaseModel):
    total_data: int
    page: int
    limit: int
    total_page: int
    data: List[Any]

# ==========================================
# 5. RESPONSE STRUKTUR GEOJSON PETA
# ==========================================
class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: Any
    properties: Any

class GeoJSONResponse(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]