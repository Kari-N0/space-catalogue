#!/usr/bin/env bash
# sync-nas.sh — back up the by-design-untracked heavy data to the Synology NAS.
#
# Target: X:\projects\farsidelab on the Synology (\\192.168.50.130\Kari),
# reached from WSL at /mnt/x (drvfs mount; /etc/fstab makes it boot-persistent).
# Legs:
#   assets_src/               -> <NAS>/assets_src/    (.blend sources, textures)
#   pipeline/rehearsal/web/   -> <NAS>/splats/rehearsal/
#   /mnt/d/renders/           -> <NAS>/renders/       (Windows staging: datasets, renders)
#
# Accumulative by design: no --delete, so a local mistake can never propagate
# into the backup. Excess files on the NAS are pruned manually if ever needed.
# rsync -rlt (not -a): SMB/drvfs can't take perms/owner, and FAT-style mtime
# granularity needs --modify-window.
#
# Usage: sync-nas.sh [--dry-run]
# Log:   ~/.local/state/sync-nas/sync-<stamp>.log (last.log -> most recent)
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAS_ROOT="${NAS_ROOT:-/mnt/x/projects/farsidelab}"
LOG_DIR="$HOME/.local/state/sync-nas"
STAMP="$(date +%Y%m%d-%H%M%S)"
MODE="real"
DRY=()
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=(--dry-run); MODE="dry-run" ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done
LOG="$LOG_DIR/sync-$STAMP-$MODE.log"
mkdir -p "$LOG_DIR"

if ! mountpoint -q /mnt/x; then
  echo "ERROR: /mnt/x is not mounted. Run:" | tee -a "$LOG"
  echo "  sudo mount -t drvfs X: /mnt/x   # or: sudo mount -t drvfs '\\\\192.168.50.130\\Kari' /mnt/x" | tee -a "$LOG"
  exit 1
fi
mkdir -p "$NAS_ROOT/assets_src" "$NAS_ROOT/splats/rehearsal" "$NAS_ROOT/renders"

OPTS=(-rlt --modify-window=2 --human-readable --info=stats2
      --exclude='*.blend1' --exclude='*Zone.Identifier' --exclude='Thumbs.db'
      --exclude='desktop.ini' --exclude='__pycache__/')

run_leg() { # name src dst
  local name="$1" src="$2" dst="$3"
  echo "== leg: $name ($MODE) ==" | tee -a "$LOG"
  rsync "${OPTS[@]}" "${DRY[@]}" "$src" "$dst" 2>&1 | tee -a "$LOG" | grep -E \
    'Number of created files|Number of regular files transferred|Total transferred file size|^total size' || true
  local rc=${PIPESTATUS[0]}
  [ "$rc" -ne 0 ] && [ "$rc" -ne 24 ] && { echo "LEG FAILED ($name): rsync rc=$rc" | tee -a "$LOG"; return "$rc"; }
  return 0
}

START=$(date +%s)
echo "sync-nas $MODE started $(date -Is) -> $NAS_ROOT" | tee -a "$LOG"
FAIL=0
run_leg assets_src "$REPO/assets_src/"            "$NAS_ROOT/assets_src/"      || FAIL=1
run_leg splats     "$REPO/pipeline/rehearsal/web/" "$NAS_ROOT/splats/rehearsal/" || FAIL=1
run_leg renders    /mnt/d/renders/                 "$NAS_ROOT/renders/"          || FAIL=1
DUR=$(( $(date +%s) - START ))
echo "sync-nas $MODE finished $(date -Is), duration ${DUR}s, status $([ $FAIL -eq 0 ] && echo OK || echo FAILED)" | tee -a "$LOG"
ln -sfn "$LOG" "$LOG_DIR/last.log"
exit $FAIL
