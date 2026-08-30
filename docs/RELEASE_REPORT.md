# 0.14.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed evidence

- The focused proactive storage/runner/API set passed 28 tests in 8.376 seconds
  after version and documentation alignment.
- The final pre-publication `make check` passed 120 tests in 21.283 seconds,
  including deterministic ordering and the hard 200-alert response bound.
- A non-editable `0.14.0a1` wheel was built without dependency resolution,
  installed in a fresh virtual environment, and ran `sparkle status` plus the
  automation check/once/status lifecycle. Runtime defaults materialized as two
  separate mode-0600 files, status surfaces reported
  `credentials_exposed: false`, and the service completed one clean cycle.
- Dashboard JavaScript syntax and Git whitespace checks passed.
- The engine emits six bounded alert types exclusively from validated
  structured memory metadata. Invalid, incomplete, unstructured, non-finite,
  and out-of-range evidence produces no alert; serialized alerts omit memory
  free text.
- Strict conditional-automation schemas reject unknown types, alert names,
  categories, fields, empty/oversized keys, and invalid cooldowns. A real
  weak-learning condition executed once and respected its cooldown.
- `GET /api/proactive` and the dashboard panel are integration tested, and the
  query-free audit path is recorded separately.

## Honest limits

- Proactive output is deterministic evidence-based prioritization, not
  prediction or autonomous understanding of unstructured memory text.
- Schedule-conflict detection, research-change monitoring, notification
  delivery, and calendar/webhook connectors are not implemented.
## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability commit
`99f5bd27853145fec00fb80d356c6f45bdd52f50` on `main` by a non-force
fast-forward. Its tree `fa068d1e7f15dfdb8306abd93febdd53d1cb593a`
exactly matches the locally tested v0.14 tree in commit
`6c086530100181c3d77bf504cfa6abde995bbb68`.

SPARKLE CI run #29 (`33287645323`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`, including the compile/test, worker image build and
entrypoint, non-editable package install, and service lifecycle steps.

---

# 0.13.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed evidence

- The focused automation/API set passed 27 tests in 9.234 seconds.
- The dedicated service set passed 10 tests in 0.899 seconds, including a real
  foreground subprocess heartbeat → SIGTERM → draining → exit-0 workflow.
- The first full pre-release run passed 113 tests in 20.231 seconds before the
  SIGTERM case was added. After the signal-safety refinement, the final
  release-state `make check` passed all 114 tests in 21.288 seconds with no
  failures or errors. Dashboard JavaScript
  syntax and Git whitespace checks also passed.
- Offline editable installation initially succeeded as
  `sparkle-personal-ai==0.13.0a1`, and its entrypoints passed from the checkout.
  CI then correctly showed that this was insufficient wheel evidence. After
  the fix, a non-editable wheel was built without dependencies or an index,
  installed into a fresh virtual environment, and its `sparkle-automations`
  check → once → status workflow returned ready, one cycle, stopped state, and
  `credentials_exposed: false`. Both separate mode-0600 runtime configuration
  files were materialized from bundled defaults. With `SPARKLE_DATA_DIR`
  absent, the wheel also used `XDG_STATE_HOME/sparkle` rather than an installed
  code directory. The final corrected suite passed 116 tests in 20.023 seconds.

## Verified v0.13 capability paths

- The existing scheduler remains the execution core; the new
  `sparkle-automations` entrypoint adds supervision rather than a parallel
  scheduling implementation.
- Atomic claims carry bounded expiring tokens. Startup and each cycle recover
  expired claims, append an `AutomationLeaseExpired` run, and make work eligible
  again. A recovered/cancelled token cannot commit a result.
- A no-follow, mode-0600 POSIX flock prevents concurrent local service
  instances. Lifecycle state records only heartbeats, counts, timestamps,
  bounds, and safe error types.
- `--check`, `--once`, `--status`, and `--healthcheck` are exercised. The
  signal-safe SIGTERM handler performs no I/O, prevents another cycle, and
  normal control flow persists a clean stop after the active bounded operation.
- The non-root systemd profile supplies restart policy, forced-stop bound,
  read-only host protection, one writable state path, empty capabilities, and
  no embedded provider credential.

## Honest limits

- Recovery is at least once, not exactly once. Future external actions need
  independent idempotency keys.
- The systemd profile is inspected and the service lifecycle runs locally, but
  no named persistent host has installed the unit.
