# Agents

All agents are registry records with a purpose, capability requirement,
instructions, allowed tools, and routing keywords. They share the orchestrator,
context, trace, and model systems.

| Agent | Primary responsibility |
|---|---|
| Personal | Goals, priorities, context, specialist coordination |
| Learning | Explain, ask, test, correct, apply, retest |
| Skill | Evidence-based mastery levels 0–6 |
| Exam | Syllabus, practice, mocks, revision, error analysis |
| Research | Source evaluation, cross-checking, synthesis |
| Coding | Implementation, debugging, tests, code review |
| Software Engineering | Architecture, maintenance, security, releases |
| Application Builder | Complete application lifecycle |
| AI Builder | Complete model/data/evaluation AI systems |
| Agent Builder | Purpose/tools/memory/workflow/guardrail agent design |
| Project | Status, deadlines, risks, blockers, milestones |
| Data Analysis | Cleaning, statistics, visualization, forecasting |
| Content | Research, ideas, scripts, visuals, publishing |
| Productivity | Realistic schedules and deep work |
| Automation | Triggers, actions, failure policies |
| System | Runtime, configuration, security, diagnosis |

Multi-agent execution runs selected specialists, then asks the Personal Agent to
synthesize their outputs. Each specialist and synthesis receives its own trace.
