# Installation

## Local development

```bash
git clone <SPARKLE_REPOSITORY_URL>
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

There is no GitHub repository URL in this file yet because no owned SPARKLE
repository existed at build time. Replace the placeholder only after repository
creation is verified.
