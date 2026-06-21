"""Phase 6 authentication and authorization planning contracts.

These models describe the intended auth boundary without enforcing runtime
authentication yet. They let future Phase 6 slices add checks deliberately
while preserving the current deployed prototype behavior.
"""

from typing import Literal

from pydantic import Field, model_validator

from saas_lead_agent.schemas.base import StrictBaseModel

AuthMode = Literal["anonymous_demo", "authenticated"]
UserRole = Literal["anonymous", "user", "admin"]
RouteSensitivity = Literal["public", "user_owned", "external_action"]
AccessAction = Literal["read", "write", "approve", "delete"]
OwnedResourceType = Literal[
    "lead_run",
    "source",
    "contact",
    "company_signal",
    "score_breakdown",
    "outreach_draft",
    "decision",
    "delivery_event",
    "retrieval_context",
]


class AuthContext(StrictBaseModel):
    """Request identity context before auth enforcement is wired in."""

    mode: AuthMode = "anonymous_demo"
    user_id: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    roles: list[UserRole] = Field(default_factory=lambda: ["anonymous"], max_length=10)

    @model_validator(mode="after")
    def validate_identity_for_mode(self) -> "AuthContext":
        if self.mode == "authenticated":
            if not self.user_id:
                raise ValueError("authenticated context requires user_id")
            if "anonymous" in self.roles:
                raise ValueError("authenticated context cannot include anonymous role")
        return self

    @property
    def is_authenticated(self) -> bool:
        """Return whether this context represents a real authenticated user."""

        return self.mode == "authenticated"


class ProtectedRoutePolicy(StrictBaseModel):
    """Planned access policy for one API route."""

    route_name: str = Field(min_length=1, max_length=100)
    path_template: str = Field(min_length=1, max_length=300)
    methods: list[str] = Field(min_length=1, max_length=5)
    sensitivity: RouteSensitivity
    requires_auth: bool
    allow_anonymous_demo: bool = True
    requires_human_approval: bool = False
    user_owned_resource: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_policy_consistency(self) -> "ProtectedRoutePolicy":
        normalized_methods = [method.upper() for method in self.methods]
        object.__setattr__(self, "methods", normalized_methods)
        if self.sensitivity in {"user_owned", "external_action"} and not self.requires_auth:
            if not self.allow_anonymous_demo:
                raise ValueError("sensitive routes must require auth outside anonymous demo mode")
        if self.sensitivity == "external_action" and not self.requires_human_approval:
            raise ValueError("external-action routes must require human approval")
        return self


class ResourceOwnershipPolicy(StrictBaseModel):
    """Planned ownership boundary for one app-owned data category."""

    resource_type: OwnedResourceType
    owner_field: str = Field(min_length=1, max_length=100)
    identifier_fields: list[str] = Field(min_length=1, max_length=5)
    allowed_actions: list[AccessAction] = Field(min_length=1, max_length=10)
    allow_legacy_unowned_demo_access: bool = True

    @model_validator(mode="after")
    def normalize_actions(self) -> "ResourceOwnershipPolicy":
        object.__setattr__(self, "allowed_actions", sorted(set(self.allowed_actions)))
        return self


class AccessDecision(StrictBaseModel):
    """Pure authorization decision for future repository/API enforcement."""

    allowed: bool
    reason: str = Field(min_length=1, max_length=300)


