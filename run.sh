#!/usr/bin/env bash
cd "$(dirname "$0")"
export HF_HUB_OFFLINE=1
. .venv/bin/activate
echo "Open http://localhost:8320"
python -m uvicorn app.server:app --host 127.0.0.1 --port 8320
