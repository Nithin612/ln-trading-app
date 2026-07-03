from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class CategoryCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name must not be empty")
        return v


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    created_by: int | None
    created_at: datetime


class CategoryWithCount(CategoryRead):
    stock_count: int = 0


class StockTagRequest(BaseModel):
    category_id: int


class StockTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_id: int
    category_id: int
    tagged_at: datetime
    tagged_by: int | None
