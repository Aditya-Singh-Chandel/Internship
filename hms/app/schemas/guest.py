from pydantic import BaseModel, Field, EmailStr
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

class GuestListResponse(BaseModel):
    guests: list[GuestItem]

class GuestUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    id_document_number: str | None = Field(default=None, description="Government ID or Passport number.", examples=[""])
