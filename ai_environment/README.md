# AI environment

This boundary owns provider/model configuration. Runtime adapter code is kept
in the installable package at `src/sparkle/providers/`; registry and routing
code lives in `src/sparkle/registry.py`. Application configuration does not
contain provider endpoints, model IDs, or credential references.
