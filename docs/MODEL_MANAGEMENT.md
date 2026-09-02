# Model management

Each model record defines an internal ID, provider, provider model ID, adapter,
capabilities, supported content modalities, enabled state, context/output
limits, parameters, endpoint, and secret references.

Supported registry operations:

- `list()` — inspect records and credential presence.
- `add(record)` — validate and persist a new model record.
- `remove(id)` — remove a non-active record.
- `set_enabled(id, bool)` — enable or disable a non-active record.
- `activate(id)` — select an enabled record as the default.
- routing — map capabilities to configured records.
- `inject()` — deterministic adapter injection for tests.

Built-in providers register adapter factories, and local/integrating code can
provide additional factories to `ModelRegistry` without changing routing or
core orchestration. Every factory result must match the configured provider and
model identity and implement every declared modality. Provider-specific code
remains behind `ModelAdapter`; agents, memory, tools, API, dashboard, and
orchestration remain unchanged.

Registry loading validates bounded safe identifiers, unique roles and
modalities, boolean enabled state, environment-style secret references, enabled
routing targets, and capability-to-role agreement. Secret-value fields are
rejected recursively. Failed enable/disable/remove operations roll back fully,
and fallback routing is deterministic by record ID. Factory-created production
adapters cannot expand the modalities declared by their records. Explicit
`inject()` remains a test-only override for simulating future providers; it is
never loaded from configuration.

For a multimodal provider, declare a non-empty unique subset of `text`, `image`,
`audio`, and `document` in the registry and implement the same set in the
adapter's `supported_modalities`. The adapter alone maps
`SPARKLE-CONTENT/1` parts to the provider protocol. Registry declarations do
not make a provider capable; unsupported requests fail before the provider is
called. Existing records without the field remain compatible and default to
text.

Use `sparkle status` to verify configuration presence and
`sparkle smoke-test --live` to verify a real provider response.
