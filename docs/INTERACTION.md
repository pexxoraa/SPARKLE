# Browser and computer interaction

SPARKLE defines provider-neutral browser and computer boundaries in
`sparkle.interaction`. They are deliberately unavailable by default and are
not registered as agent tools in v0.30.

## Browser contract

`BrowserRequest` permits credential-free HTTPS URLs on port 443, requires an
exact host allowlist, and binds timeout and returned-text limits. The service
revalidates the final URL after an adapter returns, so redirects cannot escape
the request allowlist. Credentials in URLs, non-HTTPS schemes, non-standard
ports, malformed ports, unapproved destinations, oversized results, and
out-of-policy redirects fail closed.

The injected deterministic adapter used by tests is a **TEST HARNESS**. There
is no live browser executable or remote browser provider in this release.

## Computer contract

`ComputerAction` is a closed, bounded union of screenshot, click, text entry,
and key actions. It does not accept shell commands, arbitrary executable paths,
or untyped payloads. The default adapter fails closed.

The injected deterministic adapter used by tests is a **TEST HARNESS**. There
is no live GUI session, display server, or computer-control provider in this
release.

## Evidence status

| Boundary | State | Evidence |
|---|---|---|
| Provider-neutral contracts | TESTED | Validation and fail-closed unit tests |
| Deterministic adapters | TESTED | Local harness only |
| Live browser execution | BLOCKED | No executable/provider configured |
| Live computer execution | BLOCKED | No GUI/provider configured |
| Agent tool exposure | DEFERRED BY DESIGN | Requires separate authorization, policy, and live-provider evidence |

These contracts do not change controlled execution, Level 3 isolation, or
deployment status.