- Notification/calendar/webhook connectors, live MiniMax scheduled execution,
  and external delivery remain unavailable or unverified.

## GitHub publication and CI

The initial capability commit
`01050be68ffa8915c414f2fc181a380a24bbb0c5` has exact local/remote tree
`442d2b3ef5f6301b6b8d1471c538ecc949302e43`. CI run #26
(`33265181873`) passed Python 3.12, Python 3.13, and worker-image jobs, but its
new automation-service job failed: the built wheel omitted top-level
application/model configuration, so `--check` passed but `--once` raised
`FileNotFoundError`. Bundled separated defaults plus installed-runtime
materialization fix that packaging defect; replacement evidence follows.

Result: PASS AFTER CORRECTION — remote commit
`c223942a5b01c132629930f1735b7ba1a729a418` points to corrected tree
`6e097298640407b704e3ec2390de9aa010c44b31`, exactly matching local commit
`7e0b53a1b353f86e4cf50aeb59c610ba2a680226`. CI run #27
(`33265747867`) passed `test (3.12)`, `test (3.13)`, `worker-image`, and the
non-editable installed `automation-service` check/once/status lifecycle.

---

# 0.12.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Focused artifact/API regression

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_external_worker tests.test_artifacts tests.test_orchestrator_api
```

Result: PASS — 30 tests passed in 7.690 seconds after the database fixture fix.

### Compile and full regression suite

```bash
make check
```

Result: PASS — the final release-state run passed 104 tests in 19.728 seconds;
0 failures and 0 errors.
The first full run exposed a test-only database allocator that counted SQLite
WAL/SHM sidecars and could reopen an earlier database. The fixture now assigns
a monotonic database index. Production job IDs remain UUID4 values and the
append-only uniqueness constraint remains intact.

### Offline editable installation and installed modules

```bash
python3 -m pip install -e . --no-build-isolation --no-deps --no-index
python3 -m sparkle status
python3 -m sparkle.worker_service --check
```

Result: PASS — the zero-dependency core built and installed as
`sparkle-personal-ai==0.12.0a1` without an index. Application and worker modules
both reported `0.12.0-alpha.1`; the application truthfully reported `limited`
without a live model credential, while the explicitly unsafe process-worker
check reported ready with filesystem/network isolation false and credential
exposure false. An initial bare `sparkle` lookup exited 127 because this
executor omits its user script directory from `PATH`; direct installed-module
execution succeeded. A first result formatter also addressed isolation fields
at the response root instead of the `executor` object and exited with
`KeyError`; the corrected formatter passed. Neither failure was a product
execution failure.

## Verified v0.12 capability paths

- Approval-gated application packaging accepts no command, arguments,
  dependencies, target credentials, or environment input and never executes
  workspace code.
- Stable no-follow reads, strict count/size bounds, sensitive/reserved path
  rejection, and case-fold collision detection protect portable archive input.
- Canonical per-file manifests, source digests, fixed ZIP timestamps/modes,
  stored compression, sorted entries, and whole-artifact SHA-256 hashes make
  identical inputs byte reproducible.
- Artifacts are content-addressed and immutable. Identical source reuses verified
  bytes, changed source creates a new artifact, and tampering is refused.
- Deployment records are append-only reports only. They always expose
  `verification_status: unverified` and `external_action_executed: false`.
- CLI, authenticated API, dashboard, system status, builder-agent tool access,
  storage map, and documentation expose the same honest boundary.

## Not verified

- Target-specific application builds, package installation, signing/notarizing,
  cloud credentials, an external deployment action, or independent deployment
  attestation.
- Named remote worker/TLS deployment and live hostile-code namespace isolation.
- A real MiniMax-M3 response, real voice, browser/computer control, sensors, or
  robotics hardware.

## GitHub publication and CI

Result: PASS — remote commit
`37e4d05a73d0158963fd95ea93af8675fcb976b3` points to tree
`79969d371a213b1bd92b5a61564d64db9caa2c49`, exactly matching local capability
commit `3a7f1ed19b065aa834c4c002f90b7029c4283d6d`. SPARKLE CI run #24
(`33264113348`) completed successfully: `test (3.12)`, `test (3.13)`, and the
worker-image build/installed-entrypoint job all passed.

---

# 0.11.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — the corrected final v0.11 release-state run executed 96 tests in
24.139 seconds; 96 passed, 0 failed, 0 errors. Fifteen new cases cover the
worker server, real fixed child execution, application imports, timeout and
process-group termination, exact HMAC/schema/digest/path/limit validation,
private no-follow key files, replay and job conflicts, concurrency refusal,
fail-closed executor recovery, exact-key redaction, signed HTTP exchange,
Bubblewrap command and real preflight behavior, deployment policy, and the true
client → service → executor → signed response path.

### Actual isolation preflight

Result: BLOCKED/SAFE REFUSAL — `/usr/bin/bwrap` is installed and the executable
preflight ran, but this build executor does not permit the nested namespace
operation. `sparkle-worker` reports `ready: false`, the safe failure type, and
both filesystem/network isolation fields false. It does not execute submitted
source in this state. The development process executor completed the end-to-end
protocol test but correctly reported both isolation fields false.

### Deployment assets

Result: IMPLEMENTED/LOCALLY INSPECTED — the package exports a separate
`sparkle-worker` entrypoint. `worker_environment/` contains an unprivileged
image, read-only/capability-dropped Compose policy, private worker network,
Caddy TLS gateway, file-mounted secret, bounded state/tmp, health preflight,
and a hardened systemd service. Regression tests inspect the critical policy.
Docker is unavailable in the local executor, so the actual image build is
assigned to the v0.11 GitHub CI worker-image job and is not yet marked verified.

## Verified v0.11 capability paths

- The application and service remain separate processes/packages with no
  application store, model, agent, or provider dependency in the worker.
- The server accepts only `SPARKLE-WORKER/1` `python_unittest`, exact fields,
  valid paths/digests/UTF-8 source, fresh signed requests, and requested
  isolation controls.
- A SQLite replay store binds job ID to exact request hash. Exact completed
  duplicates replay one result; changed or in-flight duplicates conflict.
- The fixed runner applies wall/POSIX resource bounds, receives a cleared
  environment, imports submitted application code, redacts output, and writes
  only inside an ephemeral workspace.
- Production readiness requires a real Bubblewrap host-canary/environment/
  network preflight. Any dependency, denial, timeout, or failed check refuses
  jobs. Development process mode requires explicit unsafe opt-in and never
  reports filesystem/network isolation.
- Signing keys resolve through existing secret references or private no-follow
  files and are absent from source, status, logs, request persistence, and
  deployment configuration.

## Not verified

- A built/pulled container image, named remote deployment, public TLS endpoint,
  live isolated hostile-code execution, cgroup/seccomp behavior at a target,
  or independent promotion of sandbox claims to isolation evidence.
- A real MiniMax-M3 response, public application deployment, multi-user role
  authorization, real voice, browser/computer control, sensors, or robotics.

## GitHub publication and CI

Result: PASS — capability commit `de9b1c7f2c58178ea691982c231ab4a13358eba0`
published the worker and tree `a94eb92258ad971184a610546eea00b1160ae510`.
CI run #21 built the worker image and verified its entrypoint successfully, but
the Python 3.13 job exposed an environment-dependent test assumption: the fake
command-construction preflight still required an installed `bwrap` executable.
The implementation was not executed on that path. The test now supplies an
inert existing binary to its injected runner; the separate real-preflight case
continues to cover dependency discovery and fail-closed behavior.

The corrected remote commit is
`e1b014b2530d0ae5ee762573d81e093fb46aa834`. Its tree
`9db377f73b86589c34c50d5174fd5cf20ea727d1` exactly matches local commit
`55d897e0738fd3f4e52a3b41fcafd0bc2eeb4201`. SPARKLE CI run #22
(`33253329992`) completed successfully: `test (3.12)`, `test (3.13)`, the
worker-image build, and the installed image entrypoint check all passed.

---

# 0.10.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — the final release-state run executed 81 tests in 13.819 seconds;
81 passed, 0 failed, 0 errors. New evidence covers signed request/response exchange, source hashes
and bounds, strict result validation, safe failure persistence, operator-only
approval, API/CLI/dashboard integration, and explicit non-verification of
remote sandbox claims. Adversarial cases include bad signatures, stale
timestamps, wrong job IDs, unknown fields, inconsistent status, oversized
responses, transport failures, symlinks, hidden/credential-like/binary/
oversized files, and source containing the configured signing key.

Editable installation with build isolation disabled also succeeded for package
`sparkle-personal-ai==0.10.0a1`. Dashboard JavaScript syntax and Git whitespace
checks passed.

A first compact status-evidence formatter failed with a `TypeError` because it
tried to sort tool-record dictionaries. SPARKLE itself had exited 0 and written
valid JSON. The formatter was corrected and the status check was rerun
successfully; this was an evidence-script error, not a product test failure.

### External worker live/isolation status

Result: BLOCKED — the repository implements and tests the client protocol with
a deterministic signed worker double. No compatible external worker endpoint,
container image, or signing secret is configured in this build process. No
source was transferred and no remote code was executed. Worker sandbox fields
remain claims and `isolation_verified` is false.

## Verified v0.10 capability paths

- External execution is disabled by default, accepts only the fixed
  `python_unittest` operation, and requires explicit approval per submission.
- The operator facade is not in the agent/model tool registry, preventing a
  model from manufacturing source-transfer approval.
- Source packaging is workspace-confined, deterministic, UTF-8-only, hashed,
  and bounded; symlinks and sensitive/hidden/key-containing inputs are rejected.
- The endpoint must be credential-free HTTPS. Canonical requests and responses
  carry fresh timestamped HMAC-SHA256 authentication with a secret-resolved
  key that is never persisted or returned.
- Responses are size-bounded, schema-exact, job-matched, type-checked,
  status-consistent, HTTP/JSON/protocol-checked, output-redacted, and safely
  recorded. Redirects are denied. Transport and
  protocol failures store only bounded metadata and error type.
- CLI, authenticated API, read-only dashboard history, system status, data map,
  security guidance, and development guidance expose the actual boundary.

## Not verified

- A deployed compatible worker, hostile-code container isolation, network
  denial, ephemeral filesystem, cgroup/seccomp limits, job deduplication, or a
  real remote test. Authenticated worker claims are not proof of those controls.
- A real MiniMax-M3 response, production TLS/reverse proxy, multi-user role
  authorization, packaging/deployment, real voice, browser/computer control,
  sensors, or robotics hardware.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.10 capability
commit `d26ba2bb951d6943ad305c187d99d86f66d0b57a` on `main` without a force
update. Its Git tree `c440cfb9f01acadd2043b03dde21cfd61349d066`
exactly matches the locally tested tree in commit
`4691b09a5a3c989c309fdb55b2c10cce4aa305ef`.

SPARKLE CI run #19 (`33251219676`) completed successfully in 22 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

---

# 0.9.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 72 tests ran in 8.634 seconds; 72 passed, 0 failed,
0 errors. New evidence covers session creation, hashed-ID storage, absolute
expiry, bounded capacity/eviction, cookie attributes, CSRF rejection and
acceptance, session restoration after dashboard reload, logout/revocation,
bearer compatibility, configuration bounds, and secret-free audit/status paths.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — the dashboard JavaScript parsed and the working diff contained
no whitespace errors.

### Sanitized runtime and bind-policy checks

A fresh process with an empty environment except the documented runtime paths
ran `sparkle status` with exit 0. It reported version `0.9.0-alpha.1`, no
configured provider key, sessions disabled while API authentication is off,
zero active sessions, non-persistent session state, and
`credentials_exposed: false`.

A separate sanitized process supplied a placeholder API token, required API
authentication, requested a non-loopback bind, and deliberately left secure
cookies disabled. Startup failed closed with exit 1 and the exact policy error
`Non-loopback dashboard sessions require secure cookies and TLS termination`.
The placeholder credential did not appear in output.

The live provider smoke in a sanitized environment exited 2 at
`credential_presence`, with `configured: false` and
`secret_value_exposed: false`. No MiniMax request was made; this remains
BLOCKED rather than PASS.

## Verified v0.9 capability paths

- The existing secret-resolved bearer credential can be exchanged for an
  opaque 256-bit dashboard session without exposing it in response bodies,
  status, audit, or browser storage.
- Session IDs are represented only by SHA-256 digests in bounded process memory;
  sessions expire absolutely, evict the oldest entry at capacity, revoke on
  logout, and disappear on restart.
- Cookies are host-only, HttpOnly, `SameSite=Strict`, path `/`, and optionally
  `Secure`; a non-loopback session bind fails unless secure cookies are enabled.
- Every cookie-authenticated mutation requires a separate per-session CSRF
  token. The same-origin session endpoint recovers it after reload without
  exposing the HttpOnly session ID.
- Bearer clients remain compatible, session/login/logout routes are rate-,
  origin-, and audit-gated, and the audit schema still cannot accept headers,
  cookies, bodies, client identity, or credentials.
- The dashboard clears the credential field after submission, uses neither
  `localStorage` nor `sessionStorage`, restores valid sessions, and explicitly
  revokes them through **End session**.

## Not verified

- TLS termination, reverse-proxy forwarding policy, public deployment, or a
  real remote browser session. Secure-cookie configuration is enforced, but
  the standard-library server cannot provide or validate edge TLS.
- Multi-user identity, role/owner authorization, distributed session/rate-limit
  state, or session revocation across multiple processes.
- A real MiniMax-M3 response, hardened hostile-code container worker, real
  voice, browser/computer control, sensors, or robotics hardware.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.9 capability
commit `e8d988f8627c83e32b888a3bd7ab93e525542b12` on `main` without a force
update. Its Git tree `92b6ab3240de1cfbbe46e73947320d388d47ef5b`
exactly matches the locally tested tree in commit
`697927c47a98d964230d88944323361d2e0be0aa`.

SPARKLE CI run #17 (`33245128813`) completed successfully in 26 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

---

# 0.8.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 68 tests ran in 9.102 seconds; 68 passed, 0 failed,
0 errors. Added evidence executes real fixed unittest runs and covers resource
limits, wall-time process-group termination, strict parent-environment refusal,
stripped child environment, file-backed pre-persistence output bounds, redaction, symlink/size/command-field
rejection, persistence, and CLI/API/dashboard integration.

### Static and isolation-capability checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
unshare --user --map-root-user true
bwrap --ro-bind /usr /usr --proc /proc --dev /dev --unshare-net -- /usr/bin/true
```

