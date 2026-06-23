"""HTTP scraper tool: fetches a URL and returns cleaned plain text."""

import hashlib
import json
from time import perf_counter
from typing import Final
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from saas_lead_agent.schemas import normalize_public_http_url, resolve_public_http_target
from saas_lead_agent.tools.contracts import (
    ToolCallContext,
    ToolResult,
    ToolSpec,
    ToolTimeoutPolicy,
    completed_tool_result,
    failed_tool_result,
)
from saas_lead_agent.tools.recording import record_tool_result

_MAX_CHARS: Final[int] = 20_000
_MAX_REDIRECTS: Final[int] = 3
_REDIRECT_STATUSES: Final[set[int]] = {301, 302, 303, 307, 308}

# Realistic Chrome UA — many sites block requests without one (CLAUDE.md gotcha).
_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Tags that add noise without useful text content.
_NOISE_TAGS: Final[tuple[str, ...]] = ("script", "style", "nav", "footer", "header", "noscript")

SCRAPE_SPEC = ToolSpec(
    name="scrape",
    category="scrape",
    provider="httpx",
    description="Fetch and clean a public HTTP(S) page for company research.",
    timeout_policy=ToolTimeoutPolicy(timeout_ms=15_000, max_attempts=1),
)


@tool
def scrape(url: str) -> str:
    """Fetch a web page and return its cleaned plain-text content.

    Strips script, style, nav, footer, header, and noscript tags before
    extracting text. Output is capped at 20,000 characters so downstream
    LLM calls stay within context limits.

    Uses a realistic Chrome User-Agent header to avoid bot-detection blocks.

    Args:
        url: Fully-qualified URL to fetch (http or https).

    Returns:
        Cleaned plain text, at most 20,000 characters.

    Raises:
        RuntimeError: If the HTTP request fails (non-2xx status or network error).
    """
    result = run_scrape(url)
    record_tool_result(result)

    if result.metadata.status == "completed" and isinstance(result.output, str):
        return result.output

    if result.error is not None:
        if result.error.kind == "validation":
            raise ValueError(result.error.message)
        raise RuntimeError(result.error.message)

    raise RuntimeError("Unknown scraper failure")


def run_scrape(url: str) -> ToolResult:
    """Fetch and clean a page, returning a typed tool-result envelope."""
    context = ToolCallContext(input_hash=_input_hash(url=url))
    started_at = perf_counter()

    try:
        safe_url = normalize_public_http_url(url)
    except ValueError as exc:
        return failed_tool_result(
            spec=SCRAPE_SPEC,
            context=context,
            error_kind="validation",
            error_message=str(exc),
            duration_ms=_elapsed_ms(started_at),
        )

    try:
        response, safe_url = _get_with_safe_redirects(safe_url)
    except ValueError as exc:
        return failed_tool_result(
            spec=SCRAPE_SPEC,
            context=context,
            error_kind="validation",
            error_message=str(exc),
            duration_ms=_elapsed_ms(started_at),
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        return failed_tool_result(
            spec=SCRAPE_SPEC,
            context=context,
            error_kind="http_status",
            error_message=f"HTTP {status_code} fetching {safe_url}",
            duration_ms=_elapsed_ms(started_at),
            provider_status_code=status_code,
        )
    except httpx.RequestError:
        return failed_tool_result(
            spec=SCRAPE_SPEC,
            context=context,
            error_kind="network",
            error_message=f"Network error fetching {safe_url}",
            retryable=True,
            duration_ms=_elapsed_ms(started_at),
        )

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    text = " ".join(soup.stripped_strings)
    return completed_tool_result(
        spec=SCRAPE_SPEC,
        context=context,
        output=text[:_MAX_CHARS],
        duration_ms=_elapsed_ms(started_at),
    )


def _get_with_safe_redirects(url: str) -> tuple[httpx.Response, str]:
    current_url = url
    for redirect_count in range(_MAX_REDIRECTS + 1):
        current_url, addresses = resolve_public_http_target(current_url)
        response = _request_pinned(current_url, addresses[0])
        if response.status_code not in _REDIRECT_STATUSES:
            response.raise_for_status()
            return response, current_url
        if redirect_count == _MAX_REDIRECTS:
            raise ValueError("url exceeded the maximum redirect limit")
        location = response.headers.get("location")
        if not location:
            raise ValueError("url redirect is missing a location")
        current_url = urljoin(current_url, location)
    raise ValueError("url exceeded the maximum redirect limit")


def _request_pinned(url: str, address: str) -> httpx.Response:
    """Connect to a validated IP while preserving HTTP Host and TLS SNI."""
    parsed = urlparse(url)
    host = parsed.hostname
    if host is None:
        raise ValueError("url must include a hostname")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    address_host = f"[{address}]" if ":" in address else address
    default_port = 443 if parsed.scheme == "https" else 80
    connect_netloc = address_host if port == default_port else f"{address_host}:{port}"
    connect_url = urlunparse((parsed.scheme, connect_netloc, parsed.path, "", parsed.query, ""))
    host_header = host.encode("idna").decode("ascii")
    if parsed.port is not None and parsed.port != default_port:
        host_header = f"{host_header}:{parsed.port}"
    with httpx.Client(follow_redirects=False, timeout=15.0) as client:
        return client.request(
            "GET",
            connect_url,
            headers={"User-Agent": _USER_AGENT, "Host": host_header},
            extensions={"sni_hostname": host.encode("idna")},
        )


def _input_hash(*, url: str) -> str:
    raw = json.dumps({"url": url}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
