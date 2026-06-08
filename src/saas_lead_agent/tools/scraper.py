"""HTTP scraper tool: fetches a URL and returns cleaned plain text."""

from typing import Final

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from saas_lead_agent.schemas import normalize_public_http_url

_MAX_CHARS: Final[int] = 20_000

# Realistic Chrome UA — many sites block requests without one (CLAUDE.md gotcha).
_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Tags that add noise without useful text content.
_NOISE_TAGS: Final[tuple[str, ...]] = ("script", "style", "nav", "footer", "header", "noscript")


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
    safe_url = normalize_public_http_url(url)

    try:
        response = httpx.get(
            safe_url,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"HTTP {exc.response.status_code} fetching {safe_url}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Network error fetching {safe_url}: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    text = " ".join(soup.stripped_strings)
    return text[:_MAX_CHARS]
