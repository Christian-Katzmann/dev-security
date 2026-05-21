#!/bin/bash
set -euo pipefail

export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
exec python3 -m security_observatory.cli dashboard --port "${PORT:-8766}" --no-open
