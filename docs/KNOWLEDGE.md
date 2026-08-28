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
