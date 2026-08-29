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

## Generated-workspace verification

`DevelopmentVerifier` supports only `python_compile`, `javascript_syntax`, and
`json_parse`. Python uses the built-in compiler without executing the module.
JavaScript uses an absolute Node.js binary with `--check`, a five-second timeout,
no shell, a minimal environment containing no SPARKLE/provider secrets, and
bounded output. JSON is parsed without application hooks.

Checks are confined to an existing generated project and reject traversal,
symlinks, wrong file types, missing files, undeclared fields, more than 50
checks, and files over 500 KB. Syntax failures are successful verifier
executions with a recorded `failed` result; verifier contract violations are
client errors.

Do not widen this verifier into a general command runner. Executing generated
code requires a separate isolation design with filesystem, process, network,
resource, secret, and artifact boundaries.
