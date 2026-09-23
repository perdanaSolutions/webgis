from pydantic import BaseModel, field_validator, model_validator
from uuid import UUID
from typing import Optional, List, Any


def _empty_to_blank(value: Any) -> str:
    if value is None:
        return ""
    return value


def _empty_to_none(value: Any) -> Any:
    if value is None or value == "":
        return None
    return value


class MenuBase(BaseModel):
    title: str
    description: Optional[str] = None
    bg_class: Optional[str] = "bg-blue-50"
    icon_class: Optional[str] = "text-blue-500"
    arrow_class: Optional[str] = "text-blue-500"
    to: Optional[str] = ""
    icon: str
    order_position: Optional[int] = 0
    parent_id: Optional[UUID] = None

    @field_validator("to", mode="before")
    @classmethod
    def normalize_to(cls, value: Any) -> str:
        return _empty_to_blank(value)

    @field_validator("parent_id", mode="before")
    @classmethod
    def normalize_parent_id(cls, value: Any) -> Any:
        return _empty_to_none(value)


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
    parent_id: Optional[UUID] = None

    @field_validator("to", mode="before")
    @classmethod
    def normalize_to(cls, value: Any) -> Any:
        if value is None:
            return None
        return _empty_to_blank(value)

    @field_validator("parent_id", mode="before")
    @classmethod
    def normalize_parent_id(cls, value: Any) -> Any:
        return _empty_to_none(value)


class MenuResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    bgClass: Optional[str] = None
    iconClass: Optional[str] = None
    arrowClass: Optional[str] = None
    to: str = ""
    icon: str
    order_position: int = 0
    parentId: Optional[UUID] = None
    level: int = 1
    children: List["MenuResponse"] = []

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def map_snake_to_camel(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data

        if not isinstance(data, dict) and hasattr(data, "keys"):
            data = dict(data)

        if isinstance(data, dict) and "bg_class" in data:
            return {
                "id": data.get("id"),
                "title": data.get("title"),
                "description": data.get("description"),
                "bgClass": data.get("bg_class"),
                "iconClass": data.get("icon_class"),
                "arrowClass": data.get("arrow_class"),
                "to": data.get("to") or "",
                "icon": data.get("icon"),
                "order_position": data.get("order_position") or 0,
                "parentId": data.get("parent_id"),
                "level": data.get("level") or 1,
                "children": data.get("children") or [],
            }
        return data


MenuResponse.model_rebuild()
