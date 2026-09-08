# Knowledge

Knowledge answers factual/domain questions from user-provided sources. It is
stored separately from personal memory.

The current pipeline is source → extract → paragraph-aware chunk → tokenize →
SQLite FTS5 index → title/content BM25 rank → retrieve → context. Supported core
formats include text, Markdown, JSON, YAML, CSV, code, HTML, and CSS. The
`documents` extra enables PDF and DOCX extraction.

The current ranker is deterministic lexical retrieval. Embedding and hybrid
retrieval adapters are planned; they can replace ranking without changing the
source/chunk schema or context interface.

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
