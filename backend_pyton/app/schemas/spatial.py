from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List, Any

# 1. Schema PT
class PTResponse(BaseModel):
    id: UUID
    nama_pt: str
    kode_pt: str
    class Config:
        from_attributes = True

# 2. Schema Estate / Area
class EstateResponse(BaseModel):
    id: UUID
    pt_id: UUID
    nama_estate: str
    kode_estate: str
    class Config:
        from_attributes = True

# 3. Schema Atribut Blok untuk List/Table Biasa
class BlokResponse(BaseModel):
    id: UUID
    estate_id: UUID
    nama_blok: str
    kode_blok: str
    luas_ha: float
    status_tanaman: Optional[str] = None
    komoditas: Optional[str] = None
    class Config:
        from_attributes = True

# 4. Wrapper untuk Server-Side Pagination (List Data)
class PaginatedResponse(BaseModel):
    total_data: int
    page: int
    limit: int
    total_page: int
    data: List[Any]
    class Config:
        from_attributes = True

# 5. Schema khusus GeoJSON Peta (Tidak di-paginate karena peta butuh semua poligon sekaligus)
class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: Any
    properties: Any

class GeoJSONResponse(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]