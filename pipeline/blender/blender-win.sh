#!/usr/bin/env bash
# Run Windows Blender headless from WSL (Phase 8a, SETUP.md).
# Resolves the newest Blender 5.x under Program Files, converts absolute
# path arguments to Windows form with wslpath -w, and invokes blender.exe
# via WSL interop — Cycles renders run Windows-side at full OptiX speed.
set -euo pipefail

BF="/mnt/c/Program Files/Blender Foundation"
BLENDER_EXE=$(ls -d "$BF"/Blender\ 5.*/blender.exe 2>/dev/null | sort -V | tail -1)
if [ -z "$BLENDER_EXE" ]; then
    echo "error: no Blender 5.x installation found under $BF" >&2
    exit 1
fi

args=()
for a in "$@"; do
    # Convert absolute WSL paths (existing, or creatable in an existing dir)
    # to Windows paths; leave flags and everything else untouched.
    if [[ "$a" == /* ]] && { [ -e "$a" ] || [ -d "$(dirname "$a")" ]; }; then
        args+=("$(wslpath -w "$a")")
    else
        args+=("$a")
    fi
done

exec "$BLENDER_EXE" "${args[@]}"
