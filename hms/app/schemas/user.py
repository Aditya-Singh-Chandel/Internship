from pydantic import BaseModel, Field, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime
from app.schemas.role import RoleItem

class UserBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=["John Doe"])
    email: EmailStr = Field(description="A valid email address format (e.g. user@example.com).", examples=["john@example.com"])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=["+1234567890"])
    role_id: UUID | None = Field(default=None, description="Valid value for role id. Optional if role_name is provided.", examples=[None])
    role_name: str | None = Field(default=None, description="Role name ('admin', 'manager', 'receptionist', 'customer'). Optional if role_id is provided.", examples=["customer"])
    hotel_id: UUID | None = Field(default=None, description="Optional assigned hotel ID for staff members (receptionist/manager).", examples=[None])

class UserCreate(UserBase):
    password: str = Field(description="Strong password for authentication.", examples=["Secret123!"])

class UserRegister(BaseModel):
    name: str = Field(description="User's full name", examples=["John Doe"])
    email: EmailStr = Field(description="Valid email address", examples=["john@example.com"])
    password: str = Field(min_length=6, description="Password (at least 6 characters)", examples=["Secret123!"])
    phone: str | None = Field(default=None, description="Phone contact number", examples=["+1234567890"])
    role_id: UUID | None = Field(default=None, description="Optional role id. Defaults to 'customer' if omitted.")
    role_name: str | None = Field(default=None, description="Optional role name ('admin', 'manager', 'receptionist', 'customer'). Defaults to 'customer'.")
    hotel_id: UUID | None = Field(default=None, description="Optional assigned hotel ID for staff.", examples=[None])

class UserItem(UserBase):
    id: UUID
    role: RoleItem | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    role_id: UUID | None = Field(default=None, description="Valid value for role id.", examples=[""])
    role_name: str | None = Field(default=None, description="Role name ('admin', 'manager', 'receptionist', 'customer').", examples=[""])
    hotel_id: UUID | None = Field(default=None, description="Optional assigned hotel ID for staff.", examples=[None])

from app.schemas.common import ItemResponse, PaginatedResponse

UserItemResponse = ItemResponse[UserItem]
UserPaginatedResponse = PaginatedResponse[UserItem]

class AdminInitRequest(BaseModel):
    name: str = Field(default="System Administrator", description="Admin name", examples=["System Administrator"])
    email: EmailStr = Field(default="admin@hms.com", description="Admin login email", examples=["admin@hms.com"])
    password: str = Field(default="Admin123!", min_length=6, description="Admin password", examples=["Admin123!"])
    phone: str | None = Field(default="+1000000000", description="Admin contact phone", examples=["+1000000000"])
