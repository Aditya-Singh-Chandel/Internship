from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import ItemResponse, PaginatedResponse

class RoleBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class RoleCreate(RoleBase):
    pass

class RoleItem(RoleBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

RoleItemResponse = ItemResponse[RoleItem]
RolePaginatedResponse = PaginatedResponse[RoleItem]
