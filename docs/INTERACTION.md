# Browser and computer interaction

SPARKLE defines provider-neutral browser and computer boundaries in
`sparkle.interaction`. The main `SparkleSystem` and `sparkle-interaction` CLI
instantiate the concrete read-only `SafeHTTPSBrowserAdapter`; GUI computer
control remains disabled unless a host-specific adapter is explicitly supplied.
Neither boundary is registered as a general agent tool in v0.30.

## Browser runtime

`BrowserRequest` permits credential-free HTTPS URLs on port 443, requires an
exact operator-owned host allowlist, and binds timeout and returned-text limits.
The concrete stdlib runtime rejects non-public DNS results, pins a validated IP
for the TCP connection while retaining the hostname for TLS certificate/SNI
validation, handles redirects itself, and revalidates every redirect against the
same HTTPS/host/DNS policy. Credentials in URLs, non-HTTPS schemes, non-standard
ports, malformed ports, private/loopback/link-local/reserved destinations,
oversized results, unsupported content types, compressed bodies, redirect loops,
and out-of-policy redirects fail closed.

Browser sessions persist allowed hosts, TTL, optimistic revision and bounded
event history. Browser output is read-only extracted text; page scripts are not
executed and requests carry no cookies, authorization headers or request body.
`live_browser_verified` remains false until real host/network acceptance is run.

## Computer contract

`ComputerAction` is a closed, bounded union of screenshot, click, text entry,
and key actions. It does not accept shell commands, arbitrary executable paths,
or untyped payloads. Computer sessions persist operator-approved action kinds,
TTL, optimistic revision and history. The default computer adapter fails closed.

A real GUI runtime still requires a host-specific adapter, OS display/session
permissions and manual action/screenshot acceptance. Injected deterministic
adapters used by tests are test harnesses, not evidence of GUI control.

## Authorization boundary

Browser and computer execution are intentionally not exposed as unrestricted
agent tools. Starting a session establishes operator-owned destinations/actions;
each subsequent operation is revision-bound to that session. A model cannot
create its own network or GUI authorization through the normal tool registry.

## Evidence status

| Boundary | State | Evidence |
|---|---|---|
| Provider-neutral contracts | IMPLEMENTED | bounded validation and fail-closed tests |
| Safe HTTPS browser runtime | IMPLEMENTED | concrete stdlib adapter and deterministic transport-policy tests |
| Browser session integration | IMPLEMENTED | main runtime + operator CLI + persisted revisioned sessions |
| Live browser host/network acceptance | EXTERNAL ACCEPTANCE | no live acceptance campaign in this milestone |
| Computer contract/session lifecycle | IMPLEMENTED | typed actions, persistence, permissions and test adapters |
| Live computer execution | EXTERNAL ADAPTER/HOST | concrete GUI adapter, permissions and live evidence required |
| Agent tool exposure | DEFERRED BY DESIGN | operator-owned authorization remains outside general model tools |

These boundaries do not change controlled execution, Level 3 isolation, or
deployment status.
