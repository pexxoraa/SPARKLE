# Development

1. Add domain code beneath `src/sparkle/`.
2. Keep provider behavior beneath `providers/`.
3. Add or change configuration without embedding credentials.
4. Add deterministic tests for success, failure, and security boundaries.
5. Run `make check` before committing.
6. Update `BUILD_STATE.md` and `ACCEPTANCE.md` using actual evidence.

To add a provider, implement `ModelAdapter.complete()`, optionally `stream()`,
and `health()`, register the adapter class, add a model record, and test the
mapping with a fake HTTP opener. Do not add provider types to agents.