Result: PASS for JavaScript and Git whitespace. Both kernel namespace checks
were BLOCKED with `Operation not permitted`; bubblewrap 0.9.0 is installed but
cannot create a namespace in this container. The implementation and status
therefore report `filesystem_isolation: false` and `network_isolation: false`.

### Isolated-status and provider smoke

A fresh, sanitized process ran `sparkle status` with exit 0 and reported
version `0.8.0-alpha.1`, workspace tests disabled, POSIX resource limits true,
filesystem/network isolation false, a sanitized parent, and arbitrary
commands false.

The live provider smoke in the same sanitized environment exited 2 at
`credential_presence`, with `configured: false` and
`secret_value_exposed: false`. No MiniMax request was made; this remains
BLOCKED rather than PASS.

## Verified v0.8 capability paths

- Execution is disabled by default and requires configuration opt-in plus
  explicit approval for each project run.
- The model/user cannot choose an executable, arguments, environment, package,
  or working directory; unsupported fields are rejected.
- A complete workspace scan rejects symlinks and enforces file-count,
  individual-file, and total-byte bounds before execution.
- The trusted child runs only isolated-mode standard-library unittest discovery
  and receives a fixed environment with no inherited provider/API variables.
- POSIX CPU, memory, file-size, descriptor, process, and core limits are applied;
  the parent kills the whole process group on wall timeout.
