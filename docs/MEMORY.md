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
