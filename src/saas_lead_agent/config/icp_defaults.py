"""Default Ideal Customer Profile (ICP) configuration.

The dossier_writer reads these constants to build a context block in its
system prompt, so the model scores against an explicit rubric and
returns a short, attribute-by-attribute explanation alongside the
numeric fit_score.

Hardcoded defaults for now — a future settings UI / per-user override
mechanism can replace ``DEFAULT_ICP`` with a database lookup without
touching the dossier_writer logic.
"""

from typing import TypedDict


class ICPConfig(TypedDict):
    """Shape of the rubric the dossier_writer scores against."""

    target_industries: list[str]
    target_stages: list[str]
    target_geographies: list[str]
    red_flags: list[str]
    ideal_signals: list[str]


DEFAULT_ICP: ICPConfig = {
    "target_industries": ["B2B SaaS", "Fintech", "Developer Tools"],
    "target_stages": ["Series A", "Series B", "Series C"],
    "target_geographies": ["US", "UK", "Canada", "EU"],
    "red_flags": ["pre-revenue", "consumer app", "gaming", "ecommerce"],
    "ideal_signals": [
        "recent funding",
        "hiring sales team",
        "product launch",
    ],
}


def format_icp_for_prompt(icp: ICPConfig = DEFAULT_ICP) -> str:
    """Render the ICP rubric as a bullet list for inclusion in a system prompt.

    Returns a multiline string with one labelled line per ICP dimension.
    """
    return (
        f"- Target industries: {', '.join(icp['target_industries'])}\n"
        f"- Target funding stages: {', '.join(icp['target_stages'])}\n"
        f"- Target geographies: {', '.join(icp['target_geographies'])}\n"
        f"- Ideal signals (boost score): {', '.join(icp['ideal_signals'])}\n"
        f"- Red flags (lower score): {', '.join(icp['red_flags'])}"
    )
