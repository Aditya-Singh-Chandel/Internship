from pydantic import BaseModel, Field, ConfigDict
from app.schemas.user import UserItem

class TokenData(BaseModel):
    access_token: str = Field(..., description="Short-lived JWT access token for API requests")
    refresh_token: str = Field(..., description="Long-lived JWT refresh token for renewing access")
    token_type: str = "bearer"
    user: UserItem | None = None

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    success: bool = Field(default=True, description="Request status flag")
    message: str = Field(default="Authentication successful", description="Human-readable response message")
    data: TokenData = Field(description="Token and user payload data")
    access_token: str = Field(..., description="Top-level token for RFC 6749 OAuth2 compatibility")
    refresh_token: str = Field(..., description="Top-level refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserItem | None = Field(default=None, description="Current user information")

    model_config = ConfigDict(from_attributes=True)

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="The refresh token provided during login or registration", examples=["eyJhbGciOiJIUzI1Ni..."])
