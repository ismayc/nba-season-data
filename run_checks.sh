#!/bin/bash
# Checks on the committed CSVs. PY overrides the interpreter; the default is
# the family's shared venv in the parent folder (see basketball-analysis-tools).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-$(cd .. && pwd)/.venv/bin/python}

echo "=== output checks (pytest) ==="
$PY -m pytest tests/python -q
