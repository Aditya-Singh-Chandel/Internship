from pydantic import BaseModel, Field
from uuid import UUID

class RoleBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class RoleCreate(RoleBase):
    pass

class RoleItem(RoleBase):
    id: UUID

class RoleListResponse(BaseModel):
    roles: list[RoleItem]

class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
