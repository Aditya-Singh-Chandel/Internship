from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class PolicyBase(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id. Defaults to manager's assigned hotel if omitted.", examples=[None])
    policy_type: str = Field(description="Valid value for policy type.", examples=[""])
    description: str = Field(description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])

class PolicyCreate(PolicyBase):
    pass

class PolicyItem(PolicyBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PolicyUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    policy_type: str | None = Field(default=None, description="Valid value for policy type.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])

from app.schemas.common import ItemResponse, PaginatedResponse

PolicyItemResponse = ItemResponse[PolicyItem]
PolicyPaginatedResponse = PaginatedResponse[PolicyItem]
