#!/usr/bin/env bash
# Build the Catalogue Tools extension zip with the capture pipeline VENDORED in
# (single source of truth stays pipeline/blender/capture/ — this stages a copy
# into catalogue_tools/capture/ at build time so the installed extension works
# on any computer with just Blender, no repo and no WSL).
#
# Usage: pipeline/blender/addons/build_addon.sh [output.zip]
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
VERSION=$(grep -oP '^version = "\K[^"]+' "$HERE/catalogue_tools/blender_manifest.toml")
OUT=${1:-/mnt/d/renders/addons/catalogue_tools-$VERSION.zip}
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT

cp -r "$HERE/catalogue_tools" "$BUILD/catalogue_tools"
cp -r "$HERE/../capture" "$BUILD/catalogue_tools/capture"
find "$BUILD" -name __pycache__ -type d -exec rm -rf {} +

mkdir -p "$(dirname "$OUT")"
"$HERE/../blender-win.sh" --factory-startup --command extension build \
    --source-dir "$BUILD/catalogue_tools" --output-filepath "$OUT"
echo "built: $OUT"
