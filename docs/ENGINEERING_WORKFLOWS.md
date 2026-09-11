# Repository engineering workflows

SPARKLE coding and software-engineering support now includes bounded repository inspection and persistent engineering work state instead of relying only on agent prompts.

`RepositoryEngineeringService` inventories the configured repository without following symlinks or traversing `.git`, virtual environments, node_modules, build output or hidden secret-style environment files. Snapshots record deterministic manifest SHA-256, file counts, total bytes and suffix counts. Individual UTF-8 files expose bounded content plus exact SHA-256 identity.

Engineering work items persist requirements, design decisions, target files, risks, tests, technical debt, priority, release notes, state and optimistic revision. States are planned, in_progress, blocked, ready_for_review, complete and archived. Completion requires release notes. Readiness reports distinguish documented readiness from actual execution or deployment verification.

The read-only `engineering_inspect` tool is available to Coding, Software Engineering and builder agents. It can inspect repository structure/files and engineering plans, but it cannot modify source or claim tests ran. Operator work-state mutation uses `sparkle-engineering`. Existing workspace scaffold/static verification/test/package controls remain the execution/build path.
