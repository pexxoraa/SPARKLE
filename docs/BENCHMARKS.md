# Retrieval and agent outcome benchmarks

## Scope and execution

This is a credential-free evaluation milestone. It does not establish autonomous
agent intelligence, live NVIDIA access, real embedding quality, Level 3 isolation,
or deployment readiness. Ordinary application requests still use lexical search.
Independent validation is an explicit post-execution evaluation stage, not an
automatic certificate attached to every chat answer.

```bash
PYTHONPATH=src python -m benchmarks.run --output-dir /path/to/benchmark-output
PYTHONPATH=src python -m unittest tests.test_benchmarks tests.test_system_e2e tests.test_knowledge_retrieval -v
make check
```

The runner creates isolated temporary SQLite databases and harmless files, runs
real retrieval/tools/orchestration, independently reads outcome state, and cleans
up. It restores SPARKLE_DATA_DIR on completion/failure. Do not invoke it concurrently
inside a running application process: its temporary configuration is process-wide.
There are no external requests in the default mode. Reports contain synthetic
fixture data, not real user memory. Execution timestamps/random trace identities
are excluded for reproducibility; trace completion is observed from the real local
trace store. Dataset and implementation SHA-256 hashes bind recorded results.

Versioned corpus, tasks, runner, gates and [recorded evidence](../benchmarks/evidence/REPORT.md)
live in `benchmarks/`. The JSON result contains each query's relevance/ranking,
per-class metrics, failures, context metrics, each task's observations and criteria,
and independent validation decisions. Identical runs must reproduce it byte for
byte. CI runs the full suite on Python 3.12/3.13, regenerates both reports, compares
them with the recorded versions, and includes the human report in its job summary.

## Retrieval judgments and metrics

`corpus.json` version sparkle-retrieval-1 contains 12 manually authored synthetic
sources, 14 exact chunks and 16 queries. Stable source/position identifiers map to
actual SQLite chunk IDs after ingestion; mismatches fail. It includes title-only,
accent/case, Japanese, multiple relevant chunks, repeated-word distractors,
paraphrases and cross-language cases. Relevance judgments were written before
running the benchmark. Challenge judgments express desirable conceptual matches,
not promises made by lexical search. Four lexical misses at K=5 remain visible.

- Recall@K: for each query, distinct relevant chunks in the first K results divided
  by all judged relevant chunks; then macro-average over queries.
- Hit@K: fraction of queries with at least one relevant chunk in the first K. This
  is the any-hit definition sometimes called recall; it is reported separately.
- MRR: mean reciprocal rank of the first relevant chunk in the top 50; zero if none.
  The corpus has only 14 chunks, so this covers every possible result here.
- Ties: lexical and semantic use chunk ID ascending; hybrid uses the same tie rule.
- Scores are rounded to six decimals for reporting. They are not confidence values.

Frozen lexical floors: Recall@1 0.625, Recall@3/5 0.75, MRR 0.71875. Comparison
allows only half a last printed decimal of rounding tolerance. Every required
query must hit at rank 1 and retrieve all its relevant chunks by rank 5. No query's
first-relevant rank may worsen relative to the recorded baseline. An empty ranker
must fail. Corpus hash changes require explicit review/versioning. Do not lower
gates or relabel hard queries to hide regression. To change the corpus or scoring,
review judgments and gates, then deliberately regenerate evidence; the runner
never rewrites regression thresholds.

## Replaceable embedding and hybrid experiments

`EmbeddingProvider` exposes identity, dimensions and batch embedding. It is
independent of model providers and knowledge ingestion. `SemanticRetriever`
validates finite dimensions/counts, normalizes cosine vectors, preserves authoritative
source/chunk identity and caps the corpus (default 1000 chunks, maximum 10000).
Text sent to an explicitly supplied provider is bounded to 16384 characters per
item. Operators must authorize such data transfer; no external provider is selected
by default. There is no vector persistence/cache or production-scale claim.

`HashingTestEmbeddings` is a **TEST DOUBLE**: hashed tokens, not a trained semantic
model. The semantic-test-double and hybrid-test-double numbers measure plumbing
only. Small apparent paraphrase gains can be hash collisions or common words.
They do not establish semantic quality. Real embedding-provider evaluation remains
pending. Unknown malformed vectors fail; the hybrid adapter records unavailable
semantic evidence and explicitly falls back to the existing lexical retriever.
Hybrid uses equal-weight reciprocal-rank fusion with constant 60 over two top-50
lists. It is opt-in and does not replace the normal lexical path.

The class table shows lexical leading the embedding double on Unicode; the hybrid
double retains lexical Recall@1/3/5 and raises MRR slightly through low-ranked
paraphrase matches. Four conceptual misses still remain at K=5. There is no evidence
here justifying a production retriever switch.

## Context trust and quality

Previously, retrieved text was appended to the system prompt. It now travels as
an explicitly untrusted JSON user message, separately from fixed system guidance
and the actual user request. Other agents' work also uses a lower-trust user
message. Retrieved strings cannot select message roles. This is structural trust
separation, not a proof that any particular model resists prompt injection.

Context carries source ID, chunk ID, position, title and text. It includes at most
five knowledge chunks and five memories, with bounded excerpts and a 12000-byte
serialized budget; tail items are omitted when necessary. Context recall is
measured after serialization, separately from answer quality. The hostile-text
HTTP test verifies the payload is absent from system instructions and metadata
survives. Tool allowlists, approval gates and worker boundaries remain unchanged.

