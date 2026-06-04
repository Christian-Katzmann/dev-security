#!/bin/bash
set -euo pipefail

# Serve the sealed DëvSec Design Lab as static files.
# No backend, no build step — just the prototype screens. Loopback-only.
# app-it invokes this with cwd = baked PROJECT_ROOT and PORT set; the $0-derived
# ROOT also makes `bash scripts/run-design-lab.sh` work from the repo root.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 -m http.server "${PORT:-8788}" --bind 127.0.0.1 --directory "$ROOT/design-lab"