- A parent containing any non-allowlisted environment variable is refused, because
  same-user process access cannot be safely excluded without a real sandbox.
- Results and bounded credential-pattern-redacted output persist separately and
  are exposed through the CLI, API, dashboard, system status, and tool registry.

## Not verified

- Hostile-code filesystem or network isolation; the runner is not a container
  sandbox and must use a disposable, secret-free worker.
- Package installation, arbitrary application/build execution, packaging, or
  deployment.
- A real MiniMax-M3 response, remote authenticated UI, role authorization, TLS,
  real voice, browser/computer control, sensors, or robotics hardware.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.8 capability
commit `228c302fa23927356e72723f792530ab1e948cee` on `main` without a force
update. Its Git tree `c756d7cbdc239fcf1c518b22f5b01dcf7f6e1344`
exactly matches the locally tested tree in commit
`155dd04335f82d8edad52c9a9e14430d38954f17`.

SPARKLE CI run #15 (`33239100793`) completed successfully in 19 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

The v0.8 documentation checkpoint commit
`cd0fdfb96365122985081614184e3af3d7157a39` was then verified by SPARKLE CI
run #16 (`33239280620`) in 18 seconds; both Python matrix jobs and their
`Compile and test` steps completed successfully.

---

# 0.7.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 61 tests ran in 8.744 seconds; 61 passed, 0 failed,
0 errors. Added evidence covers deterministic fixed-window enforcement/reset,
bounded client state, rate limiting before authentication, response quota
headers, HTTP 429 behavior, query-free audit paths and request logs, and absence of tokens,
query values, origins, headers, and client identifiers from audit records.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed and the working diff contained no
whitespace errors.

