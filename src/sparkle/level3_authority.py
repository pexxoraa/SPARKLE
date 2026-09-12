from __future__ import annotations


PYTHON_UNITTEST_AGENTS = frozenset({
    "coding",
    "software_engineering",
    "application_builder",
    "ai_builder",
    "agent_builder",
    "system",
})

CAPABILITY_AGENTS: dict[str, frozenset[str]] = {
    "python_unittest": PYTHON_UNITTEST_AGENTS,
}


def agent_authorized(agent: str, capability: str) -> bool:
    """Return whether a named agent has explicit Level-3 capability authority."""
    return agent in CAPABILITY_AGENTS.get(capability, frozenset())
