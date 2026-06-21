"""Tests for web_search and scraper tools.

Both tools are invoked via .invoke() — the LangChain tool interface — so the
tests exercise the full decorator stack, not just the inner function.
All external I/O (Tavily API, httpx) is monkeypatched.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from saas_lead_agent.tools import capture_tool_results
from saas_lead_agent.tools.scraper import _request_pinned, run_scrape, scrape
from saas_lead_agent.tools.web_search import run_web_search, web_search


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "saas_lead_agent.schemas.url.socket.getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", ("93.184.216.34", port))],
    )

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


def test_run_web_search_returns_typed_success_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = _TAVILY_RESPONSE
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    with patch("saas_lead_agent.tools.web_search.TavilyClient", return_value=mock_client):
        result = run_web_search(query="Acme Corp", max_results=3)

    assert result.metadata.tool_name == "web_search"
    assert result.metadata.category == "search"
    assert result.metadata.provider == "tavily"
    assert result.metadata.status == "completed"
    assert result.metadata.timeout_ms == 15_000
    assert result.context.input_hash is not None
    assert len(result.context.input_hash) == 64
    assert isinstance(result.output, list)
    assert len(result.output) == 2
    assert result.error is None


def test_run_web_search_returns_typed_configuration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = run_web_search(query="Acme Corp")

    assert result.metadata.status == "failed"
    assert result.error is not None
    assert result.error.kind == "configuration"
    assert result.error.retryable is False
    assert result.output is None


def test_web_search_records_sanitized_tool_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = _TAVILY_RESPONSE
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    with (
        patch("saas_lead_agent.tools.web_search.TavilyClient", return_value=mock_client),
        capture_tool_results(node="company_researcher", run_id="run-1") as records,
    ):
        results = web_search.invoke({"query": "Acme Corp", "max_results": 3})

    assert len(results) == 2
    assert records == [
        {
            "tool_name": "web_search",
            "category": "search",
            "provider": "tavily",
            "status": "completed",
            "duration_ms": records[0]["duration_ms"],
            "attempt": 1,
            "max_attempts": 1,
            "timeout_ms": 15_000,
            "node": "company_researcher",
            "run_id": "run-1",
            "input_hash": records[0]["input_hash"],
            "output_count": 2,
        }
    ]
    assert "content" not in records[0]
    assert "output" not in records[0]
    assert len(str(records)) < len(str(_TAVILY_RESPONSE))


def test_web_search_records_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with capture_tool_results(node="company_researcher") as records:
        with pytest.raises(Exception, match="TAVILY_API_KEY"):
            web_search.invoke({"query": "Acme Corp"})

    assert records[0]["tool_name"] == "web_search"
    assert records[0]["status"] == "failed"
    assert records[0]["error_kind"] == "configuration"
    assert records[0]["retryable"] is False
    assert "error_message" not in records[0]


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
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


def test_scraper_returns_clean_text() -> None:
    mock_html = _mock_response(_SAMPLE_HTML)
    with patch("saas_lead_agent.tools.scraper._request_pinned", return_value=mock_html):
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


def test_run_scrape_returns_typed_success_result() -> None:
    with patch(
        "saas_lead_agent.tools.scraper._request_pinned",
        return_value=_mock_response(_SAMPLE_HTML),
    ):
        result = run_scrape("https://acme.example.com")

    assert result.metadata.tool_name == "scrape"
    assert result.metadata.category == "scrape"
    assert result.metadata.provider == "httpx"
    assert result.metadata.status == "completed"
    assert result.metadata.timeout_ms == 15_000
    assert result.context.input_hash is not None
    assert len(result.context.input_hash) == 64
    assert isinstance(result.output, str)
    assert "Welcome to Acme Corp" in result.output
    assert result.error is None


def test_run_scrape_returns_typed_validation_failure() -> None:
    result = run_scrape("http://127.0.0.1")

    assert result.metadata.status == "failed"
    assert result.error is not None
    assert result.error.kind == "validation"
    assert "IP address is not allowed" in result.error.message
    assert result.output is None


def test_scraper_records_sanitized_tool_usage() -> None:
    with (
        patch(
            "saas_lead_agent.tools.scraper._request_pinned",
            return_value=_mock_response(_SAMPLE_HTML),
        ),
        capture_tool_results(node="company_researcher", run_id="run-1") as records,
    ):
        text = scrape.invoke({"url": "https://acme.example.com"})

    assert "Welcome to Acme Corp" in text
    assert records == [
        {
            "tool_name": "scrape",
            "category": "scrape",
            "provider": "httpx",
            "status": "completed",
            "duration_ms": records[0]["duration_ms"],
            "attempt": 1,
            "max_attempts": 1,
            "timeout_ms": 15_000,
            "node": "company_researcher",
            "run_id": "run-1",
            "input_hash": records[0]["input_hash"],
            "output_count": 1,
        }
    ]
    assert "Welcome to Acme Corp" not in str(records)
    assert "output" not in records[0]


def test_scraper_pins_validated_ip_with_original_host_and_sni() -> None:
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = _mock_response(_SAMPLE_HTML)
    with patch("saas_lead_agent.tools.scraper.httpx.Client", return_value=mock_client):
        _request_pinned("https://acme.example.com/about", "93.184.216.34")

    args = mock_client.request.call_args.args
    kwargs = mock_client.request.call_args.kwargs
    assert args == ("GET", "https://93.184.216.34/about")
    assert kwargs["headers"]["Host"] == "acme.example.com"
    assert "Mozilla" in kwargs["headers"]["User-Agent"]
    assert kwargs["extensions"] == {"sni_hostname": b"acme.example.com"}


def test_scraper_truncates_at_20k_chars() -> None:
    large_html = "<p>" + ("A" * 30_000) + "</p>"
    with patch(
        "saas_lead_agent.tools.scraper._request_pinned",
        return_value=_mock_response(large_html),
    ):
        text = scrape.invoke({"url": "https://acme.example.com"})

    assert len(text) <= 20_000


def test_scraper_raises_on_http_error() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 403
    exc = httpx.HTTPStatusError("403 Forbidden", request=MagicMock(), response=mock_resp)

    with patch("saas_lead_agent.tools.scraper._request_pinned", side_effect=exc):
        with pytest.raises(Exception, match="HTTP 403"):
            scrape.invoke({"url": "https://acme.example.com"})


def test_scraper_raises_on_network_error() -> None:
    exc = httpx.ConnectError("Connection refused")

    with patch("saas_lead_agent.tools.scraper._request_pinned", side_effect=exc):
        with pytest.raises(Exception, match="Network error"):
            scrape.invoke({"url": "https://acme.example.com"})


def test_scraper_rejects_private_ip_before_fetch() -> None:
    with patch("saas_lead_agent.tools.scraper._request_pinned") as mock_request:
        with pytest.raises(Exception, match="IP address is not allowed"):
            scrape.invoke({"url": "http://127.0.0.1"})

    mock_request.assert_not_called()


def test_scraper_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "saas_lead_agent.schemas.url.socket.getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", ("127.0.0.1", port))],
    )
    with patch("saas_lead_agent.tools.scraper._request_pinned") as mock_request:
        result = run_scrape("https://acme.example.com")

    assert result.metadata.status == "failed"
    assert result.error is not None
    assert result.error.kind == "validation"
    assert "non-public IP" in result.error.message
    mock_request.assert_not_called()


def test_scraper_revalidates_redirect_target_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(host: str, port: int, **kwargs: Any) -> list[tuple[Any, ...]]:
        address = "127.0.0.1" if host == "internal.example.com" else "93.184.216.34"
        return [(2, 1, 6, "", (address, port))]

    redirect = _mock_response("", status_code=302)
    redirect.headers = {"location": "http://internal.example.com/admin"}
    monkeypatch.setattr("saas_lead_agent.schemas.url.socket.getaddrinfo", resolve)
    with patch(
        "saas_lead_agent.tools.scraper._request_pinned",
        return_value=redirect,
    ) as mock_request:
        result = run_scrape("https://acme.example.com")

    assert result.metadata.status == "failed"
    assert result.error is not None
    assert result.error.kind == "validation"
    assert "non-public IP" in result.error.message
    assert mock_request.call_count == 1
