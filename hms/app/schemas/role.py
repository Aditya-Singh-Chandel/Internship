from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class RoleBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class RoleCreate(RoleBase):
    pass

from datetime import datetime

class RoleItem(RoleBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class RoleListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    roles: list[RoleItem]

    model_config = ConfigDict(from_attributes=True)
