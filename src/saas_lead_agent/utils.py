"""Shared utilities for the saas_lead_agent package."""

import json
from typing import Any


def _extract_json_list(content: str) -> list[dict[str, Any]]:
    """Extract a JSON array of dicts from an LLM response string.

    Same fence-stripping logic as ``_extract_json``, but validates a list
    rather than a dict.  An empty list ``[]`` is a valid return value.

    Args:
        content: Raw text from a final ``AIMessage``.

    Returns:
        Parsed list of dicts.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON.
        ValueError: If the parsed value is not a list, or any element is
            not a dict.
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
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(f"Expected array of objects, got {type(item).__name__} at index {i}")
    return parsed


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
