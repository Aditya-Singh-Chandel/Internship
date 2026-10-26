from enum import Enum
from typing import Generic, TypeVar, Any
from pydantic import BaseModel, Field

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class StringFilterOperator(str, Enum):
    eq = "eq"
    like = "like"

FilterOperator = StringFilterOperator

class NumericFilterOperator(str, Enum):
    eq = "eq"
    lt = "lt"
    gt = "gt"
    lte = "lte"
    gte = "gte"

T = TypeVar("T")

class PaginationMeta(BaseModel):
    total: int = Field(description="Total count of matching records across all pages")
    page: int = Field(description="Current page number (1-indexed)")
    limit: int = Field(description="Maximum items per page")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")

class ItemResponse(BaseModel, Generic[T]):
    success: bool = Field(default=True, description="Request status flag")
    message: str = Field(default="Operation completed successfully", description="Human-readable response message")
    data: T = Field(description="Payload resource data")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = Field(default=True, description="Request status flag")
    message: str = Field(default="Records retrieved successfully", description="Human-readable response message")
    data: list[T] = Field(description="List of records for current page")
    pagination: PaginationMeta = Field(description="Pagination metadata")

class ActionResponse(BaseModel):
    success: bool = Field(default=True, description="Request status flag")
    message: str = Field(description="Human-readable confirmation message")
    data: dict[str, Any] | None = Field(default=None, description="Optional action metadata or affected entity ID")

class ErrorResponse(BaseModel):
    success: bool = Field(default=False, description="Always false for error responses")
    message: str = Field(description="Detailed error message")
    error_code: str = Field(description="Categorical error code (e.g. NOT_FOUND, FORBIDDEN, VALIDATION_ERROR)")
    details: Any = Field(default=None, description="Optional error details or field validation issues")
