from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaResponse(BaseModel):
    request_id: str = Field(
        description="Correlation ID for request tracing (same as X-Correlation-ID header)"
    )


class DataResponse(BaseModel, Generic[T]):
    data: T
    meta: MetaResponse


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginatedMeta(MetaResponse):
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginatedMeta
