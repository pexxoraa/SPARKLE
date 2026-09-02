# AI environment

The AI environment owns model records, provider adapters, health, request
policy, routing, and content-free request evidence. The application requests a
capability; it does not select a vendor endpoint.

The active provider is NVIDIA and the active model is
`nvidia/nemotron-3.5-lightning-30b-a3b`. The hosted NIM endpoint uses
`POST /v1/chat/completions`, bearer authentication, SSE streaming, and
OpenAI-style tool definitions. SPARKLE normalizes that surface behind the same
`ModelAdapter` interface used by deterministic test adapters and the retained
MiniMax adapter.

Registry records declare roles, modalities, enabled state, context/output
bounds, endpoint, secret references, streaming/tool support, latency class,
timeout, and whether the record may be used as a fallback. Loading fails closed
on unknown adapters, identity mismatch, secret-value fields, unsafe or duplicate
identifiers, invalid capabilities/modalities, invalid policy types, disabled
routing targets, or capability-to-role mismatch.

Routing evaluates health and request requirements before credentials or network
access. A provider is not healthy because a key name exists. Successful live
requests create provider health evidence; deterministic injected adapters stay
marked as test-harness evidence. Request records contain no prompt or response
content and leave missing usage values unknown.

The current NVIDIA integration is text-only. `SPARKLE-CONTENT/1` continues to
carry bounded image, audio, and document inputs through the provider-neutral
core, but semantic non-text execution requires a separately registered capable
adapter. Unsupported combinations fail before provider access.

Current evidence:

- NVIDIA adapter mapping, auth refusal, safe errors, retry, usage, tools, and
  SSE normalization: tested with deterministic HTTP doubles.
- Nemotron as the primary configured record: tested.
- Switching to local/mock providers without core changes: tested.
- Health, policy, fallback, timeout/latency filtering, and content-free usage:
  tested.
- Live NVIDIA Nemotron request: **NOT VERIFIED**.
- Live MiniMax request: **NOT VERIFIED**; MiniMax is retained but disabled.