ROUTE_POLICIES: tuple[ProtectedRoutePolicy, ...] = (
    ProtectedRoutePolicy(
        route_name="qualify",
        path_template="/api/qualify",
        methods=["POST"],
        sensitivity="user_owned",
        requires_auth=False,
        allow_anonymous_demo=True,
        user_owned_resource="lead_run",
    ),
    ProtectedRoutePolicy(
        route_name="list_leads",
        path_template="/api/leads",
        methods=["GET"],
        sensitivity="user_owned",
        requires_auth=False,
        allow_anonymous_demo=True,
        user_owned_resource="lead_run",
    ),
    ProtectedRoutePolicy(
        route_name="get_lead",
        path_template="/api/leads/{thread_id}",
        methods=["GET"],
        sensitivity="user_owned",
        requires_auth=False,
        allow_anonymous_demo=True,
        user_owned_resource="lead_run",
    ),
    ProtectedRoutePolicy(
        route_name="get_lead_events",
        path_template="/api/leads/{thread_id}/events",
        methods=["GET"],
        sensitivity="user_owned",
        requires_auth=False,
        allow_anonymous_demo=True,
        user_owned_resource="run_event",
    ),
    ProtectedRoutePolicy(
        route_name="approve_lead",
        path_template="/api/leads/{thread_id}/approve",
        methods=["POST"],
        sensitivity="external_action",
        requires_auth=False,
        allow_anonymous_demo=True,
        requires_human_approval=True,
        user_owned_resource="lead_run",
    ),
    ProtectedRoutePolicy(
        route_name="reject_lead",
        path_template="/api/leads/{thread_id}/reject",
        methods=["POST"],
        sensitivity="user_owned",
        requires_auth=False,
        allow_anonymous_demo=True,
        user_owned_resource="lead_run",
    ),
)


RESOURCE_OWNERSHIP_POLICIES: tuple[ResourceOwnershipPolicy, ...] = (
    ResourceOwnershipPolicy(
        resource_type="lead_run",
        owner_field="user_id",
        identifier_fields=["thread_id", "run_id"],
        allowed_actions=["read", "write", "approve", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="source",
        owner_field="user_id",
        identifier_fields=["source_id", "thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="contact",
        owner_field="user_id",
        identifier_fields=["contact_id", "thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="company_signal",
        owner_field="user_id",
        identifier_fields=["signal_id", "thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="score_breakdown",
        owner_field="user_id",
        identifier_fields=["thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="outreach_draft",
        owner_field="user_id",
        identifier_fields=["thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="decision",
        owner_field="user_id",
        identifier_fields=["thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="delivery_event",
        owner_field="user_id",
        identifier_fields=["thread_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
    ResourceOwnershipPolicy(
        resource_type="retrieval_context",
        owner_field="user_id",
        identifier_fields=["document_id", "chunk_id", "run_id"],
        allowed_actions=["read", "write", "delete"],
    ),
)


def get_route_policy(route_name: str) -> ProtectedRoutePolicy | None:
    """Return the planned policy for an API route by stable route name."""

    return next((policy for policy in ROUTE_POLICIES if policy.route_name == route_name), None)


def get_resource_policy(resource_type: OwnedResourceType) -> ResourceOwnershipPolicy | None:
    """Return the planned ownership policy for one resource category."""

    return next(
        (policy for policy in RESOURCE_OWNERSHIP_POLICIES if policy.resource_type == resource_type),
        None,
    )


def can_access_resource(
    *,
    auth: AuthContext,
    resource_type: OwnedResourceType,
    resource_owner_id: str | None,
    action: AccessAction,
) -> AccessDecision:
    """Return the future access decision without enforcing it in routes yet."""

    policy = get_resource_policy(resource_type)
    if policy is None:
        return AccessDecision(allowed=False, reason="unknown resource type")
    if action not in policy.allowed_actions:
        return AccessDecision(allowed=False, reason="action is not allowed for resource type")
    if "admin" in auth.roles:
        return AccessDecision(allowed=True, reason="admin role")
    if auth.mode == "anonymous_demo":
        if resource_owner_id is None and policy.allow_legacy_unowned_demo_access:
            return AccessDecision(allowed=True, reason="legacy anonymous demo resource")
        return AccessDecision(allowed=False, reason="anonymous demo cannot access owned resource")
    if auth.user_id and auth.user_id == resource_owner_id:
        return AccessDecision(allowed=True, reason="resource owner match")
    return AccessDecision(allowed=False, reason="resource owner mismatch")
