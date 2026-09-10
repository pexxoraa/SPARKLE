# Agents

All agents are registry records with a purpose, capability requirement,
instructions, allowed tools, and routing keywords. They share the orchestrator,
context, trace, and model systems.

| Agent | Primary responsibility |
|---|---|
| Personal | Goals, priorities, context, specialist coordination |
| Learning | Explain, ask, test, correct, apply, retest |
| Skill | Evidence-based mastery levels 0–6; read-only access to validated `SPARKLE-SKILL/1` summaries |
| Exam | Syllabus, practice, mocks, revision, error analysis |
| Research | Source evaluation, cross-checking, synthesis |
| Coding | Implementation, debugging, tests, code review |
| Software Engineering | Architecture, maintenance, security, releases |
| Application Builder | Complete application lifecycle |
| AI Builder | Complete model/data/evaluation AI systems |
| Agent Builder | Purpose/tools/memory/workflow/guardrail agent design |
| Project | Status, deadlines, risks, blockers, milestones; read-only access to validated `SPARKLE-PROJECT/1` records |
| Data Analysis | Cleaning, statistics, visualization, forecasting |
| Content | Research, ideas, scripts, visuals, publishing |
| Productivity | Realistic schedules and deep work |
| Automation | Triggers, actions, failure policies |
| System | Runtime, configuration, security, diagnosis |

Multi-agent execution runs selected specialists, then asks the Personal Agent to
synthesize their outputs. Each specialist and synthesis receives its own trace.

Personal, Learning, and Skill agents can inspect bounded structured mastery
summaries through `skill_search`. Evidence creation/verification, metadata
updates, and archive are explicit user/API/CLI boundaries; no model tool can
raise a level. Descriptions, evidence summaries, and artifact references are
excluded from model-facing results.

Generated agents use the same `AgentSpec` contract and execution path. Approved
manifests are validated against registered tools, persisted outside source code,
hot-loaded immediately, and reloaded on restart. The registry protects all 16
built-in definitions from replacement or deletion. Generated-agent lifecycle
operations are available through the CLI and local HTTP API.

Coding, Software Engineering, Application Builder, AI Builder, and Agent Builder
can request the approval-gated `workspace_verify` and `workspace_package`
tools. Verification provides static syntax/parse evidence only. Packaging
creates deterministic bytes without executing source. Agents must not describe
either as application execution or deployment; deployment records remain an
operator/API boundary rather than a model tool.

Research can use `knowledge_verify` after `knowledge_search`. Exact stored citation
integrity is independently checked, but factual truth and relevance remain
inconclusive. This optional tool does not automatically validate final answers.
