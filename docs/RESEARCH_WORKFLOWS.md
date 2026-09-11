# Stateful research workflows

SPARKLE research now has a persistent deterministic lifecycle in addition to the Research Agent prompt and knowledge retrieval tools.

A research project contains an objective, bounded research questions, workflow state, exact stored evidence and synthesized claims. States are planning, collecting, synthesizing, complete and archived, with optimistic revisions on transitions.

Evidence is accepted only through the existing stored-citation integrity verifier. Exact source/chunk identity, retrieved digest and quotation are rechecked against current eligible knowledge before persistence. A VERIFIED citation means the quoted text matches SPARKLE's stored source snapshot; it does not establish external source quality or claim truth. Source quality is therefore an explicit label and rationale rather than an inferred fact.

Factual claims require at least one stored evidence ID. Every claim records fact/inference/comparison/recommendation kind, uncertainty and notes. Deterministic Markdown report generation lists questions, claims, evidence IDs, citation integrity and source-quality labels. Reports explicitly state that claim truth and external source validity are not established automatically.

The read-only `research_workspace` model tool exposes plans, evidence and reports. Operator mutation uses `sparkle-research`; no model tool can silently install evidence or mark research complete.
