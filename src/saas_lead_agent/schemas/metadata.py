"""Processing metadata contracts for agent runs."""

from datetime import UTC, datetime

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel


class ProcessingMetadata(StrictBaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    thread_id: str = Field(min_length=1, max_length=500)
    model_used: str | None = Field(default=None, max_length=200)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_breakdown_usd: dict[str, float] = Field(default_factory=dict)
    provider_status: dict[str, str] = Field(default_factory=dict)
    duration_seconds: float = Field(default=0.0, ge=0)
    steps_completed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
