import operator
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class LeadState(TypedDict):
    company_url: str
    domain: str
    messages: Annotated[list[AnyMessage], add_messages]
    company_profile: dict[str, Any] | None
    errors: Annotated[list[str], operator.add]