## Agent outcomes and independent validation

`tasks.json` defines three tasks each for Personal, Research, Learning and Coding.
They exercise calculation, explicit durable memory, cited retrieval, empty evidence,
read-only Python constant inspection, approved non-executing syntax-error detection
and rejection of unsafe expressions/path
escape. No generated application, code patch, tests executed by an agent, or teaching
quality is claimed. The default model is a visibly named scripted test harness:
its tool plan is prescribed; its response is derived from actual tool results.
It never reads the expected answer/criteria. Autonomous tool selection is unverified.

The evaluator separately records:

- execution success: orchestrator returned;
- protocol success: response is a JSON object;
- outcome correctness: execution/protocol succeeded and every criterion validated;
- validation: validated, rejected or inconclusive; independent of trace completion.

Criteria come from the trusted versioned task fixture, not the agent response.
Actual tool names/arguments/errors and persisted memory/file state are observed
outside the model. Returned citations must be grounded in tool retrieval results.
Numeric claims are compared against known answers with absolute tolerance 1e-9;
booleans and non-finite numbers are not numeric answers. Each criterion receives
one point only when validated. Score = validated criteria / criterion count;
no criteria means zero. Task pass requires all criteria and execution/protocol
success. Unknown criteria or missing observations are inconclusive; a known
mismatch is rejected and takes precedence over uncertainty.

The 12 scripted tasks currently validate. These are **workflow regression outcomes**,
not a 100% agent-intelligence score. Controls reject an incorrect known answer and
mark missing/subjective evidence inconclusive. A separate end-to-end test proves
that a successful trace from a false-success model is rejected for missing actions.

## Optional live evaluation

```bash
SPARKLE_BENCHMARK_LIVE=1 PYTHONPATH=src python -m unittest tests.test_benchmarks_live -v
```

This explicit opt-in uses the configured provider and can incur costs. It requires
real credentials; CI does not set it. Live adapters receive task input and tool
schemas, never fixture plans/expected answers. The optional test applies the same
strict outcome criteria. Its success alone would still cover only this small task
set, not general intelligence or safety. No live request was performed for this
checkpoint; NVIDIA remains IMPLEMENTED BUT INSUFFICIENTLY VERIFIED.

Level 3 remains BLOCKED and parked. Deployment remains FROZEN.

## Durable live-run diagnostics (2026-09-09)

The previous optional test injected a cached adapter into every temporary registry
and deleted runtime evidence at teardown. `provider_provider_failure` could mean
missing configuration or an unsatisfied routing policy, not necessarily an HTTP
provider failure. Those pre-request paths now use `configuration_failure` and
`routing_failure`. This identifies reproducible classification defects; it does
not establish the cause of an earlier host run without its request evidence.

Use a new output filename for every explicitly authorized live run:

```bash
SPARKLE_BENCHMARK_LIVE=1 PYTHONPATH=src python -m benchmarks.live --output /path/to/new-live-evidence.jsonl
```

The existing optional unittest uses this same runner. Set
`SPARKLE_BENCHMARK_OUTPUT` to select its output; otherwise it uses
`live-agent-evidence.jsonl`. Existing files and symlinks are rejected, never
replaced. Output is created mode 0600 and each event is flushed/fsynced. Do not
commit live output without reviewing it. Interrupted runs retain completed task
records and an incomplete marker where Python can handle the interruption; power
loss or SIGKILL can leave a valid prefix with no terminal marker. A prefix is never
complete benchmark evidence.

The runner fixes the model configuration path before creating temporary task
state, constructs a normal registry per task, and preserves routing/health/fallback
policy. It does not inject a mock or bypass health in live mode. Ordinary CI runs
explicit HTTP doubles and the unchanged deterministic harness, never this real
provider command. No model, task, scoring, validator, or retry setting changed.

Each task records execution/protocol/outcome status separately, independent
validation status/score, safe tool names and failure flags, retrieval identifiers,
memory count, and content-free runtime rows: model/provider, route, timestamps,
latency, attempts, reported usage, request ID and failure category. No model text,
tool arguments/results, memory values, prompt, HTTP headers or exception text is
exported. Configured secret values are additionally redacted from string fields.
Null token counts mean the provider did not report usage; they are not estimated.
Detailed tool-argument correctness remains part of the unchanged validator; the
public evidence intentionally omits argument values.

A runtime row proves adapter invocation, not delivery to NVIDIA. Provider response
metadata supports a completed response; a timeout alone cannot show whether a
remote server received the request. Existing opt-in transport timing diagnostics
remain available. Authentication, HTTP provider failure, timeout, malformed provider
response, pre-provider rejection and outcome validation are separate categories.

Exit 0 means all unchanged outcomes passed; exit 1 means completed evaluation with
failed outcomes; exit 2 means blocked/incomplete. Setup/resource failure is not
model-quality evidence. Do not treat a successful trace or a completed HTTP request
as outcome correctness. Small fixture success is not autonomous competence.

Current executor: credential unavailable; no live request attempted. The user's
previous authenticated smoke test remains valid host connectivity evidence. The
latest host 12-task run remains inconclusive because it failed before provider
execution. Level 3 remains BLOCKED/PARKED; deployment remains FROZEN.
