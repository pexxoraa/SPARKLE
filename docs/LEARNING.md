# Stateful learning and assessment

Implemented: operator-authored curricula, bounded topic prerequisites, lessons,
question banks, exam sections, timed persistent attempts, saved answers,
submission/cancellation, deterministic grading, explicit manual review, retakes,
weak-topic recommendations and links to existing skill evidence. This is not
proctored assessment, verified learner identity, calibrated teaching quality or
independent competence verification.

## Definition and operations

`learning --manifest PATH --approve` applies an operator operation. The protected
`POST /api/learning` uses the same JSON, plus `approved:true`.

Operations and arguments:

| Operation | Arguments |
|---|---|
| install | definition, expected_revision (0 for new curriculum) |
| archive | name, expected_revision |
| start | course, exam, learner, expected_revision (curriculum revision) |
| act | attempt_id, action=answer/submit/cancel, expected_revision; answers for save/submit |
| grade_manual | attempt_id, expected_revision, grades mapping question ID to points and feedback |
| link_skill | attempt_id, skill_name |

Install `examples/learning-install.json` for a harmless authored practice example.
The definition includes name/title/goal, topics, questions and exams. Topics have
id/title/lesson/prerequisites/skill; skill is null or an existing active skill ID.
Questions have id/topic/prompt/kind/options/answer/tolerance/points/difficulty.
Kinds: choice (exact option), number (finite numeric key/tolerance), text (exact
case-sensitive text after trimming), manual (no automatic answer key).
Exams have id/title/sections/duration_seconds/pass_percent/max_attempts; sections
have title/questions. Definitions are validated as a DAG; unknown references and
cycles fail. Revisions and private definitions are retained in immutable
application-level version records. Existing attempts retain their own snapshots.

Inspect with `learning`, `learning --course NAME`, `learning --course NAME
--learner ID`, or `learning --attempt ID`. GET `/api/learning` accepts equivalent
course/learner/attempt query parameters. The dashboard supports curriculum
inspection, start, save, submit, cancel, refresh, progress and attempt resumption.
Manual grading and curriculum authoring use the approved API/CLI. Personal,
Learning, Skill and Exam agents have read-only curriculum/progress
access where their existing skill tool permissions apply. No model tool can
install a key, start/submit a learner attempt, grade or raise mastery.

## Timing, grading and progression

Attempts are active, submitted, cancelled or timed_out. Every mutation requires
its exact revision. One active attempt per learner/course/exam is permitted.
An expired attempt is finalized on inspection or action; it cannot pass or be
submitted late. The durable deadline uses the server clock, survives restart,
and rejects backward-clock actions. This assumes a trustworthy host clock; it
is not tamper-proof timing or a proctoring system. Cancellation/timeout consume
retake allowance; installing a new curriculum revision does not reset counts.

Manual questions produce INCONCLUSIVE until an operator supplies points and
feedback. Automatic keys cannot be overridden through manual grading. Reviews
are revision-bound and cannot silently replace an already-reviewed grade.
Missing automatic answers score zero. Any unresolved manual grade keeps the
overall score inconclusive. Keys/tolerances are excluded from all public
curriculum/attempt reads and model-facing tools. Stored definitions are private
application data; database administrators can access them.

Progress uses the latest submitted practice per topic in the current curriculum
revision. Below 80% recommends revision; at/above 80% recommends spaced review.
Missing prerequisite practice blocks a later-topic exam unless that same exam
also assesses the prerequisite. These are transparent deterministic practice
rules, not a claim of optimal pedagogy or mastery. Source lessons remain
untrusted content. Learner identifiers are operator-owned labels, not authenticated
student accounts; this is a single-owner practice system, not a multi-tenant LMS.

A completed, fully graded attempt can be linked to its declared skill. That
creates `verified=false` evidence with a stable attempt reference and timestamp;
duplicate evidence is refused by the existing skill store. It does not raise
verified mastery. Learner identity, source/key correctness and broad competence
remain unverified even after a perfect score.

## Bounds and manual acceptance

100 curricula, 50 topics and 200 bank questions per curriculum; 20 exams,
100 selected questions per exam; up to 2 hours and 20 attempts per exam;
10,000 stored attempts globally and 10,000 audit events per subject. Definitions
are bounded to 1 MB. Private audit/version data is retained, not silently erased.
The operator must manage state storage and protect database backups. No automatic
external provider or paid model calls are required.

Internally checked with deterministic persistence, grading, expiry, revision,
key non-disclosure, manual-review and API/CLI cases. Real browser UX,
accessibility, learning effectiveness, real learner behavior and comprehensive
manual/security acceptance remain pending. The human acceptance sequence is:
install an authored course; inspect key-free reads; start/save/restart/resume;
submit correct/incorrect/manual responses; test timeout and stale revision;
review manual answers; inspect recommendations; link unverified skill evidence;
confirm that no competence or verified mastery is inferred automatically.
