# AI System Builder

SPARKLE implements a bounded provider-neutral AI System Blueprint boundary.
`SPARKLE-AI-SYSTEM-BLUEPRINT/1` converts exact structured
requirements into a deterministic architecture manifest and, with explicit
operator approval, materializes a two-file application workspace.

The Blueprint boundary itself composes existing registries and stores without
calling a model. v0.24 added a separate approval-gated
`SPARKLE-AI-SYSTEM-DRAFT/1` boundary that can ask the configured model router
to convert bounded natural language into the exact structured contract. It
does not generate source code, run semantic evaluations, or perform deployment.
v0.25 adds deterministic `SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1` derivation
from a revalidated Blueprint. The plan is human-reviewable and can be
materialized separately, but source generation and every execution claim
remain explicitly false.
v0.26 adds bounded `SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1` generation. It
requires plan review, separately approved provider disclosure, generation
approval, explicit human source review, non-executing static verification, and
separate final candidate approval. Candidates never enter production source.
v0.27 adds `SPARKLE-AI-SYSTEM-RUNTIME-EVALUATION/1` for explicitly approved
candidates. It prepares a separate bounded evaluation bundle and can submit it
only through the existing authenticated external-worker client. The current
environment provides contract evidence, not live isolated-runtime evidence.
v0.28 adds `SPARKLE-AI-SYSTEM-SOURCE-PROMOTION/1`. A separate post-evaluation
approval binds exact candidate, plan, evaluation, actor, and origin identity
before exact source is atomically materialized into controlled staging. It
does not build, package, publish, deploy, or modify production source.
v0.29 adds `SPARKLE-AI-SYSTEM-CONTROLLED-BUILD/1`. A separate build approval
binds the exact completed promotion digest, actor, and origin before the staged
tree can become a deterministic content-addressed source-bundle artifact. The
builder revalidates promotion lineage and staged content, but does not import
or execute source, publish the artifact, deploy, or modify production source.

v0.30 adds `SPARKLE-AI-SYSTEM-CONTROLLED-EXECUTION/1`. A successful build does
not authorize execution. A separate expiring authorization binds the full
authoritative lineage, immutable artifact identity, execution mode, timeout,
output bound, actor, and origin. The execution controller verifies and extracts
only that artifact, submits through the existing authenticated worker, records
explicit lifecycle and failure states, and verifies the signed result. It does
not publish, deploy, replace production, or turn `executed` into `deployed`.

CLI operations are `ai-system-execution-approve`,
`ai-system-controlled-execute`, `ai-system-execution-cancel`, and
`ai-system-controlled-executions`. API operations are
`POST /api/ai-systems/execution/approve`, `/request`, `/cancel`, and
`GET /api/ai-system-controlled-executions`.

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

## Implementation planning

Create a non-mutating deterministic implementation plan from the same exact
structured requirements:

```bash
sparkle ai-system-plan requirements.json
```

Materialize only the plan manifest with separate explicit approval:

```bash
sparkle ai-system-plan-build requirements.json --approve
```

Equivalent authenticated HTTP endpoints are:

- `POST /api/ai-systems/plan`
- `POST /api/ai-systems/plan/build`
- `GET /api/ai-system-plans`

The planner re-runs the complete Blueprint validator. It removes resolved
provider/model identities from its architecture inputs and retains only
capability and modality requirements, selected agents/tools/environments, and
interfaces. It deterministically proposes confined unique Python interface and
evaluation paths, then orders contract review, core composition, interface
adapters, evaluation harness, and release review with explicit dependencies and
acceptance gates.

Preparation changes no workspace or evidence store. Approved materialization
adds only `SPARKLE_IMPLEMENTATION_PLAN.json` to the bounded application
workspace with overwrite disabled. It can coexist with the Blueprint's
`README.md` and `SPARKLE_AI_SYSTEM.json`. The proposed source and test paths are
plan records only; they are not written. Materialization approval is permission
to write the plan, not evidence that a human completed review or approved
future source generation.

## Source-candidate generation

The generation lifecycle is deliberately discontinuous:

```text
MATERIALIZED PLAN → REVIEWED PLAN → PROVIDER DISCLOSURE PENDING
→ PROVIDER DISCLOSURE APPROVED → GENERATED/HUMAN REVIEW REQUIRED
→ REVIEWED → STATICALLY VERIFIED → APPROVED CANDIDATE
```

Each approval is explicit. Generation uses the Application Builder through the
common model router and isolated evaluation profile. The response must be one
duplicate-free `SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1` JSON object linked to the
exact plan digest, with 1–20 UTF-8 files and at most 256,000 total bytes. Every
path must already appear in the approved plan's proposed source files.

Provider disclosure is prepared and stored independently before generation. It
records provider, model, registry identifier, timestamp, bounded generation
task, related plan/candidate identifiers, generated path labels, and status.
It never stores credentials or source. A current router selection that differs
from the approved disclosure fails closed, as does missing or inconsistent
metadata on the model response.

Candidate files and `SPARKLE_SOURCE_CANDIDATE.json` are written only under
`candidate_environment/source_candidates/candidate-NNNNNN/`, not the bounded
application workspace, repository, artifacts, or deployment area. Human review
stores only a digest of bounded notes. Static verification revalidates the
requirements and plan, candidate paths, manifest and digests, then applies
syntax/configuration, import/reference, dependency, formatting, and security
pattern checks where supported. JavaScript `--check` receives a minimal
environment; Python uses AST parsing and is never imported.

CLI and authenticated API operations keep review, disclosure approval,
generation, human review, verification, and final approval separate. Listing
surfaces expose content-free evidence. Reading one declared candidate file is
an explicit review operation; no endpoint promotes it.

