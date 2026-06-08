"""First-pass URL validation for server-side fetches.

This is not the final SSRF layer. Phase 6 should add DNS resolution checks,
redirect re-validation, and environment-specific allow/deny policy. This module
blocks obvious unsafe inputs before any scraper or graph work begins.
"""

from ipaddress import ip_address
from urllib.parse import urlparse, urlunparse

_MAX_URL_LENGTH = 2_048
_DANGEROUS_PORTS = {22, 25, 110, 143, 3306, 5432, 6379, 11211, 27017}
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "0", "0.0.0.0"}


def normalize_public_http_url(raw: str) -> str:
    """Return a stripped URL or raise ValueError for unsafe obvious inputs."""
    url = raw.strip()
    if not url:
        raise ValueError("url is required")
    if len(url) > _MAX_URL_LENGTH:
        raise ValueError("url must be 2048 characters or fewer")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            "url must be a fully-qualified HTTP/HTTPS URL (e.g. https://acme.example.com)"
        )

    if parsed.username or parsed.password:
        raise ValueError("url must not include credentials")

    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise ValueError("url must include a hostname")
    if host in _LOCAL_HOSTNAMES or host.endswith(".localhost"):
        raise ValueError("url hostname is not allowed")

    try:
        ip = ip_address(host)
    except ValueError:
        ip = None

    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("url IP address is not allowed")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("url port is invalid") from exc

    if port in _DANGEROUS_PORTS:
        raise ValueError("url port is not allowed")

    netloc_host = f"[{host}]" if ip is not None and ip.version == 6 else host
    netloc = f"{netloc_host}:{port}" if port is not None else netloc_host
    normalized = urlunparse((scheme, netloc, parsed.path or "", "", parsed.query, parsed.fragment))
    if normalized.endswith("/") and not parsed.query and not parsed.fragment:
        normalized = normalized.rstrip("/")
    return normalized
