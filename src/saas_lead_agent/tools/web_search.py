"""Tavily web-search tool exposed as a LangChain structured tool."""

import hashlib
import json
import os
from time import perf_counter
from typing import Any

from langchain_core.tools import tool
from tavily import TavilyClient

from saas_lead_agent.tools.contracts import (
    ToolCallContext,
    ToolResult,
    ToolSpec,
    ToolTimeoutPolicy,
    completed_tool_result,
    failed_tool_result,
)
from saas_lead_agent.tools.recording import record_tool_result

WEB_SEARCH_SPEC = ToolSpec(
    name="web_search",
    category="search",
    provider="tavily",
    description="Search the web for company research and buying-signal evidence.",
    timeout_policy=ToolTimeoutPolicy(timeout_ms=15_000, max_attempts=1),
)


@tool
def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the web and return ranked results for a given query.

    Uses Tavily's search API. Results are sorted by relevance score descending.
    Reads TAVILY_API_KEY from the environment.

    Args:
        query: The search query string (e.g. "Acme Corp SaaS funding 2024").
        max_results: Maximum number of results to return (1–10, default 5).

    Returns:
        List of result dicts, each with keys:
          - title (str): Page title.
          - url (str): Source URL.
          - content (str): Short content snippet.
          - score (float): Relevance score in [0, 1].

    Raises:
        RuntimeError: If TAVILY_API_KEY is not set or the API call fails.
    """
    result = run_web_search(query=query, max_results=max_results)
    record_tool_result(result)

    if result.metadata.status == "completed":
        output = result.output
        return output if isinstance(output, list) else []

    if result.error is not None and result.error.kind == "configuration":
        raise RuntimeError("TAVILY_API_KEY environment variable is not set")

    error_message = result.error.message if result.error is not None else "unknown error"
    raise RuntimeError(f"Tavily search failed for query '{query}': {error_message}")


def run_web_search(query: str, max_results: int = 5) -> ToolResult:
    """Run Tavily search and return a typed tool-result envelope."""
    context = ToolCallContext(input_hash=_input_hash(query=query, max_results=max_results))
    started_at = perf_counter()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return failed_tool_result(
            spec=WEB_SEARCH_SPEC,
            context=context,
            error_kind="configuration",
            error_message="TAVILY_API_KEY environment variable is not set",
            duration_ms=_elapsed_ms(started_at),
        )

    try:
        client = TavilyClient(api_key)
        response: dict[str, Any] = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
        )
    except Exception:
        return failed_tool_result(
            spec=WEB_SEARCH_SPEC,
            context=context,
            error_kind="provider",
            error_message="Tavily search failed",
            retryable=True,
            duration_ms=_elapsed_ms(started_at),
        )

    output = [
        {
            "title": str(r.get("title", "")),
            "url": str(r.get("url", "")),
            "content": str(r.get("content", "")),
            "score": float(r.get("score", 0.0)),
        }
        for r in response.get("results", [])
    ]
    return completed_tool_result(
        spec=WEB_SEARCH_SPEC,
        context=context,
        output=output,
        duration_ms=_elapsed_ms(started_at),
    )


def _input_hash(*, query: str, max_results: int) -> str:
    raw = json.dumps(
        {"query": query, "max_results": max_results},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
