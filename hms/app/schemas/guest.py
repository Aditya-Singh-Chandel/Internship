from pydantic import BaseModel, Field, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime

class GuestBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    id_document_number: str | None = Field(default=None, description="Government ID or Passport number.", examples=[""])

class GuestCreate(GuestBase):
    pass

class GuestItem(GuestBase):
    id: UUID
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class GuestUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    id_document_number: str | None = Field(default=None, description="Government ID or Passport number.", examples=[""])

class GuestListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    guests: list[GuestItem]

    model_config = ConfigDict(from_attributes=True)
