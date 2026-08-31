# Build state

Updated: 2026-08-31 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.25.0-alpha.1 |
| Current phase | Continuous improvement — Phase 16/21 AI-system implementation planning |
| Current task | Preserve the verified local v0.25 implementation-plan checkpoint and prepare the next bounded source-candidate generation boundary without claiming execution or remote publication |
| Completed | v0.3-v0.22 capability releases and four-job CI; v0.23 capability publication and four-job CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded structured Agent Blueprint generation/static routing evaluation/approval/rollback; isolated response-contract evaluation with bounded content-free evidence; provider-neutral AI System Blueprints; approval-gated `SPARKLE-AI-SYSTEM-DRAFT/1` natural-language conversion through the model router with isolated no-context/no-tool execution, exact duplicate-free JSON and full Blueprint revalidation, bounded content-free evidence, API/CLI/status/dashboard integration, and deterministic adapter tests; `SPARKLE-PROJECT/1` strict project lifecycle and evidence; `SPARKLE-SKILL/1` strict targets/evidence types/transactional derived levels/duplicate and future-evidence protection/optimistic metadata/archive/content-free proactive and least-privilege agent reads/API/CLI/status/dashboard integration; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation service; bounded dashboard notifications; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; provider-neutral deterministic text/image/audio/document content contracts; dedicated voice/presence contracts; 16-agent matrix; documentation audit; cohesive E2E |
| In progress | Local v0.25 passes all 219 official tests and a fresh no-index installed-wheel plan-only gate. Private GitHub `main` remains at the v0.23 capability commit; later local commits have not been published or run in remote CI. Bounded source-candidate generation with independent human review/static verification is the next unblocked implementation boundary |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); semantic non-text provider mapping; voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | The first two focused commands did not execute the new cases because the worktree had no `.venv` and then lacked `PYTHONPATH=src`. The first executed six-case draft run produced five setup errors because its test adapter omitted `health()`; after adding it, one case failed on an invalid memory-category fixture. Corrected focused/adjacent/full runs pass. Four earlier wheel harness attempts stopped on a missing build entrypoint, rejected network-capable invocation, wrong wheel filename matcher, and wrong automation executable name. The first reconciliation wheel smoke used a nonexistent singular model-status key and stopped after install; a new fresh corrected gate passes. No v0.24 product assertion has failed. Historical failures remain in the release report |
| Next action | Define a bounded provider-neutral source-candidate protocol that consumes an approved plan, requires separate disclosure/generation approval, writes nothing before review, and cannot claim tests or deployment. Remote publication remains a separate approval-gated action |
| Estimated directive completion | 93% |

Release-state reconciliation confirmed local v0.24 implementation at commit
`e5895087e082287df197f4e5c27b925f6dbe4a4d`, tree
`8b0d76e414bd6e8bc547e3ad649e74b58a1b409a`, restored CHANGELOG coverage,
aligned runtime version markers, and added a cross-surface regression contract.
The reconciled source passed 213/213 official tests and a fresh installed-wheel
gate. This is local evidence only: private GitHub `main` remains at
`78032c1fbbaeab7253421f8cdde6e70da5d6f97c`, and no v0.24 remote CI exists.

The v0.25 Implementation Plan boundary revalidates the Blueprint and derives a
deterministic provider-neutral plan with confined proposed paths, ordered work
dependencies, evaluation contracts, and release gates. Approved
materialization writes only the plan manifest and content-free evidence. The
complete local suite passes 219/219 and a fresh installed wheel passes, but
human review, source generation, runtime evaluation, and deployment remain
unexecuted. The completion estimate therefore remains 93%.

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator. Structured
Agent Blueprints now provide deterministic non-mutating requirements-to-
manifest preparation, production-router fixtures, approval-gated installation,
separate evidence persistence, and rollback. Approved response-contract runs
now execute through an isolated no-context/no-tool profile and store bounded
content-free evidence. Generated agents, internal
automations, bounded workspace creation/static verification,
the full external-worker protocol/service loop, deterministic artifact
packaging, the supervised automation lifecycle, and eight structured proactive
rule types now have runtime evidence.
Structured AI System Blueprints now resolve capability/modality routes from the
model registry, validate installed agents and their tool access, preserve the
separate data environments, and materialize a deterministic architecture
manifest only after explicit approval. This is static architecture and
workspace evidence, not generated implementation, semantic evaluation, or
deployment evidence.
The separate AI System Draft boundary now converts explicitly approved bounded
natural language through the common model router and isolated execution
profile, then rejects anything that is not exact duplicate-free JSON satisfying
the entire Blueprint contract. Its persisted evidence contains no prompt or
generated JSON. Deterministic injected-adapter execution is verified; live
MiniMax semantic fidelity and autonomous implementation generation are not.
The Project Agent now reads validated structured project state through a
least-privilege tool. Explicit interfaces own optimistic create/update/archive
operations, and bounded content-free events plus proactive alerts make status,
deadlines, blockers, milestones, and next actions operational rather than
prompt-only. Live-model decision quality and external project/calendar
connectors remain incomplete.
The provider-neutral multimodal transport phase is implemented and locally
tested. It proves bounded content flow, not semantic understanding by the
currently text-only MiniMax adapter. The reference production executor and
deployment profiles exist, but this host
cannot validate their namespaces and no remote instance is provisioned, so
isolation remains blocked. Natural-language agent source generation, semantic
correctness evaluation, live-provider evaluation verification, autonomous code generation, and external
deployment adapters, external email/SMS/push/calendar/webhook delivery, external research
polling, live browser control, real voice, physical embodiment, multi-user role authorization,
TLS/edge rate limiting, and deployment are not
complete.
