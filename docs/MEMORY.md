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
