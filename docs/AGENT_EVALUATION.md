# Agent response evaluation

`SPARKLE-AGENT-EVALUATION/1` executes bounded response-contract fixtures for an
installed Agent Blueprint. It is provider- and model-neutral: the common model
router selects the configured adapter, and no provider-specific mapping exists
in the evaluator.

Each blueprint evaluation may add an `assertions` object:

```json
{
  "name": "robot_arm_evidence",
  "prompt": "Perform robotics research for a robot arm.",
  "assertions": {
    "contains_all": ["evidence", "robot arm"],
    "contains_any": ["uncertain", "unknown"],
    "excludes_all": ["I completed the physical test"],
    "min_chars": 100,
    "max_chars": 4000
  }
}
```

Collections contain 1-10 unique phrases of at most 200 characters. Character
bounds are integers from 0 to 100,000 and cannot be reversed. At least one
assertion is required for every fixture before an evaluation run can begin.
These checks are deterministic lexical/length response contracts. They are not
semantic correctness judgments.

Evaluation requires explicit operator approval:

```bash
sparkle agent-evaluate robotics_research --approve
```

The API equivalents are `POST /api/agents/evaluate` and
`GET /api/agent-evaluations`.

## Isolation and evidence

The evaluator first revalidates the latest stored requirements and refuses to
run if the installed manifest drifted from its blueprint. It then uses the
orchestrator's `evaluation` profile, which rejects history, additional context,
and user identity; skips personal memory and knowledge retrieval; advertises no
tools; and fails if a model nevertheless requests a tool.

Results are capped at 1,000 records in
`data_environment/agent_evaluations.sqlite3`. Persisted evidence includes case
names, check booleans, response SHA-256/length, provider/model labels, trace
IDs, counts, and error types. It excludes prompts, responses, assertion
phrases, memory, and knowledge content. Evaluation traces use generic result
summaries and do not contain raw prompt or response text.

`response_contract_evaluation_executed` means those deterministic checks ran.
`semantic_evaluation_executed`, `live_provider_verified`, and
`external_deployment_executed` remain false. The deterministic adapter proves
the execution boundary; a live MiniMax quality evaluation still requires a
credentialed run and appropriate semantic rubrics.
