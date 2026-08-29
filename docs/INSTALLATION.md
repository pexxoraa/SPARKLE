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

## Secured API binding

Keep the default loopback bind for local use. Before binding to a non-loopback
address, enable API authentication and place `SPARKLE_API_TOKEN` in the process
secret manager. Do not put the value in configuration, source, command history,
or service arguments.

```bash
export SPARKLE_API_AUTH_REQUIRED=true
sparkle serve --host 0.0.0.0
```

Startup refuses this bind if the token reference is absent. This control does
not provide TLS; terminate TLS at a trusted edge before any network exposure.
