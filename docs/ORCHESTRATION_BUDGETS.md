# Orchestration execution budgets

SPARKLE orchestration applies one shared workflow budget across specialist calls, synthesis, model rounds and tool execution. The default wall-clock budget is 300 seconds, bounded to 1-3600 seconds when constructing an `Orchestrator`. Each model request receives at most the remaining workflow time and never more than the existing 120-second per-attempt ceiling.

Tool-call count remains reserved per returned batch before any tool in that batch executes, preventing partial execution when a batch would exceed the configured limit. The shared budget persists across `run_multi` specialists and final synthesis.

Provider tool-call IDs are also workflow idempotency keys. The first occurrence stores the exact canonical name/arguments signature and bounded result. An exact replay returns the cached result without re-executing the tool. Reuse of the same call ID with different arguments fails closed with `tool_call_replay_mismatch`. Failed tool results are cached as results too, so retries cannot repeatedly trigger a rejected or partially side-effecting boundary.

Trace execution metadata records the workflow time limit, elapsed time, reserved tool attempts and exact replay count. A wall-clock failure uses the content-free orchestration code `workflow_deadline`. These controls are engineering safeguards; they do not establish semantic correctness of model planning or tool results.
