"""Common API schemas."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class HealthStatus(BaseModel):
    status: str
    database: str
    gcp_auth: str
    version: str = "0.1.0"
    details: dict[str, Any] | None = None