`STATICALLY VERIFIED` means only that the recorded non-executing checks passed.
It never means runtime tested, semantically correct, worker-isolated,
production-ready, published, or deployed.

## Runtime evaluation

The exact contract records candidate and plan IDs, requested capabilities, a
fixed Python/unittest runtime, bounded JSON input data, expected behavior,
timeout/output limits, named criteria, bounded `tests/test_*.py` harness files,
and `SPARKLE-RUNTIME-RESULT/1`. Unknown fields, shell/command runtimes, path
traversal, duplicate paths, invalid limits, unapproved candidates, and plan
mismatches fail closed.

Without approval, no evaluation exists (`NOT_REQUESTED`). An approved valid
request follows `REQUESTED → QUEUED → SUBMITTED → RUNNING → COMPLETED →
EVALUATED`. Approved invalid requests become `REQUESTED → REJECTED`. Separate
terminal states preserve `FAILED_TO_START`, `TIMEOUT`, `WORKER_UNAVAILABLE`,
`PROTOCOL_FAILURE`, `EXECUTION_FAILURE`, and `EVALUATION_FAILURE`.

The evaluator copies only approved candidate files plus the explicit harness
into `runtime_environment/evaluations/<evaluation-id>`. It never modifies the
candidate, application workspace, repository, artifact store, or deployment
records. The existing worker client performs HTTPS/HMAC request and response
authentication, body integrity, timestamp freshness, response identity/schema
validation, size bounds, and worker-side replay/conflict protection. Contract
timeout and output limits are included in the signed request.

Persisted results contain identifiers, lifecycle, return code, timeout and
duration, bounded output digest/length, criterion booleans, worker/runtime
labels, response-verification state, safe failure type, and trace linkage—not
source, harness content, inputs, expected behavior, output, credentials, or
review text. `RUNTIME VERIFIED` means the authenticated worker returned a
successful fixed-test result and all declared criteria passed. It does not mean
production verified or deployed. `isolation_verified` remains false unless
separate executable hostile-canary evidence proves the deployed worker.

Controlled execution now binds `SPARKLE-CONTROLLED-EXECUTION-POLICY/1`, pins
the configured worker ID, enforces its lifecycle graph, exposes content-free
single-execution status/result inspection, and mounts the verified artifact
read-only in the Bubblewrap profile. None of those software checks converts the
local process harness into Level 3 evidence.

## Controlled source promotion

Promotion is a separate operator action after runtime evaluation:

```text
APPROVED CANDIDATE → SUCCESSFUL RUNTIME EVALUATION
→ PROMOTION APPROVAL → PROMOTION REQUEST → PROMOTING → PROMOTED → STOP
```

Candidate approval and runtime success do not imply promotion approval. The
promotion approval expires after 24 hours and binds candidate ID/digest, plan
ID/digest, evaluation ID/contract digest, actor, and request origin. CLI and
authenticated API origins are explicit and must match the approval.

`SPARKLE-AI-SYSTEM-SOURCE-PROMOTION/1` requires a unique request ID and repeats
those identities rather than trusting caller metadata. The service re-reads
the authoritative candidate, plan, evaluation, approval, and exclusion stores;
recomputes every candidate file byte count and SHA-256; checks the canonical
candidate digest and manifest; and refuses failed evaluations, mismatches,
stale approvals, invalidated or superseded candidates, traversal, conflicts,
and overwrite.

The only destination is
`promotion_environment/staging/<candidate-system-name>`. A private exclusive
lock serializes the destination. Files are written exactly into a temporary
directory with exclusive creation, verified against the source digest, renamed
atomically without an allowed overwrite, then re-read and verified. Failures
remove only partial materialization created by that attempt. Failed attempts
require a new explicit approval before retry.

Persisted requested, promoting, promoted, rejected, and failed events are
content-free. Traces include identifiers, actor/origin, destination, digests,
resulting promoted-source identity, timestamps, lifecycle, and bounded failure
class. They never contain candidate source, runtime output, review notes, API
tokens, signing material, or credentials.

`PROMOTED` means exact evaluated source exists in controlled staging. It does
not mean built, executed, packaged, published, production verified, deployed,
or isolated. All those flags remain false and the workflow stops.

CLI:

- `ai-system-promotion-approve`
- `ai-system-promote`
- `ai-system-promotion-exclude`
- `ai-system-promotions`

Authenticated API:

- `POST /api/ai-systems/promotion/approve`
- `POST /api/ai-systems/promotion/request`
- `POST /api/ai-systems/promotion/exclude`
- `GET /api/ai-system-source-promotions`

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

Implementation-plan attempts are stored separately in
`data_environment/ai_system_implementation_plans.sqlite3`, retaining the latest
1,000 attempts and returning at most 100. Evidence contains only system name,
Blueprint and plan-body digests, plan byte count, status, workspace build ID,
timestamps, and safe error type. Purpose, workflow, criteria, plan content, and
source are excluded. The plan digest scope is the canonical plan before its
`plan_sha256` field is added, avoiding a self-referential digest.

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

Natural-language conversion and bounded candidate generation are locally
verified with deterministic injected adapters; implementation-plan derivation
is deterministic and provider neutral. Runtime-evaluation contracts and the
authenticated worker boundary have deterministic integration evidence. Live
live-provider conversion, semantic fidelity of generated content, an actual human
review, a named isolated-worker evaluation, provider-specific multimodal
mapping, production build/package/publish, and real deployment remain
incomplete. Controlled staging promotion is not production promotion.
