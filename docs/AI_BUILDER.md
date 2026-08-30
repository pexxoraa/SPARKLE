# AI System Builder

SPARKLE v0.21 implements a bounded provider-neutral AI System Blueprint
boundary. `SPARKLE-AI-SYSTEM-BLUEPRINT/1` converts exact structured
requirements into a deterministic architecture manifest and, with explicit
operator approval, materializes a two-file application workspace.

This boundary composes existing registries and stores. It does not call a
model, generate source code, run evaluations, or perform deployment. Those
claims remain explicitly false in every blueprint.

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

## Evidence and persistence

Blueprint attempts are stored separately in
`data_environment/ai_system_blueprints.sqlite3`. Retention is the latest 1,000
attempts; the public API returns at most 100 records. Successful records link
to the existing workspace build ID. Failed materialization stores only the
safe exception type, not source content or an exception message.

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

Natural-language requirements conversion, generated implementation code,
runtime semantic evaluation, provider-specific multimodal mapping, and real
deployment remain future increments.
