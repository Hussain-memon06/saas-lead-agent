"""Tool integrations and Phase 5 tool contract helpers."""

from saas_lead_agent.tools.contracts import (
    ToolCallContext,
    ToolCategory,
    ToolError,
    ToolErrorKind,
    ToolExecutionMetadata,
    ToolResult,
    ToolSpec,
    ToolStatus,
    ToolTimeoutPolicy,
    completed_tool_result,
    failed_tool_result,
)
from saas_lead_agent.tools.recording import capture_tool_results, record_tool_result
from saas_lead_agent.tools.registry import get_tool_spec, list_tool_specs

__all__ = [
    "ToolCallContext",
    "ToolCategory",
    "ToolError",
    "ToolErrorKind",
    "ToolExecutionMetadata",
    "ToolResult",
    "ToolSpec",
    "ToolStatus",
    "ToolTimeoutPolicy",
    "completed_tool_result",
    "capture_tool_results",
    "failed_tool_result",
    "get_tool_spec",
    "list_tool_specs",
    "record_tool_result",
]
