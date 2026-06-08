"""Ideal Customer Profile input contract.

The field names intentionally mirror ``frontend/lib/icp.ts`` so the backend can
validate the wire payload without adding a mapping layer.
"""

from typing import Any

from pydantic import Field, field_validator

from saas_lead_agent.schemas.base import StrictBaseModel


class IcpContext(StrictBaseModel):
    seller_name: str = Field(default="", max_length=300)
    offering: str = Field(default="", max_length=500)
    target_industries: list[str] = Field(default_factory=list, max_length=30)
    target_stages: list[str] = Field(default_factory=list, max_length=30)
    target_geographies: list[str] = Field(default_factory=list, max_length=30)
    target_employees: str = Field(default="Any", max_length=100)
    must_have_signals: list[str] = Field(default_factory=list, max_length=30)
    red_flags: list[str] = Field(default_factory=list, max_length=30)
    value_proposition: str = Field(default="", max_length=2_000)

    @field_validator(
        "target_industries",
        "target_stages",
        "target_geographies",
        "must_have_signals",
        "red_flags",
        mode="before",
    )
    @classmethod
    def _normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of strings")
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                normalized.append(text[:300])
        return normalized
