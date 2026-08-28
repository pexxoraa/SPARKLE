# Model management

Each model record defines an internal ID, provider, provider model ID, adapter,
capabilities, enabled state, context/output limits, parameters, endpoint, and
secret references.

Supported registry operations:

- `list()` — inspect records and credential presence.
- `add(record)` — validate and persist a new model record.
- `remove(id)` — remove a non-active record.
- `set_enabled(id, bool)` — enable or disable a non-active record.
- `activate(id)` — select an enabled record as the default.
- routing — map capabilities to configured records.
- `inject()` — deterministic adapter injection for tests.

Changing a provider requires a new adapter under `providers/` and a registry
record. Agents, memory, tools, API, dashboard, and orchestration remain unchanged.

Use `sparkle status` to verify configuration presence and
`sparkle smoke-test --live` to verify a real provider response.
