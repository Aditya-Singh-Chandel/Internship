from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class PolicyBase(BaseModel):
    hotel_id: UUID = Field(description="Valid value for hotel id.", examples=[""])
    policy_type: str = Field(description="Valid value for policy type.", examples=[""])
    description: str = Field(description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])

class PolicyCreate(PolicyBase):
    pass

from datetime import datetime

class PolicyItem(PolicyBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PolicyUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    policy_type: str | None = Field(default=None, description="Valid value for policy type.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])

class PolicyListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    policies: list[PolicyItem]

    model_config = ConfigDict(from_attributes=True)
