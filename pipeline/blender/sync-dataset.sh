#!/usr/bin/env bash
# Copy a finished render dataset from Windows staging into ext4 (Phase 8b).
# Training I/O must never run against /mnt/* (SETUP.md rule 9).
# Usage: sync-dataset.sh <scene> [src-root] [dst-root]
set -euo pipefail

SCENE=${1:?usage: sync-dataset.sh <scene> [src-root] [dst-root]}
SRC=${2:-/mnt/d/renders}/$SCENE
DST=${3:-$HOME/datasets}/$SCENE

if [ ! -d "$SRC" ]; then
    echo "error: source dataset $SRC not found" >&2
    exit 1
fi

mkdir -p "$DST"
if command -v rsync >/dev/null; then
    rsync -a --info=progress2 "$SRC/" "$DST/"
else
    cp -a "$SRC/." "$DST/"
fi
echo "synced $SRC -> $DST ($(du -sh "$DST" | cut -f1), $(find "$DST" -type f | wc -l) files)"
