from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    email: EmailStr = Field(description="A valid email address format (e.g. user@example.com).", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    role_id: UUID = Field(description="Valid value for role id.", examples=[""])

class UserCreate(UserBase):
    password: str = Field(description="Strong password for authentication.", examples=[""])

class UserItem(UserBase):
    id: UUID
    created_at: datetime

class UserListResponse(BaseModel):
    users: list[UserItem]

class UserUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    role_id: UUID | None = Field(default=None, description="Valid value for role id.", examples=[""])
