# AI environment

The AI environment contains registry records, routes, provider adapters, and
model request/response contracts. The application asks for a capability; it
does not select a vendor endpoint.

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
