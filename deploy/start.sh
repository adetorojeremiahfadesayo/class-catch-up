#!/bin/sh
set -eu

cd /app/services/api
uv run --no-sync python -m app.bootstrap
uv run --no-sync python -m app.worker &
exec uv run --no-sync python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
