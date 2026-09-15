# Safe browser runtime

SPARKLE includes a concrete read-only HTTPS browser adapter in `browser_runtime.py`.
The adapter is used by the `sparkle-interaction` operator CLI and preserves the
persistent session/revision model implemented by `interaction.py`.

The browser accepts only credential-free HTTPS URLs on port 443 and only hosts that
are explicitly allowlisted by the operator-owned browser session. Each DNS lookup is
bounded and every returned address must be globally routable; loopback, private,
link-local, multicast, reserved and other non-public addresses fail closed. The live
transport connects to a prevalidated IP while retaining the original hostname for TLS
certificate/SNI validation, reducing DNS-rebinding exposure between policy validation
and socket connection.

Redirects are handled by SPARKLE rather than urllib automatic redirect logic. Every
hop is revalidated against the same HTTPS/host policy and DNS boundary, redirect loops
fail, and no more than five redirects are followed. Requests carry no cookies,
authorization headers, user credentials, or request body.

Responses are bounded to at most 1 MB and further constrained by the requested text
limit. Only HTML, plain text, JSON and XML text media types are accepted. Compressed
content is rejected to avoid decompression-bomb ambiguity. HTML is parsed with the
standard-library `HTMLParser` into bounded title/text output; scripts are never
executed.

Host acceptance is a separate, operator-owned gate. Run it only on the approved
networked host and write a new evidence file:

```bash
sparkle-interaction accept-browser --output /secure/new-browser-acceptance.json
sparkle-interaction record-browser-acceptance /secure/new-browser-acceptance.json \
  --operator <operator-id> --ttl-hours 720
sparkle-interaction browser-acceptance-status
```

The fixed checkset requires real public HTTPS success, rejection of loopback/private/
reserved destinations, TLS-hostname failure, redirect revalidation, output-bound
enforcement, and a reopened persistent session lifecycle. The artifact contains no
page text, URL, address, credential, or exception message. It is created as a new
owner-only regular file and is bound to the exact browser/interaction/CLI source hash,
safe-adapter identity, SPARKLE version, fixed approved-host-set digest, stable host
identity digest, and timestamps. The raw machine identity is never exported.

Acceptance records are append-only. Status reports `live_browser_verified=true` only
for the latest record matching the current build, adapter, and checkset while it is
unexpired and unrevoked. Revoke obsolete evidence explicitly:

```bash
sparkle-interaction revoke-browser-acceptance <record-id> \
  --operator <operator-id> --reason <bounded-reason>
```

Configuration and current health remain separate from point-in-time acceptance;
status never performs an implicit network request. GUI computer interaction remains
adapter-driven and externally unconfigured by default, and browser acceptance does
not imply desktop GUI control.
