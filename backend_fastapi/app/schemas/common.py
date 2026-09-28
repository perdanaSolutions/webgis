from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel):
    total_data: int
    page: int
    limit: int
    total_page: int
    data: list[Any]


class MessageResponse(BaseModel):
    message: str
