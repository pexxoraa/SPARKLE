# Agent Builder

The Agent Builder turns bounded structured requirements into a provider-neutral
`SPARKLE-AGENT-BLUEPRINT/1` manifest. Agent definitions are data-driven
`AgentSpec` records, so installing a new generated agent does not change the
orchestrator, model adapters, memory, knowledge, tools, or interfaces.

Preparation validates exact fields and JSON size, purpose/capability/tool
contracts, unique routing keywords, workflow and guardrail bounds, and 1-20
evaluation fixtures. Each fixture must select the candidate with the same
deterministic scorer used by the production router while the registry remains
unchanged. Preparation reports `prepared_static_verified`; it explicitly
reports that semantic model evaluation and external deployment did not run.

Approved generated-agent manifests are validated, stored in
`data_environment/generated_agents.sqlite3`, hot-loaded into routing, and
reloaded at process startup. Each originating blueprint and its static evidence
form append-only build history in
`data_environment/agent_blueprints.sqlite3`, so an approved rebuild after
removal does not erase prior evidence. Unknown
fields or tools, invalid capabilities, duplicate fields or case names,
shadowed evaluation routes, duplicate agents, and attempts to replace built-in
agents are rejected before mutation. If blueprint persistence fails after the
agent manifest is written, installation is rolled back. Installation and
removal require explicit approval.

Create a structured requirements file with the exact fields below:

```json
{
  "name": "robotics_research",
  "capability": "reasoning",
  "purpose": "Research robotics systems with evidence and engineering constraints.",
  "tools": ["calculator", "knowledge_search"],
  "keywords": ["robotics research", "robot arm"],
  "workflow": ["Collect evidence.", "Cross-check sources.", "State uncertainty."],
  "guardrails": ["Never fabricate sources or completed tests."],
  "evaluations": [
    {"name": "robot_arm_evidence", "prompt": "Perform robotics research for a robot arm."}
  ]
}
```

Prepare without mutation, then approve the build:

```bash
sparkle agent-prepare requirements.json
sparkle agent-build requirements.json --approve
sparkle agent-remove robotics_research --approve
```

The equivalent HTTP operations are `POST /api/agents/prepare`,
`POST /api/agents/build`, and `GET /api/agent-blueprints`. The original
lower-level `agent-install` manifest command remains available for reviewed
manifests; `--replace` updates an existing generated definition.

The runtime does not yet turn unrestricted natural language into source code,
run live-model response-quality benchmarks, or deploy an external agent
service. Static routing success is not semantic-quality evidence. The verified
capability is structured requirements-to-manifest generation, deterministic
static evaluation, approval-gated installation, persistence, reload, and
routing—not fully autonomous agent engineering.
