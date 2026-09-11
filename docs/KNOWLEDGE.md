# Knowledge

Knowledge answers factual/domain questions from user-provided sources. It is
stored separately from personal memory.

The current pipeline is source → extract → paragraph-aware chunk → tokenize →
SQLite FTS5 index → title/content BM25 rank → retrieve → context. Supported core
formats include text, Markdown, JSON, YAML, CSV, code, HTML, and CSS. The
`documents` extra enables PDF and DOCX extraction.

The current ranker is deterministic lexical retrieval. Experimental provider-neutral embedding and hybrid retrieval adapters exist,
with deterministic test doubles. Real semantic quality remains unverified;
lexical retrieval remains the default.

Knowledge revisions can be tracked with an explicit safe monitor key. Re-ingest
the same logical source with `research_monitor: true` and the same
`monitor_key`, or use `sparkle ingest --monitor-key KEY`. SPARKLE stores a
SHA-256 content digest inside the knowledge database and compares the two most
recent bounded observations. Changed content produces a computed
`research_change` alert for seven days.

Monitor keys must contain 1-64 lowercase letters, numbers, dots, underscores,
or hyphens. Metadata is limited to 4 KiB. Alerts expose only the monitor key,
knowledge source IDs, observation time, and age; they never expose source
content, title, URI, or digest. This is revision detection for explicitly
observed sources. External web polling and source discovery are not implemented.


## Indexed retrieval boundary

New ingests split long paragraphs to the configured character bound (default
1800; integer 1–100000). Existing chunks retain their IDs and bytes during the
transactional one-time index backfill. SQLite must include FTS5; startup fails
if index creation fails. No network service or embedding provider is used.
The index contains knowledge titles/content only, in the same knowledge DB;
personal memory, credentials and traces are not indexed. Insert/update/delete
triggers keep the index consistent, including source deletion and rollback.

Retrieval considers the first 16384 query characters and 64 distinct Unicode
word tokens (longer chat input is preserved for the model);
FTS operators are treated as literal words, not executable query syntax. Results
are capped at 50. Title matches carry weight 3 versus content weight 1, using
SQLite BM25 with stable chunk-ID ties. Positive scores are relative relevance,
not probabilities or calibrated confidence. Unicode61 normalizes case and
accent marks; it does not provide semantic, synonym or language segmentation
understanding. Context carries source ID, chunk ID and position for attribution;
this does not compel a model to cite correctly.

The index improves lexical retrieval without changing the knowledge-search
tool or public result shape. Representative retrieval-quality benchmarking and
semantic/hybrid search remain unfinished. See the
[foundation audit](FOUNDATION_AUDIT.md) for scope and evidence.
Implementation reference: https://sqlite.org/fts5.html .


## Measurable evaluation milestone

See [Benchmarks](BENCHMARKS.md) for the versioned corpus, lexical baseline,
opt-in embedding/hybrid test paths, bounded untrusted context, four-agent
outcome harness and independent validation. Real semantic and live-model
quality remain unverified; production retrieval remains lexical.

## Stored citation integrity

`knowledge_search` tool results include `citation_digest`, a SHA-256 snapshot
of source/chunk identity, position, title, URI and complete stored chunk text.
The Research Agent can call `knowledge_verify` with up to 20 citations, each
containing `source_id`, `chunk_id`, `digest`, and an exact `quote` (1–1800
characters). The protected `POST /api/knowledge/verify` accepts the same tool
arguments. No URL is fetched or followed by verification.

The checker reads one SQLite snapshot. Missing chunks, wrong source identities,
changed snapshots, and absent exact quotes are REJECTED. Invalid/ambiguous
citations remain INCONCLUSIVE. A mixed batch never hides a failed citation.
Results report index, status and reason without echoing private text or URIs.

VERIFIED means only that the supplied quote exists in the identified stored
snapshot. `claim_truth=INCONCLUSIVE` and `external_source_verified=false` remain
explicit even then. This is not semantic entailment, source credibility, current
web verification, or model-answer validation. A model that cites an irrelevant
but genuine quotation has not proven its answer. Stored knowledge remains
untrusted. No automatic answer approval or memory approval is introduced.

The digest binds a retrieved snapshot; it is not a signature against a database
owner who can replace both data and evidence. Revision/retention workflows and
independent external source verification remain unfinished work. Lexical and
experimental semantic ranking are unchanged.

## Operator-owned source lifecycle

Knowledge policy is now independent of source contents. Existing sources migrate
as active revision 0 without inventing historical events. `knowledge-policy ID`
shows state, eligibility and the latest 100 events. To change policy, supply
`--action archive|restore|revoke|retention|supersede --revision N --approve`.
Retention uses `--seconds 1..31536000`; omitting seconds explicitly clears expiry.
Supersession requires `--replacement-id ID` naming an active, unexpired source.
The equivalent protected API is GET `/api/knowledge/lifecycle?source_id=ID` and
POST `/api/knowledge/lifecycle` with source_id, action, expected_revision,
approved=true, and optional retention_seconds/replacement_id.

Changes and audit events commit atomically. Stale revisions fail. Revoked and
superseded records are terminal; restore only applies to unexpired archives.
Expired sources can be explicitly extended by the operator, but no agent tool
can change lifecycle policy. Supersession preserves the original source/chunks;
it does not assert that the replacement is more credible or factually correct.
Source deletion retains content-free lifecycle events, not deleted source text.
Event UPDATE/DELETE is refused by SQLite triggers; this is not cryptographic
protection against the database owner.

Lexical retrieval excludes ineligible sources before ranking LIMIT. Semantic
retrieval excludes them before embedding and rechecks eligibility after the
provider returns. Hybrid retrieval rechecks before returning either fused or
fallback results. Citation verification rejects ineligible sources. These are
bounded read snapshots, not leases: an operator can revoke a source after a
result is returned. External embedding systems must also enforce their own
retention; local revocation cannot retract bytes already sent to a provider.
Source inventory and revision-monitor history remain historical records.

Implementation is internally checked; no live embedding or human knowledge
workflow acceptance is claimed. Source replacement is explicit rather than
inferred from equal URLs or monitor keys. General semantic deduplication,
credibility and entailment remain separate unfinished capabilities.
