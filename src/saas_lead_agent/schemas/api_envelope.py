"""Planned API response envelope contracts.

The current public routes still return the existing flat response models to
preserve frontend compatibility. These models define the versioned envelope
shape planned for a future `/api/v1` transition.
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import Field, model_validator

from saas_lead_agent.schemas.base import StrictBaseModel

T = TypeVar("T")


class APIError(StrictBaseModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1_000)
    details: dict[str, Any] | None = None


class APIResponse(StrictBaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: APIError | None = None
    request_id: str = Field(min_length=1, max_length=200)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_success_shape(self) -> "APIResponse[T]":
        if self.success and self.error is not None:
            raise ValueError("successful responses must not include error")
        if not self.success and self.error is None:
            raise ValueError("failed responses must include error")
        return self
