"""Phase 6 SSRF hardening policy contracts.

These models describe the future server-side fetch safety checks without
changing the current scraper/runtime behavior.
"""

from typing import Literal

from pydantic import Field, model_validator

from saas_lead_agent.schemas.base import StrictBaseModel

SsrfCheckName = Literal[
    "scheme",
    "credentials",
    "localhost",
    "private_ip",
    "link_local",
    "dangerous_port",
    "redirect",
    "dns_rebinding",
    "post_resolution",
]


class SsrfCheckPolicy(StrictBaseModel):
    """One planned SSRF safety check."""

    name: SsrfCheckName
    phase: Literal["pre_fetch", "redirect", "post_resolution"]
    blocks_request: bool = True
    description: str = Field(min_length=1, max_length=500)


class SsrfFetchPolicy(StrictBaseModel):
    """Planned fetch policy before deeper SSRF enforcement is wired in."""

    allowed_schemes: list[str] = Field(default_factory=lambda: ["http", "https"])
    blocked_hostnames: list[str] = Field(default_factory=list, max_length=50)
    blocked_ip_ranges: list[str] = Field(default_factory=list, max_length=50)
    dangerous_ports: list[int] = Field(default_factory=list, max_length=50)
    max_redirects: int = Field(default=3, ge=0, le=10)
    revalidate_each_redirect: bool = True
    require_post_resolution_check: bool = True
    checks: tuple[SsrfCheckPolicy, ...]

    @model_validator(mode="after")
    def validate_fetch_policy(self) -> "SsrfFetchPolicy":
        if "http" not in self.allowed_schemes or "https" not in self.allowed_schemes:
            raise ValueError("SSRF policy must allow only explicit HTTP/HTTPS schemes")
        check_names = {check.name for check in self.checks}
        required = {"redirect", "dns_rebinding", "post_resolution"}
        if not required.issubset(check_names):
            raise ValueError("SSRF policy must include redirect, DNS rebinding, and post-resolution checks")
        return self


SSRF_FETCH_POLICY = SsrfFetchPolicy(
    blocked_hostnames=["localhost", "localhost.localdomain", "0", "0.0.0.0"],
    blocked_ip_ranges=[
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ],
    dangerous_ports=[22, 25, 110, 143, 3306, 5432, 6379, 11211, 27017],
    checks=(
        SsrfCheckPolicy(
            name="scheme",
            phase="pre_fetch",
            description="Allow only HTTP and HTTPS URLs.",
        ),
        SsrfCheckPolicy(
            name="credentials",
            phase="pre_fetch",
            description="Reject URLs containing username or password components.",
        ),
        SsrfCheckPolicy(
            name="localhost",
            phase="pre_fetch",
            description="Reject localhost hostnames and aliases before fetch.",
        ),
        SsrfCheckPolicy(
            name="private_ip",
            phase="pre_fetch",
            description="Reject direct private, loopback, reserved, multicast, and unspecified IPs.",
        ),
        SsrfCheckPolicy(
            name="link_local",
            phase="pre_fetch",
            description="Reject link-local targets including cloud metadata addresses.",
        ),
        SsrfCheckPolicy(
            name="dangerous_port",
            phase="pre_fetch",
            description="Reject ports commonly used by mail, databases, caches, and SSH.",
        ),
        SsrfCheckPolicy(
            name="redirect",
            phase="redirect",
            description="Revalidate every redirect target before following it.",
        ),
        SsrfCheckPolicy(
            name="dns_rebinding",
            phase="post_resolution",
            description="Validate resolved addresses immediately before connection.",
        ),
        SsrfCheckPolicy(
            name="post_resolution",
            phase="post_resolution",
            description="Reject private/link-local/localhost resolved addresses after DNS lookup.",
        ),
    ),
)
