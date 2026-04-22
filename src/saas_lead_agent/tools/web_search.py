"""Tavily web-search tool exposed as a LangChain structured tool."""

import os
from typing import Any

from langchain_core.tools import tool
from tavily import TavilyClient


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
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY environment variable is not set")

    try:
        client = TavilyClient(api_key)
        response: dict[str, Any] = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Tavily search failed for query '{query}': {exc}") from exc

    return [
        {
            "title": str(r.get("title", "")),
            "url": str(r.get("url", "")),
            "content": str(r.get("content", "")),
            "score": float(r.get("score", 0.0)),
        }
        for r in response.get("results", [])
    ]
