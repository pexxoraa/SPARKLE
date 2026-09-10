# Memory

Memory answers: “What does SPARKLE know about the user?” It is not a knowledge
base or secret store.

Supported categories are user, goals, preferences, skills, learning, exams,
projects, research, content, tasks, decisions, mistakes, conversations, and
summaries. Records support upsert, search, recent listing, importance,
metadata, archive, and restore by a future API.

SPARKLE does not automatically convert every conversation into durable memory.
The agent-facing `memory_write` tool is reserved for explicit or materially
useful facts. Secrets are not a valid memory category.

## Bounded literal query behavior

Memory lookup accepts Unicode word tokens, including one-character non-ASCII
terms, and considers at most 64 distinct terms. ASCII single-character tokens
remain excluded. Underscores are literal, not SQL LIKE wildcards. Blank queries
retain the existing recent-memory behavior; nonempty queries with no usable tokens
return no matches. A Japanese or punctuation-only query must not silently insert
unrelated recent memories into model context.

This is lexical substring matching. SQLite lower/LIKE does not provide complete
Unicode case folding, accent normalization, semantic similarity or multilingual
translation. Those limitations remain explicit. Category, archive and result-count
filters are preserved. No memory mutation/authorization workflow is changed.

## Review model-proposed writes

The default `SparkleSystem` registers `MemoryProposalTool` under `memory_write`.
It returns `stored=false`, a proposal ID/digest and `status=pending`. Pending
content lives in the memory database's separate proposal table and is never
returned by memory search, context assembly or durable-memory export. Treat it
as untrusted model output. Review content against user instructions and evidence.

```sh
sparkle memory-proposals
sparkle memory-review PROPOSAL_ID EXACT_DIGEST approve
sparkle memory-review PROPOSAL_ID EXACT_DIGEST reject
```

API: `GET /api/memory/proposals`; `POST /api/memory/review` with exactly
`proposal_id`, `digest`, and `decision` (`approve` or `reject`). Existing API
authentication, session/CSRF and rate controls apply. In configured unauthenticated
local mode the reviewer is recorded as `local_api`, never as authenticated.
No review tool is exposed to the model. Direct operator `remember`/memory POST
remains available and is not replaced by a model assertion of authorization.

Proposals expire for approval after 24 hours, bind the current memory row, and
require unchanged content/digest and a pending state. Reject can dispose of expired
proposals. A transaction makes approval, memory upsert and review status atomic;
concurrent/replayed approvals cannot apply twice. Changed/archived/deleted target
memories require a new proposal. Limits: 1,000 pending proposals, 256-character
keys, 8,000-character values, and 100 reviewed records per list request. Pending
records require operator rejection to release capacity; automatic retention is
not implemented. Review history stores content in the private database; traces
record only proposal identifiers, not proposal content. Protect backups as memory.

This provides independent operator review, not automatic truth detection or an
LLM validator. Unknown claims must stay pending or be rejected. The legacy
`MemoryWriteTool` remains for explicitly constructed existing integrations and the
unchanged benchmark fixture; it is not registered by the default system. Custom
registries must select the proposal tool to receive the new authorization boundary.
No new secret ingestion/recognition capability is claimed. Never submit secrets
as memory content. Level 3 stays parked and deployment frozen.

### Pending queue visibility

Proposal listing defaults to pending records, oldest first (ID breaks timestamp
ties). Reviewed history cannot bury pending work in the bounded result set.
Use `sparkle memory-proposals --status approved` (or `rejected` / `all`) for
history; API clients use `/api/memory/proposals?status=approved`. Reviews do
not change retention policy, expiry, exact-digest checks or authorization.

## Exact factual validation against operator attestations

`memory-attest CATEGORY KEY VALUE SOURCE_REF --ttl-seconds 86400` registers an
independently checked operator fact. It is not a model tool. Source references
are provenance labels, not fetched or authenticated websites. The operator is
responsible for establishing the fact independently of a proposal. Values
represent exact field assertions; paraphrase equivalence is not inferred.

