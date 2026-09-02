# Foundation capability audit

This audit distinguishes implementation, executed evidence, external blockers,
and intentionally deferred scope. It does not convert code volume into a
completion claim.

| Capability | Classification | Current evidence / remaining boundary |
|---|---|---|
| Model manager, registry, routing, provider factories | VERIFIED | Provider switching, identity validation, capability routing, and rollback are tested without core edits |
| NVIDIA Nemotron adapter | IMPLEMENTED BUT UNVERIFIED | Exact NIM adapter and deterministic doubles pass; no live NVIDIA credential was available |
| MiniMax adapter | COMPLETE | Retained as a disabled legacy provider; deterministic adapter tests pass |
| Model health, request policy, usage evidence | VERIFIED | Health is evidence-based, fallback explicit, traces content-free, and missing usage remains unknown |
| Context, memory, knowledge | VERIFIED | Independent local storage, retrieval, lifecycle, separation, and orchestration integration pass |
| Orchestrator and agents | PARTIAL | Routing, tools, context, traces, and deterministic execution pass; live-model semantic quality remains unverified |
| AI Builder and Agent Builder | PARTIAL | Requirements through controlled execution are implemented; live semantic generation/evaluation and external deployment are absent |
| Projects, skills, automation, proactive rules | PARTIAL | Local structured lifecycles pass; external calendar, learning, research, and notification providers are not connected |
| Controlled promotion | VERIFIED | Exact identity, approval, integrity, replay, traversal, overwrite, and atomic promotion evidence pass |
| Controlled build | VERIFIED | Separate approval and deterministic immutable artifact evidence pass |
| Controlled execution Level 1 | VERIFIED | Contract, authorization, lifecycle, policy, and result verification pass |
| Controlled execution Level 2 | VERIFIED | Genuine local authenticated worker execution passes |
| Controlled execution Level 3 | EXTERNAL-INFRASTRUCTURE-BLOCKED | Current host denies required namespaces; no hostile-canary isolation evidence exists |
| Browser interaction | PARTIAL | Provider-neutral HTTPS/allowlist/result boundary and test harness pass; no live runtime exists |
| Computer interaction | PARTIAL | Typed bounded actions and test harness pass; no live GUI runtime exists |
| Voice | EXTERNAL-INFRASTRUCTURE-BLOCKED | Interfaces exist; no microphone, speaker, STT, or TTS provider is available |
| Dashboard, API, CLI | VERIFIED | Local authenticated surfaces and model/execution evidence views are tested |
| Deployment | DEFERRED BY DESIGN | Frozen until Level 3 and a separate deployment authorization milestone |

## Current decision

The infrastructure-independent model-runtime and interaction-contract work is
ready. Live Nemotron, live browser/computer/voice providers, Level 3 isolation,
and deployment require evidence not available in the current environment.
SPARKLE remains `0.30.0-alpha.1`; the directive completion estimate remains
93% rather than increasing from preparatory code alone.
