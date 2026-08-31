# Skill mastery

SPARKLE v0.23 implements `SPARKLE-SKILL/1`, a provider-neutral structured
skill record stored separately in `data_environment/skills.sqlite3`. A stored
mastery level is never accepted from an agent or interface. It is recomputed
from validated evidence after every evidence insertion.

## Levels and evidence

Evidence types are exactly `question`, `exercise`, `test`, `project`,
`implementation`, and `independent_problem_solving`. Each item has an integer
score from 0–100, an explicit verification flag, a bounded summary, optional
artifact reference, and a timezone-aware occurrence time. Unverified evidence
is retained but never contributes to level or average score. Occurrence times
more than five minutes in the future are rejected before persistence.

| Level | Name | Minimum verified evidence |
|---:|---|---|
| 0 | Awareness | No qualifying evidence |
| 1 | Fundamentals | 1 item; average at least 60 |
| 2 | Beginner | 2 items across 2 types; average at least 65 |
| 3 | Intermediate | 3 items across 2 types, including applied evidence; average at least 70 |
| 4 | Advanced | 5 items across 3 types, including 2 applied types; average at least 75 |
| 5 | Professional | 7 items across 4 types, including project and implementation; average at least 80 |
| 6 | Expert / Research | 10 items across 5 types, including project, implementation, and independent problem solving; average at least 85 |

Applied types are exercise, test, project, implementation, and independent
problem solving. Levels can fall if later verified evidence lowers the
aggregate below a threshold. Identical canonical evidence is rejected so it
cannot be replayed to inflate mastery.

## Boundaries

- At most 1,000 active skills and 100 evidence items per skill.
- Active-state checking, the evidence bound, insertion, and level recomputation
  execute in one immediate database transaction.
- Skill identifiers, manifests, timestamps, scores, flags, and update versions
  fail closed on invalid input.
- Metadata updates use optimistic version checks. The derived current level is
  not an updateable field.
- Archival is immutable and requires explicit API or CLI approval.
- Personal, Learning, and Skill agents receive only the read-only
  `skill_search` tool. Research and unrelated agents do not.
- Agent search results exclude the skill description, evidence summary, and
  artifact reference. Model tools cannot create, verify, or archive evidence.
- Proactive `weak_learning` evidence contains only identifiers, levels, counts,
  average score, and evidence-type count. It never copies free text or artifact
  references.

## Interfaces

Create, update, add evidence, list, and archive through the CLI:

```bash
sparkle skill-create skill.json
sparkle skill-evidence evidence.json
sparkle skill-update python changes.json --expected-version 2
sparkle skills --query Python
sparkle skill-archive python --expected-version 3 --approve
```

Equivalent authenticated API routes are `GET/POST /api/skills`,
`GET /api/skill-evidence`, `POST /api/skills/update`,
`POST /api/skills/evidence`, and `POST /api/skills/archive`. The dashboard is a
read-only summary view.

## Honest limits

The contract proves deterministic evidence accounting and least-privilege
access. It does not independently verify that a submitted artifact is genuine,
certify professional competence, generate semantic assessments, or establish
live-provider teaching quality. Evidence verification remains an explicit
trusted-user/API action; external learning platforms and certification
connectors are not implemented.