### Runtime security and provider smoke

Authenticated `sparkle status` with a placeholder test token exited 0. Output
reported authentication required/configured, `credentials_exposed: false`, and
the 120-request/60-second quota; the placeholder value was absent.

`python -m sparkle serve` with a non-loopback host and authentication disabled
exited 1 before binding. Required authentication with no token also exited 1
before binding. Both messages were concise and contained no traceback or
credential value.

The live MiniMax smoke command exited 2 at credential presence with
`configured: false` and `secret_value_exposed: false`; no provider request was
made, so this remains BLOCKED rather than PASS.

The first composite smoke wrapper had a shell quoting error after its successful
status command. The simpler rerun produced all results above; this was a test
harness error, not an application failure.

## Verified v0.7 capability paths

- Every API method consumes a per-client fixed-window quota before origin or
  authentication checks, including OPTIONS requests.
- Client buckets are protected by a lock, expire by window, and are capped at
  10,000 entries with deterministic stale/oldest eviction.
- Quota headers accompany API responses; blocked requests return HTTP 429 and
  `Retry-After` without reaching authorization or application state.
- One API audit record is attempted before each API response. The store accepts
  only method, query-free `/api/` path, status, coarse outcome, bounded
  duration, and timestamp.
- Unknown API paths are normalized to `/api/[unknown]` in both audit records
  and request logs so attacker-controlled path segments are not retained.
