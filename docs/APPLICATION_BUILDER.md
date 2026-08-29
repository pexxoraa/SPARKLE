# Application Builder

The Application Builder is implemented as a specialized agent routed to a
coding-capable model and allowed safe file/context tools. Its instruction covers
requirements, UX, architecture, implementation, tests, packaging, and
deployment. It can invoke an approval-gated workspace scaffold with a project
name and UTF-8 file map.

Workspaces are confined beneath the configured applications data root. The
manager rejects absolute paths, traversal, symlinks, invalid project names,
unapproved overwrites, more than 100 files, files over 250 KB, and manifests
over 1 MB. Each write records its byte count and SHA-256 digest in
`data_environment/builds.sqlite3`.

```bash
sparkle scaffold app.json --approve
```

Current limitation: SPARKLE intentionally cannot execute arbitrary shell or
build commands through its runtime API. A permissioned development runner,
test-evidence collector, packager, and deployment adapter are still required
before autonomous application delivery can be marked complete.
