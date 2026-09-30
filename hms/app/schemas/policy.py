from pydantic import BaseModel, Field
from uuid import UUID

class PolicyBase(BaseModel):
    hotel_id: UUID = Field(description="Valid value for hotel id.", examples=[""])
    policy_type: str = Field(description="Valid value for policy type.", examples=[""])
    description: str = Field(description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])

class PolicyCreate(PolicyBase):
    pass

class PolicyItem(PolicyBase):
    id: UUID

class PolicyListResponse(BaseModel):
    policies: list[PolicyItem] = Field(description="Valid value for policies.", examples=[""])

class PolicyUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    policy_type: str | None = Field(default=None, description="Valid value for policy type.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
