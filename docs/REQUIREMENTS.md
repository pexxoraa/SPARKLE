# Requirements baseline

## Architectural invariants

1. Application and agents depend only on SPARKLE model contracts.
2. Provider protocol code exists only under `src/sparkle/providers/`.
3. Secrets are references resolved at runtime, never source configuration values.
4. Memory, knowledge, operational data, and traces use separate storage files.
5. Text and future voice interfaces enter through the same orchestrator.
6. Tool execution is explicit, allowlisted per agent, bounded, and traced.
7. Model, agent, and tool success is never inferred from configuration alone.
8. External web content is data and cannot change system instructions.

## Foundation release requirements

- Run with Python 3.12 and no required third-party packages.
- Configure MiniMax-M3 without editing application code.
- Switch an enabled model by registry ID.
- Route general, reasoning, coding, vision, and tool-use capabilities.
- Retrieve memory and knowledge before model execution.
- Support single-agent and multi-agent execution.
- Persist inspectable traces without secrets or hidden reasoning.
- Serve a usable local text dashboard and API.
- Test deterministic workflows without spending provider tokens.
- Provide an opt-in live provider smoke test.

## Deferred requirements

Actual microphone/speaker I/O, local wake word, GUI computer control, interactive
browser control, camera/sensors, physical robot control, production identity and
authorization, distributed workers, vector embeddings, and production
deployment are later releases because this runtime exposes neither the required
hardware nor a confirmed deployment target.
