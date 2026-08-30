# AI environment

The AI environment contains registry records, routes, provider adapters, and
model request/response contracts. The application asks for a capability; it
does not select a vendor endpoint.

Each registry record declares a bounded `modalities` list and every adapter
exposes its authoritative runtime `supported_modalities`. Routing first follows
the configured capability and then may select another enabled compatible
adapter. If no adapter supports the complete request, execution raises a safe
provider-neutral unsupported-modality error before credential resolution or
network access. Existing registry records that omit the field default to
`["text"]` for backward compatibility.

Current MiniMax-M3 contract, verified against MiniMax documentation on
2026-08-28:

| Field | Value |
|---|---|
| Model ID | `MiniMax-M3` |
| Endpoint | `https://api.minimax.io/anthropic/v1/messages` |
| Authentication | `Authorization: Bearer <API_KEY>` |
| Context | 1,000,000 input + output tokens |
| Recommended M3 output limit | 131,072 tokens |
| Maximum M3 output limit | 524,288 tokens |
| Streaming | Server-sent events |
| Tool calling | `tools`, `tool_use`, `tool_result` blocks |
| Thinking | `adaptive` or `disabled`; disabled by default on Messages API |
| Service tier | `standard` or `priority` |
| Published account limit | 200 RPM and 10,000,000 TPM |

Sources:

- https://platform.minimax.io/docs/api-reference/api-overview
- https://platform.minimax.io/docs/api-reference/text-chat-anthropic
- https://platform.minimax.io/docs/guides/text-m3-function-call
- https://platform.minimax.io/docs/guides/rate-limits
- https://platform.minimax.io/docs/api-reference/errorcode

The adapter uses the recommended Messages HTTP surface directly. It does not
install the Anthropic SDK and does not expose that protocol to agents.
The current MiniMax adapter advertises text only. SPARKLE does not infer or
hard-code a MiniMax image, audio, or document mapping without separately
verified provider documentation and executable tests.
