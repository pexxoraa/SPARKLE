# Knowledge

Knowledge answers factual/domain questions from user-provided sources. It is
stored separately from personal memory.

The current pipeline is source → extract → paragraph-aware chunk → tokenize →
SQLite store → lexical relevance rank → retrieve → context. Supported core
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
