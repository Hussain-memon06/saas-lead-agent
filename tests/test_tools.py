"""Tests for web_search and scraper tools.

Both tools are invoked via .invoke() — the LangChain tool interface — so the
tests exercise the full decorator stack, not just the inner function.
All external I/O (Tavily API, httpx) is monkeypatched.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from saas_lead_agent.tools.scraper import scrape
from saas_lead_agent.tools.web_search import web_search

# ---------------------------------------------------------------------------
# web_search
# ---------------------------------------------------------------------------

_TAVILY_RESPONSE: dict[str, Any] = {
    "query": "Acme Corp",
    "results": [
        {
            "title": "Acme Corp – Home",
            "url": "https://acme.example.com",
            "content": "Acme Corp makes anvils for cartoons.",
            "score": 0.95,
        },
        {
            "title": "Acme Corp Funding",
            "url": "https://techcrunch.example.com/acme",
            "content": "Acme raised $10M Series A.",
            "score": 0.80,
        },
    ],
    "response_time": 0.42,
}


def test_web_search_returns_normalised_results(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = _TAVILY_RESPONSE
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    with patch("saas_lead_agent.tools.web_search.TavilyClient", return_value=mock_client):
        results: list[dict[str, Any]] = web_search.invoke({"query": "Acme Corp"})

    assert len(results) == 2
    first = results[0]
    assert first["title"] == "Acme Corp – Home"
    assert first["url"] == "https://acme.example.com"
    assert first["score"] == pytest.approx(0.95)
    assert isinstance(first["content"], str)


def test_web_search_respects_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = _TAVILY_RESPONSE
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    with patch("saas_lead_agent.tools.web_search.TavilyClient", return_value=mock_client):
        web_search.invoke({"query": "Acme Corp", "max_results": 3})

    mock_client.search.assert_called_once_with(
        query="Acme Corp",
        max_results=3,
        search_depth="basic",
        include_answer=False,
    )


def test_web_search_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(Exception, match="TAVILY_API_KEY"):
        web_search.invoke({"query": "Acme Corp"})


def test_web_search_wraps_tavily_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.search.side_effect = ValueError("quota exceeded")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    with patch("saas_lead_agent.tools.web_search.TavilyClient", return_value=mock_client):
        with pytest.raises(Exception, match="Tavily search failed"):
            web_search.invoke({"query": "Acme Corp"})


def test_web_search_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = {"results": []}
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    with patch("saas_lead_agent.tools.web_search.TavilyClient", return_value=mock_client):
        results = web_search.invoke({"query": "nonexistent company xyz"})

    assert results == []


# ---------------------------------------------------------------------------
# scraper
# ---------------------------------------------------------------------------

_SAMPLE_HTML = """
<html>
<head><title>Acme Corp</title></head>
<body>
  <nav>Nav link 1 Nav link 2</nav>
  <header>Header stuff</header>
  <main>
    <h1>Welcome to Acme Corp</h1>
    <p>We build great products for <strong>enterprises</strong>.</p>
    <p>Founded in 2020, headquartered in San Francisco.</p>
  </main>
  <script>alert('noise')</script>
  <style>.foo { color: red; }</style>
  <footer>Footer noise</footer>
</body>
</html>
"""


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.text = html
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def test_scraper_returns_clean_text() -> None:
    mock_html = _mock_response(_SAMPLE_HTML)
    with patch("saas_lead_agent.tools.scraper.httpx.get", return_value=mock_html):
        text: str = scrape.invoke({"url": "https://acme.example.com"})

    assert "Welcome to Acme Corp" in text
    assert "We build great products" in text
    assert "Founded in 2020" in text
    # Noise tags stripped
    assert "alert" not in text
    assert "color: red" not in text
    assert "Nav link" not in text
    assert "Footer noise" not in text
    assert "Header stuff" not in text


def test_scraper_sends_user_agent() -> None:
    mock_get = MagicMock(return_value=_mock_response(_SAMPLE_HTML))
    with patch("saas_lead_agent.tools.scraper.httpx.get", mock_get):
        scrape.invoke({"url": "https://acme.example.com"})

    call_kwargs = mock_get.call_args.kwargs
    assert "User-Agent" in call_kwargs["headers"]
    assert "Mozilla" in call_kwargs["headers"]["User-Agent"]


def test_scraper_truncates_at_20k_chars() -> None:
    large_html = "<p>" + ("A" * 30_000) + "</p>"
    with patch("saas_lead_agent.tools.scraper.httpx.get", return_value=_mock_response(large_html)):
        text = scrape.invoke({"url": "https://acme.example.com"})

    assert len(text) <= 20_000


def test_scraper_raises_on_http_error() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 403
    exc = httpx.HTTPStatusError("403 Forbidden", request=MagicMock(), response=mock_resp)

    with patch("saas_lead_agent.tools.scraper.httpx.get", side_effect=exc):
        with pytest.raises(Exception, match="HTTP 403"):
            scrape.invoke({"url": "https://acme.example.com"})


def test_scraper_raises_on_network_error() -> None:
    exc = httpx.ConnectError("Connection refused")

    with patch("saas_lead_agent.tools.scraper.httpx.get", side_effect=exc):
        with pytest.raises(Exception, match="Network error"):
            scrape.invoke({"url": "https://acme.example.com"})


def test_scraper_rejects_private_ip_before_fetch() -> None:
    with patch("saas_lead_agent.tools.scraper.httpx.get") as mock_get:
        with pytest.raises(Exception, match="IP address is not allowed"):
            scrape.invoke({"url": "http://127.0.0.1"})

    mock_get.assert_not_called()
