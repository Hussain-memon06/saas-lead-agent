"""Local registry for typed tool specs.

This is intentionally a lightweight in-process registry. It gives future MCP,
durable execution, and provider fallback work one stable place to discover
tool metadata without adding a new runtime dependency.
"""

from saas_lead_agent.email.sendgrid_client import SENDGRID_DELIVERY_SPEC
from saas_lead_agent.tools.contracts import ToolSpec
from saas_lead_agent.tools.hunter import HUNT_CONTACT_SPEC
from saas_lead_agent.tools.scraper import SCRAPE_SPEC
from saas_lead_agent.tools.web_search import WEB_SEARCH_SPEC

_TOOL_SPECS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        WEB_SEARCH_SPEC,
        SCRAPE_SPEC,
        HUNT_CONTACT_SPEC,
        SENDGRID_DELIVERY_SPEC,
    )
}


def list_tool_specs() -> list[ToolSpec]:
    """Return the current typed tool specs in stable name order."""

    return [_TOOL_SPECS[name] for name in sorted(_TOOL_SPECS)]


def get_tool_spec(name: str) -> ToolSpec | None:
    """Return one tool spec by name, or None when unknown."""

    return _TOOL_SPECS.get(name)