- Audit storage is separate from execution traces, and audit failures cannot
  interrupt response delivery.
- System status, `GET /api/audit`, and the dashboard expose only aggregate quota
  configuration and secret-free audit fields.

## Not verified

- A real MiniMax-M3 network response.
- Role/owner authorization, authenticated browser sessions, TLS termination,
  distributed edge rate limiting, configured audit retention, or production
  deployment.
- Execution of generated applications/tests, builds, packaging, or deployment.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.7 capability
commit `c379ec4b01f00cf03de6ede7028b7df5bd704a3f` on `main` without a force
update. Its Git tree `42f6ed82862757c88cd989f6b9b7069806b69bbe`
exactly matches the locally tested tree in commit
`1f7bbea8811a259ed2ac06dd00e1bfe784327428`.

SPARKLE CI run #13 (`33228183633`) completed successfully in 24 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

The documentation checkpoint commit
`d98d90827ac57487b3ffff8b0af6a89fccd2c6e7` was then verified by SPARKLE CI
run #14 (`33228285510`) in 23 seconds; both Python matrix jobs and their
`Compile and test` steps completed successfully.

---

# 0.6.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 54 tests ran in 6.953 seconds; 54 passed, 0 failed,
0 errors. Added evidence covers bearer success/failure, no secret in status or
responses, unauthorized non-mutation, exact same-origin and explicit allowlist
behavior, wildcard/invalid-origin rejection, preflight, boolean configuration,
non-loopback/missing-token startup refusal, and traceback-free console errors.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed and the working diff contained no
whitespace errors.

### API-security command smoke

Authenticated `sparkle status` with a fake test token exited 0 and reported only
`authentication_required: true`, `token_configured: true`, an allowed-origin
count, and `credentials_exposed: false`. The token text was absent from output.

`python -m sparkle serve` with a non-loopback host and no authentication exited
1 before binding with `Non-loopback API binding requires authentication`.
Required authentication with no token also exited 1 before binding. Both
refusals contained no traceback or secret value.

