# Installation

## Local development

```bash
git clone https://github.com/pexxoraa/SPARKLE.git
cd SPARKLE
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
make check
sparkle serve
```

Windows PowerShell activation is `.venv\Scripts\Activate.ps1`.

## Optional document support

```bash
python3 -m pip install -e '.[documents]'
```

## Reproducibility

Core execution uses Python 3.12 standard-library modules. Optional document
extras specify minimum versions in `pyproject.toml`. Runtime databases are
created automatically on first start.

The verified repository is private. Cloning `pexxoraa/SPARKLE` requires an
authorized GitHub account.

## External worker

Installing the core package also installs `sparkle-worker`, but production
execution belongs on a separate Linux host or container runtime. Use the
container/Caddy or systemd profiles in `worker_environment/` and follow
[`WORKER.md`](WORKER.md). Do not run the production worker inside the main
SPARKLE API process and do not enable the external-worker client before the
worker's `--check` reports ready on its actual host.

## Secured API binding

Keep the default loopback bind for local use. Before binding to a non-loopback
address, enable API authentication and place `SPARKLE_API_TOKEN` in the process
secret manager. Do not put the value in configuration, source, command history,
or service arguments.

```bash
export SPARKLE_API_AUTH_REQUIRED=true
export SPARKLE_SESSION_COOKIE_SECURE=true
sparkle serve --host 0.0.0.0
```

Startup refuses this bind if the token reference is absent or session
authentication is enabled without secure cookies. The built-in server does not
provide TLS; terminate TLS at a trusted edge before any network exposure and
forward only from that trusted edge. A bearer-only API can explicitly set
`SPARKLE_SESSION_AUTH_ENABLED=false` instead of enabling dashboard sessions.

## Supervised automations

The core installation exports `sparkle-automations` separately from the API.
Run a local lifecycle check with:

```bash
sparkle-automations --check
sparkle-automations --once
sparkle-automations --status
```

For a persistent POSIX deployment, install the non-root systemd unit in
`automation_environment/` and provision the runtime data directory and model
credential through the host secret manager. The automation process must share
SPARKLE's data directory but should not run inside the API process.
