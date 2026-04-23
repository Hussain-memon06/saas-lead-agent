"""Shared utilities for the saas_lead_agent package."""

import json
from typing import Any


def _extract_json(content: str) -> dict[str, Any]:
    """Extract a JSON dict from an LLM response string.

    Handles two common formats:
    - Plain JSON: ``{"name": "Acme", ...}``
    - Markdown-fenced JSON: `` ```json\\n{...}\\n``` ``

    Args:
        content: Raw text from a final ``AIMessage``.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON.
        ValueError: If the parsed value is not a ``dict``.
    """
    text = content.strip()

    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if "\n" in inner:
                inner = inner[inner.index("\n") :].strip()
            text = inner.strip()

    parsed: Any = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed
