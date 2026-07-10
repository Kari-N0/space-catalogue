#!/usr/bin/env bash
# Launch ComfyUI headless on 127.0.0.1:8188 (Phase 6, SETUP.md).
# Extra args pass through, e.g.: comfy-server.sh --lowvram
set -euo pipefail

COMFY=~/apps/ComfyUI
exec "$COMFY/.venv/bin/python" "$COMFY/main.py" \
    --listen 127.0.0.1 --port 8188 "$@"