### Live-provider smoke test

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence`, reported
`configured: false` and `secret_value_exposed: false`, and made no MiniMax
request. This is not a live-provider PASS.

## Verified v0.6 capability paths

- Optional bearer authentication protects every `/api/` route before request
  bodies are read or state is accessed.
- Tokens are resolved only from configured environment secret references and
  compared in constant time; status returns presence booleans only.
- Same-origin requests are allowed; cross-origin requests require an exact
  configured HTTP(S) origin; wildcard and malformed origins are rejected.
- Origin-approved preflight advertises only GET, POST, OPTIONS, Authorization,
  and Content-Type.
- Required authentication without a token fails server startup, and a
  non-loopback bind is refused unless authentication is required and configured.

## Not verified

- A real MiniMax-M3 network response.
- Role/owner authorization, authenticated browser sessions, TLS termination,
  rate limiting, or production deployment.
- Execution of generated applications/tests, builds, packaging, or deployment.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.6 capability
commit `b003f4caaef856014e176841ab086f0c54aae0a1` on `main` without a force
update. Its Git tree `fb593326823b9bcb8956f9e37a7ae717b6880689`
exactly matches the locally tested tree in commit
`a090c2bd8e2fc0767d771c1745d8064d0d857258`.

SPARKLE CI run #11 (`33227542117`) completed successfully in 17 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

Documentation evidence commit
`a2d31ca84693ab3884b99ac81d5aca70ffabf822` also passed SPARKLE CI run #12
(`33227624913`) in 14 seconds; both Python matrix jobs and their compile/test
steps succeeded.

---

# 0.5.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 47 tests ran in 4.910 seconds; 47 passed, 0 failed,
0 errors. The added coverage verifies Python compilation without execution,
JavaScript and JSON validation, syntax-failure evidence, missing-Node handling,
path traversal and symlink rejection, undeclared-field/type rejection, explicit
approval, API integration, persistence, and a CLI scaffold-to-verify workflow.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed and the working diff contained no
whitespace errors.

### Isolated runtime status

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle status
```

Result: PASS — process exited 0 and reported version `0.5.0-alpha.1`, 16
built-in agents, eight registered tools, ready verification storage,
`static_verification: true`, and `arbitrary_command_execution: false`.

### Live-provider smoke test

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence` with
`configured: false` and `secret_value_exposed: false`. No MiniMax request was
made; this is not a live-provider PASS.

## Verified v0.5 capability paths

- Generated workspaces can be checked with `python_compile`,
  `javascript_syntax`, and `json_parse` only.
- Python is compiled without module execution; JavaScript uses Node `--check`;
  JSON uses the standard parser.
- Project paths reject traversal, missing files, symlinks, wrong file types,
  undeclared fields, more than 50 checks, and files over 500 KB.
- Node runs from an absolute discovered binary, without a shell or inherited
  provider secrets, with a five-second timeout and 8,000-character output cap.
- Verification results and durations persist outside source code and appear in
  the CLI, API, dashboard, agent tools, and system status.

## Not verified

- A real MiniMax-M3 network response.
- Execution of generated applications or tests, package installation, builds,
  packaging, or deployment.
- Production service scheduling or external notification delivery.
- Production deployment, authentication, and authorization.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.5 capability
commit `f0f880e3c011fd8ecae33a572347c399e40a80a6` on `main` without a force
update. Its Git tree `bfaaec45474c385327bc430b5be2cddd9124a16b`
exactly matches the locally tested tree in commit
`d0f31c9b8f0c03f155032b48b25c57bf9c5690cc`.

SPARKLE CI run #9 (`33227000794`) completed successfully in 14 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

---

# 0.4.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — latest release-state run executed 41 tests in 4.293 seconds;
41 passed, 0 failed,
0 errors. Coverage added for persistent generated-agent lifecycle, bounded
application workspaces, automation claiming/execution/retry/recurrence/cooldown
and history, memory restore/export/delete/backup, and knowledge
list/delete/backup.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed successfully and the working diff
contained no whitespace errors.

### Isolated runtime status

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle status
```

Result: PASS — process exited 0 and reported version `0.4.0-alpha.1`, 16
built-in agents, seven registered tools, ready generated-agent/automation/build
stores, zero initial records, and `arbitrary_command_execution: false`. Overall
status was correctly `limited` because the MiniMax credential was absent.