`memory-validate PROPOSAL_ID DIGEST` returns VERIFIED for an exact active match,
REJECTED for a different value under the same exact-field contract, and
INCONCLUSIVE for missing/expired/revoked evidence, conflicts, or over 64 active
attestations for a key. Agreement is not independent source voting or proof of
universal truth. Unstructured claims without an attested field stay inconclusive.
Validation never authorizes a write. `memory-review ... approve --require-verified`
requires current VERIFIED evidence. Review without that flag can independently
approve INCONCLUSIVE content, but cannot approve a currently REJECTED claim.
It records that distinction in memory metadata. Existing explicit operator writes
remain supported. All fact/approval fields stay unavailable to model tools.

`memory-fact-revoke ID` revokes an attestation; `memory-evidence` returns bounded
content-free audit events. Facts have revision IDs and expiry. Approval rechecks
facts in the same transaction as the memory update. Strict-policy retrieval
rechecks active facts before applying result limits: revocation, expiry, conflict
and contradiction exclude the record even if old metadata says VERIFIED.
Archival export retains excluded records; it is not model retrieval.

API equivalents: GET `/api/memory/facts`, GET `/api/memory/evidence`, POST
`/api/memory/attest`, `/api/memory/fact-revoke`, `/api/memory/validate`; review
accepts optional boolean `require_verified`. Existing auth/CSRF rules apply.
Audit UPDATE/DELETE is rejected by SQLite triggers. Database-owner tamper
resistance is not claimed; protect the database and backups. History records
digests and revisions, not historical plaintext attestation values. The default
operator-approved policy is distinct from strict verified-only retrieval.

This is a credential-free exact-claim validator, not an LLM judge, general
fact-checker, web verifier, or semantic entailment engine. Broader authoritative
application-state readers and natural-language claim evaluation remain open.

## Retention and immutable version history

`memory-retention ID --seconds N` sets expiry (1 second through 365 days);
omitting `--seconds` explicitly clears expiry. New records default to no expiry.
Updates preserve existing expiry, including expired records. `memory-revoke ID`
excludes an ID from retrieval; archive restoration and later upserts cannot
silently reverse revocation. Replacing a revoked ID requires an explicit new
record after deletion, with old history retained. Proposal approval refuses
revoked/expired targets until the lifecycle policy is resolved independently.

Search, recent/context and active export exclude expired, revoked or archived
records before limits. Expiry uses a fractional wall clock; no background sweeper
is required. Expired rows remain in archival export; reading does not mutate
state. `restore` works only for non-revoked, non-expired rows.

`memory-history` and GET `/api/memory/history` expose bounded private snapshots.
POST `/api/memory/retention` takes memory_id, seconds and approved=true; POST
`/api/memory/revoke` takes memory_id and approved=true. Existing auth/CSRF applies.
INSERT/UPDATE/DELETE triggers capture versions atomically with state changes.
UPDATE/DELETE of history fails. Migration captures a baseline once; it cannot
reconstruct earlier lost revisions. Concurrent migration is serialized.

Deletion removes current memory but deliberately retains historical plaintext
snapshots. This is auditable removal, not privacy erasure. History contains private
memory values and requires the same access/backup protection. There is no automatic
history purge, storage quota, cryptographic tamper-proof log, or deleted-record
auto-restore. Database-owner tampering is outside these application-level guards.

## Dashboard review

The Memory panel loads pending proposals separately from eligible records and
completed audit history. It displays exact proposal identity/digest, expiry,
current factual verification, target conflict/revocation state, and private
attestation evidence. Values and audit snapshots are rendered with text nodes,
never interpreted as HTML. These authenticated/local-operator views contain
private data and must not be exposed publicly.

Approval defaults to requiring VERIFIED evidence. An operator may explicitly
allow an INCONCLUSIVE claim after independent review; REJECTED evidence cannot
be overridden. Missing identity, unknown verification, expiry, target conflict,
or blocked targets disable approval. The API always rechecks authoritative
identity, evidence, expiry and memory state atomically; the display is not an
authorization snapshot. Revalidation never approves a proposal. In-flight clicks
are bounded and server errors do not become successful approvals.

Deterministic Node DOM tests cover rendering and interaction contracts. They
are not a real-browser accessibility or host acceptance claim. Factual validation
still means agreement with active operator-attested exact fields, not general
semantic truth. Version history is private retained data, not privacy erasure.
