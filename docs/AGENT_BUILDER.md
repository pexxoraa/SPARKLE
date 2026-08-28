# Agent Builder

The Agent Builder specializes in purpose, capability, tool, memory, model,
workflow, guardrail, testing, and deployment requirements. Agent definitions are
data-driven `AgentSpec` records, so adding a new built-in agent does not change
the orchestrator.

Persisting user-generated agent definitions and hot-reloading them is not yet
implemented. Until it is tested, requests can produce a design but cannot be
claimed as deployed runtime agents.