### Live-provider smoke test

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence` with
`configured: false` and `secret_value_exposed: false`. No provider request was
made. This is not a live-provider PASS.

## Verified v0.4 capability paths

- Generated agents validate, persist outside source, hot-load, route, reload,
  replace, and remove while built-ins remain protected.
- Agent installation and workspace scaffolding require explicit approval.
- Workspaces reject traversal, symlinks, unsafe names, unapproved overwrite,
  oversized files, and oversized manifests; file hashes are recorded.
- Once/daily/weekly/conditional automations claim work, run single or multiple
  agents, retry within bounds, record execution evidence, reschedule, and honor
  condition cooldowns.
- Automation execution traces use input source `automation`.
- Memory supports archive, restore, permanent delete, export, and database
  backup; knowledge supports source listing, source deletion, and backup.
- The CLI, HTTP API, system status, and dashboard expose the new capabilities.

## Not verified

- A real MiniMax-M3 network response.
- Arbitrary build/test execution, packaging, or deployment.
- Production service scheduling or external notification delivery.
- Production deployment, authentication, and authorization.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — the private repository `pexxoraa/SPARKLE` received v0.4
capability commit `d5984f709b3a0bd67b0131e4306e2c00498ef514` on `main` without
a force update. Its Git tree
`f472afe902d8bd902cddf7a7a4eb3f954cd9d555` exactly matches the locally tested
tree in commit `027c19a4649483086d55a42f0853a0e8c37a0ee8`.

SPARKLE CI run #7 (`33226436851`) completed successfully in 15 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step. The workflow reported no artifacts and no
annotations.

---

# 0.3.0-alpha.1 verification report

Date: 2026-08-28 UTC

## Executed commands

### Environment inspection

Executed OS, CPU, RAM, storage, language/toolchain, GPU, audio, browser, Docker,
and editor checks. Recorded results are in `ENVIRONMENT.md`.

### Compile and regression suite

```bash
make check
```

Latest post-CI-upgrade result: PASS — 32 tests ran in 2.497 seconds; 32 passed,
0 failed, 0 errors.

An earlier `make check` attempt failed during test discovery with five
`ModuleNotFoundError: sparkle` errors because the Makefile omitted
`PYTHONPATH=src`. The Makefile was corrected and the exact command was rerun to
the passing result above.

### Runtime status

```bash
python3 -m sparkle status
```

Result: PASS — process exited 0; model registry, 16 agents, five tools, memory,
knowledge, tracing, automation, voice state, proactive state, and presence state
were reported. Overall runtime state was correctly `limited` because no accepted
MiniMax secret reference exists in the build process.

### Live-provider smoke test

```bash
python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence`; configured was
false and `secret_value_exposed` was false. No API request was made. This is not
a live-provider PASS.

### Secret-pattern inspection

Searched tracked candidate files for `sk-` and `Bearer` patterns. Matches were
limited to documentation placeholders, runtime header construction, and fake
test fixtures. No credential value was found.

## Verified paths

- Model mapping, response parsing, retries, streaming, and tool state.
- Registry add/remove/enable/disable/activate.
- Memory upsert/search/archive and category boundaries.
- Knowledge ingest/chunk/search and format rejection.
- Trace sequence, success/failure metadata, and redaction.
- Automation due selection and proactive deadline alerts.
- Calculator AST and file-path confinement.
- Agent routing, tool loop, multi-agent synthesis.
- HTTP health/chat/memory/knowledge/static dashboard and security headers.

## Not verified

- Real MiniMax network response.
- Production deployment.
- Voice, wake word, camera, browser automation, GUI computer control, or robots.

## GitHub publication

Result: PASS — the source is published to the private repository
`pexxoraa/SPARKLE` on branch `main`. Connector access was limited to the
authorized account and the target repository; no unrelated repository was
modified.

The remote foundation tree
`dd4bd9833f9675cc8333065d2487d5dfb2317312` exactly matches local foundation
commit `d5c001be05193411d7b90b03d09390e2702f8e82`. The imported release-state tree
`66ccd2f802d93e6a0e91494db693936141e64aa9` exactly matches local commit
`01f8e816a55513e647674c21ea12c1ef6e495db2` and is recorded remotely in commit
`9561b1208e5c44d744bf7293fef8a7c6f7ee7361`.

Because the target was an empty repository and the connector's commit API
requires an existing parent, publication includes one bootstrap commit before
the imported foundation and release-state commits. This changes commit IDs but
not the verified file trees.

## GitHub Actions

Result: PASS — SPARKLE CI run #5 completed successfully in 15 seconds for
commit `32be63286ca0ce9b5dd07eea6b07c4942a93a5a9`. Both matrix jobs passed on
Python 3.12 and Python 3.13. The workflow uses `actions/checkout@v7` and
`actions/setup-python@v7`; the successful run reported no annotations.
