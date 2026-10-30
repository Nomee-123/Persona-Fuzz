#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi

"$PY" -m engine.cli replay sample
"$PY" -m engine.cli serve
