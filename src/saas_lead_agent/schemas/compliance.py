"""Phase 6 compliance configuration contracts.

These models document intended production safety settings without changing
runtime configuration. Enforcement belongs to a later approved Phase 6 slice.
"""

from typing import Literal

from pydantic import Field, model_validator

from saas_lead_agent.schemas.base import StrictBaseModel

DeploymentEnvironment = Literal["development", "staging", "production"]
AuditEventCategory = Literal[
    "auth",
    "lead_access",
    "approval",
    "email_delivery",
    "configuration",
    "security",
]


class CorsPolicy(StrictBaseModel):
    """Planned CORS policy for one environment."""

    environment: DeploymentEnvironment
    allowed_origins: list[str] = Field(min_length=1, max_length=20)
    allow_wildcard: bool = False

    @model_validator(mode="after")
    def validate_production_cors(self) -> "CorsPolicy":
        if self.environment == "production" and self.allow_wildcard:
            raise ValueError("production CORS cannot allow wildcard origins")
        if "*" in self.allowed_origins and not self.allow_wildcard:
            raise ValueError("wildcard origin requires allow_wildcard=True")
        return self


class RequestLimitPolicy(StrictBaseModel):
    """Planned request-size limits before middleware enforcement."""

    max_body_bytes: int = Field(ge=1)
    max_url_chars: int = Field(default=2_048, ge=1)
    max_icp_json_bytes: int = Field(ge=1)


class CriticalSecretPolicy(StrictBaseModel):
    """Critical secrets that should fail fast in production."""

    environment: DeploymentEnvironment
    required_env_vars: list[str] = Field(default_factory=list, max_length=30)
    optional_env_vars: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "CriticalSecretPolicy":
        if self.environment == "production" and "OPENAI_API_KEY" not in self.required_env_vars:
            raise ValueError("production must require OPENAI_API_KEY")
        return self


class RedactionPolicy(StrictBaseModel):
    """Fields that must not appear raw in logs, traces, or run metadata."""

    blocked_field_names: list[str] = Field(min_length=1, max_length=100)
    max_string_length: int = Field(default=2_000, ge=100)
    redact_contact_email: bool = True
    redact_outreach_body: bool = True
    redact_api_keys: bool = True


class AuditEventPolicy(StrictBaseModel):
    """Audit event category and retention intent."""

    event_name: str = Field(min_length=1, max_length=100)
    category: AuditEventCategory
    include_request_id: bool = True
    include_user_id: bool = True
    include_run_id: bool = True


class ComplianceConfigurationPlan(StrictBaseModel):
    """No-runtime-change Phase 6 compliance configuration matrix."""

    cors: tuple[CorsPolicy, ...]
    request_limits: RequestLimitPolicy
    secrets: tuple[CriticalSecretPolicy, ...]
    redaction: RedactionPolicy
    audit_events: tuple[AuditEventPolicy, ...]


COMPLIANCE_CONFIGURATION_PLAN = ComplianceConfigurationPlan(
    cors=(
        CorsPolicy(environment="development", allowed_origins=["*"], allow_wildcard=True),
        CorsPolicy(
            environment="staging",
            allowed_origins=["https://agent.hussainflow.com"],
        ),
        CorsPolicy(
            environment="production",
            allowed_origins=["https://agent.hussainflow.com"],
        ),
    ),
    request_limits=RequestLimitPolicy(max_body_bytes=128_000, max_icp_json_bytes=32_000),
    secrets=(
        CriticalSecretPolicy(
            environment="development",
            optional_env_vars=[
                "OPENAI_API_KEY",
                "TAVILY_API_KEY",
                "HUNTER_API_KEY",
                "SENDGRID_API_KEY",
                "SENDGRID_FROM_EMAIL",
                "POSTGRES_URL",
                "LANGFUSE_PUBLIC_KEY",
                "LANGFUSE_SECRET_KEY",
            ],
        ),
        CriticalSecretPolicy(
            environment="staging",
            required_env_vars=["OPENAI_API_KEY"],
            optional_env_vars=[
                "TAVILY_API_KEY",
                "HUNTER_API_KEY",
                "SENDGRID_API_KEY",
                "SENDGRID_FROM_EMAIL",
                "POSTGRES_URL",
                "LANGFUSE_PUBLIC_KEY",
                "LANGFUSE_SECRET_KEY",
            ],
        ),
        CriticalSecretPolicy(
            environment="production",
            required_env_vars=["OPENAI_API_KEY"],
            optional_env_vars=[
                "TAVILY_API_KEY",
                "HUNTER_API_KEY",
                "SENDGRID_API_KEY",
                "SENDGRID_FROM_EMAIL",
                "POSTGRES_URL",
                "LANGFUSE_PUBLIC_KEY",
                "LANGFUSE_SECRET_KEY",
            ],
        ),
    ),
    redaction=RedactionPolicy(
        blocked_field_names=[
            "api_key",
            "authorization",
            "contact.email",
            "email_body",
            "raw_provider_payload",
            "scraped_text",
            "retrieved_chunk_text",
        ],
    ),
    audit_events=(
        AuditEventPolicy(event_name="lead_qualified", category="lead_access"),
        AuditEventPolicy(event_name="lead_viewed", category="lead_access"),
        AuditEventPolicy(event_name="lead_approved", category="approval"),
        AuditEventPolicy(event_name="lead_rejected", category="approval"),
        AuditEventPolicy(event_name="email_delivery_attempted", category="email_delivery"),
        AuditEventPolicy(event_name="auth_context_resolved", category="auth"),
        AuditEventPolicy(event_name="security_policy_denied", category="security"),
    ),
)
