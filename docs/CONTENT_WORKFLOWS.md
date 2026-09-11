# Persistent content workflows

SPARKLE separates provider-neutral multimodal content envelopes (`content.py`) from operator-owned persistent content workflow state (`content_workflow.py`). The persistent layer stores bounded text content, templates, workflow state, immutable revision history and deterministic exports. It does not claim that content was externally published.

## State model

Content items have a stable lowercase name, title, kind, audience, body, JSON metadata, optional template origin, revision, SHA-256 digest and workflow status. Supported kinds are article, script, post, email, brief, notes and generic. Workflow states are `draft`, `review`, `approved` and `archived`.

Allowed transitions are explicit: draft may enter review or archive; review may return to draft, become approved, or archive; approved may return to draft or archive. Archived content is terminal. Every mutation requires the exact expected revision and appends an immutable version record. Approved bodies cannot be edited directly; they must first return to draft.

## Templates and transformations

Templates declare an exact variable set and use `{{variable}}` placeholders. Declared variables and placeholders must match exactly. Rendering is deterministic and bounded; missing or extra values fail closed.

Operator transformations support append, prepend, exact replace and trim. These transformations use the same optimistic revision boundary as direct edits. Model-facing access is read-only through `content_search`; a model can inspect persisted briefs/drafts but cannot edit, approve, archive or export them through that tool.

## CLI and output

The `sparkle-content` command exposes list, inspect, history, templates, template-save, create, update, transform, transition and export operations. Mutating operations require `--approve`. Exports are restricted to SPARKLE's data directory and support Markdown, JSON and plain text. Export results include the exact revision, relative path, byte count and SHA-256 digest.

External publication is intentionally not part of this workflow. Deployment remains frozen, and a saved or approved content item is not evidence that any external platform accepted it.

## Bounds and acceptance

Content bodies are limited to 200,000 characters, templates to 100,000, metadata to 20 KB, items to 2,000 and templates to 200. Names and variables use bounded identifiers. Persistent storage lives under `SPARKLE_DATA_DIR/data_environment` and follows the same operator backup responsibility as other SQLite state.

Software-side persistence, workflow transitions, revision conflicts, deterministic transformations, template rendering, exports, model read-only access and system status are implementation targets. Human editorial quality, platform-specific formatting, external publication and real audience outcomes remain manual/external acceptance concerns.
