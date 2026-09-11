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

`live_browser_verified` remains false until the operator performs real host/network
acceptance. GUI computer interaction remains adapter-driven and externally
unconfigured by default; the safe browser implementation does not imply desktop GUI
control.
