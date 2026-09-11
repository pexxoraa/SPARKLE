# Persistent semantic vector index

SPARKLE's semantic retrieval remains provider-neutral and opt-in. `SemanticRetriever`
now uses `PersistentVectorIndex` so unchanged knowledge chunks are not re-embedded on
every query.

The index is stored under `knowledge_environment/vectors.sqlite3` by default. Each
record binds the chunk identity, source identity, embedding-provider identity,
dimensions, SHA-256 of the chunk content, SHA-256 of the exact bounded
`title + "\n" + content` embedding input, a normalized finite vector, and an update
timestamp.

`PersistentVectorIndex.synchronize()` scans only currently eligible knowledge sources.
It embeds only missing or changed chunks, batches provider calls, rechecks source
eligibility and exact content immediately before persistence, and removes rows for
archived, revoked, superseded, expired, deleted, or otherwise stale chunks. Search
performs the same source-lifecycle and digest checks again before a vector can
contribute to a result and opportunistically deletes stale rows it encounters.

Provider implementations must expose three things: a stable `identity`, an integer
`dimensions`, and `embed(list[str]) -> list[list[float]]`. Provider identity is the
model/version boundary for persisted vectors; changing an embedding model should use a
new identity. Vectors containing booleans, non-numeric values, NaN, infinities, wrong
dimensions, or invalid stored normalization fail closed.

`HashingTestEmbeddings` remains a deterministic test double only. It is not a semantic
model and is not quality evidence. Persistent vector-index status therefore exposes
`semantic_quality_verified: false`. Real embedding-model selection, quality evaluation,
credentials, network availability, and live semantic acceptance remain separate
external/manual work.
