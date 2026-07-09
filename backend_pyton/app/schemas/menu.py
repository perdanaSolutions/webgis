from pydantic import BaseModel, model_validator
from uuid import UUID
from typing import Optional, List, Any

# Schema dasar untuk input Create & Update
class MenuBase(BaseModel):
    title: str
    description: Optional[str] = None
    bg_class: Optional[str] = "bg-blue-50"      # Mapping dari bgClass
    icon_class: Optional[str] = "text-blue-500" # Mapping dari iconClass
    arrow_class: Optional[str] = "text-blue-500" # Mapping dari arrowClass
    to: str                                     # Route tujuan path FE (e.g., '/dashboard')
    icon: str                                   # Nama icon (e.g., 'report')
    order_position: Optional[int] = 0           # Urutan menu di FE

class MenuCreate(MenuBase):
    pass

class MenuUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    bg_class: Optional[str] = None
    icon_class: Optional[str] = None
    arrow_class: Optional[str] = None
    to: Optional[str] = None
    icon: Optional[str] = None
    order_position: Optional[int] = None

# Schema Response yang akan dikonsumsi FE (CamelCase transformer di level properti)
class MenuResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    bgClass: Optional[str]     
    iconClass: Optional[str]
    arrowClass: Optional[str]
    to: str
    icon: str
    order_position: int

    class Config:
        from_attributes = True

    # KITA GANTI MENGGUNAKAN APPROACH VALIDATOR YANG LEBIH AMAN:
    @model_validator(mode='before')
    @classmethod
    def map_snake_to_camel(cls, data: Any) -> Any:
        # Jika data bertipe objek mapping/database row, konversi manual ke dict camelCase
        if hasattr(data, "bg_class") or "bg_class" in data:
            # Mengatasi objek bertipe RowMapping maupun objek model biasa
            d = dict(data) if isinstance(data, (dict, ) ) or hasattr(data, "keys") else data.__dict__
            return {
                "id": d.get("id"),
                "title": d.get("title"),
                "description": d.get("description"),
                "bgClass": d.get("bg_class"),
                "iconClass": d.get("icon_class"),
                "arrowClass": d.get("arrow_class"),
                "to": d.get("to"),
                "icon": d.get("icon"),
                "order_position": d.get("order_position", 0)
            }
        return data