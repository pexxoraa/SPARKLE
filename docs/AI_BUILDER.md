# AI System Builder

SPARKLE implements a bounded provider-neutral AI System Blueprint boundary.
`SPARKLE-AI-SYSTEM-BLUEPRINT/1` converts exact structured
requirements into a deterministic architecture manifest and, with explicit
operator approval, materializes a two-file application workspace.

The Blueprint boundary itself composes existing registries and stores without
calling a model. v0.24 adds a separate approval-gated
`SPARKLE-AI-SYSTEM-DRAFT/1` boundary that can ask the configured model router
to convert bounded natural language into the exact structured contract. It
does not generate source code, run semantic evaluations, or perform deployment.
Those claims remain explicitly false.

## Requirements contract

The root object accepts only these fields:

```json
{
  "name": "robotics_ai",
  "purpose": "Research robotics evidence and produce bounded analytical outputs.",
  "model_requirements": [
    {"capability": "reasoning", "modalities": ["text"]}
  ],
  "agents": ["research", "data_analysis"],
  "tools": ["calculator", "knowledge_search"],
  "data_environments": [
    "knowledge_environment",
    "data_environment",
    "trace_environment"
  ],
  "interfaces": ["text", "api", "dashboard"],
  "workflow": [
    "Collect bounded evidence from approved sources.",
    "Analyze evidence with the selected specialist agents.",
    "Return a traceable result and preserve evaluation evidence."
  ],
  "evaluations": [
    {
      "name": "robotics_integration",
      "kind": "integration",
      "criterion": "The system preserves source and trace boundaries."
    }
  ],
  "deployment": {
    "environment_name": "staging",
    "target_kind": "server"
  }
}
```

Model requirements use capability roles and content modalities, never a
provider or model name. Preparation resolves each requirement against enabled
records in the current model registry. The selected record must advertise the
role and every requested modality. This validates routing availability without
constructing an adapter or making a provider request.

Agents and tools must already exist in their registries. Every requested tool
must be allowed by at least one selected agent. Data environments are limited
to the separate memory, knowledge, data, and trace environments. Deployment
targets reuse the application artifact target vocabulary and remain
`planned_unverified`.

The complete JSON input is bounded to 64,000 bytes. Collection sizes, string
lengths, identifiers, duplicates, unknown fields, evaluation kinds, and
deployment labels are validated before any persistent mutation.

## Prepare and materialize

Preparation is deterministic and non-mutating:

```bash
sparkle ai-system-prepare requirements.json
```

Materialization requires explicit approval:

```bash
sparkle ai-system-build requirements.json --approve
```

Equivalent authenticated HTTP endpoints are:

- `POST /api/ai-systems/prepare`
- `POST /api/ai-systems/build`
- `GET /api/ai-system-blueprints`

The approved build creates `README.md` and `SPARKLE_AI_SYSTEM.json` in the
bounded application workspace with overwrite disabled. The canonical JSON
manifest has deterministic key ordering and a final newline.

## Natural-language draft conversion

Natural-language conversion reads a UTF-8 requirements file and requires
explicit approval because its content is sent to the configured model provider:

```bash
sparkle ai-system-draft requirements.txt --approve
```

The equivalent authenticated HTTP endpoints are:

- `POST /api/ai-systems/draft`
- `GET /api/ai-system-drafts`

The compiler derives the current allowed model capabilities/modalities,
installed agents and their tool boundaries, data environments, interfaces,
evaluation kinds, and deployment target vocabulary from the existing
registries. It invokes the Application Builder through the common orchestrator
using the isolated evaluation profile: no history, user identity,
memory/knowledge context, or tools are available. A tool request fails closed.

The provider response must be one exact JSON object. Markdown fences, duplicate
keys, extra fields, unknown agents/tools, inaccessible tools, provider-specific
fields, invalid routes, and every existing Blueprint schema or size violation
are rejected before the draft is returned. Successful output includes the
generated structured requirements and the independently prepared Blueprint;
it does not materialize a workspace.

## Evidence and persistence

Blueprint attempts are stored separately in
`data_environment/ai_system_blueprints.sqlite3`. Retention is the latest 1,000
attempts; the public API returns at most 100 records. Successful records link
to the existing workspace build ID. Failed materialization stores only the
safe exception type, not source content or an exception message.

Draft attempts are stored separately in
`data_environment/ai_system_drafts.sqlite3`, retaining the latest 1,000 records
and returning at most 100. Evidence contains only status, input byte count,
response digest/length, bounded provider/model labels, trace ID, and safe error
type. Natural-language input and generated JSON are not persisted in the draft
store. The trace uses a generic evaluation summary and does not store raw input
or output.

Static checks prove requirements shape, model capability/modality routing,
agent and tool references, agent tool access, environment separation,
evaluation schema, and deployment schema. They do not prove response quality,
runtime integration, provider availability, or a deployed target.

The following output fields preserve that boundary:

```json
{
  "status": "prepared_static_verified",
  "model_calls_executed": false,
  "runtime_evaluation_executed": false,
  "external_deployment_executed": false
}
```

Natural-language conversion is locally verified with deterministic injected
adapters. Live MiniMax conversion, semantic fidelity of the resulting draft,
generated implementation code, runtime semantic evaluation, provider-specific
multimodal mapping, and real deployment remain incomplete.
