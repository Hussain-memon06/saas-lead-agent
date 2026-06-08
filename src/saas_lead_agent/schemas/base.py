"""Shared Pydantic configuration for domain schemas."""

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    """Base model with strict boundaries for agent/API contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
