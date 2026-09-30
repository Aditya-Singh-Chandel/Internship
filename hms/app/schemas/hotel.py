from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from decimal import Decimal

class HotelBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    address_line1: str = Field(description="Valid value for address line1.", examples=[""])
    address_line2: str | None = Field(default=None, description="Valid value for address line2.", examples=[""])
    city: str = Field(description="Valid value for city.", examples=[""])
    state: str = Field(description="Valid value for state.", examples=[""])
    country: str = Field(description="Valid value for country.", examples=[""])
    postal_code: str = Field(description="Valid value for postal code.", examples=[""])
    latitude: Decimal | None = Field(default=None, description="Valid value for latitude.", examples=[""])
    longitude: Decimal | None = Field(default=None, description="Valid value for longitude.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])

class HotelCreate(HotelBase):
    pass

class HotelItem(HotelBase):
    id: UUID

class HotelListResponse(BaseModel):
    hotels: list[HotelItem]

class HotelUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    address_line1: str | None = Field(default=None, description="Valid value for address line1.", examples=[""])
    address_line2: str | None = Field(default=None, description="Valid value for address line2.", examples=[""])
    city: str | None = Field(default=None, description="Valid value for city.", examples=[""])
    state: str | None = Field(default=None, description="Valid value for state.", examples=[""])
    country: str | None = Field(default=None, description="Valid value for country.", examples=[""])
    postal_code: str | None = Field(default=None, description="Valid value for postal code.", examples=[""])
    latitude: Decimal | None = Field(default=None, description="Valid value for latitude.", examples=[""])
    longitude: Decimal | None = Field(default=None, description="Valid value for longitude.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
    phone: str | None = Field(default=None, description="Phone contact number.", examples=[""])
    email: EmailStr | None = Field(default=None, description="A valid email address format (e.g. user@example.com).", examples=[""])
