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
