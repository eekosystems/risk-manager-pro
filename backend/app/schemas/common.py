from pydantic import BaseModel, Field


class MetaResponse(BaseModel):
    request_id: str = Field(
        description="Correlation ID for request tracing (same as X-Correlation-ID header)"
    )


class DataResponse[T](BaseModel):
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


class PaginatedResponse[T](BaseModel):
    data: list[T]
    meta: PaginatedMeta
