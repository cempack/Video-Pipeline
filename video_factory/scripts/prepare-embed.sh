#!/usr/bin/env bash
# Bundle Python engine into Go binary embed FS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/internal/bootstrap/embedded/engine"
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$ROOT/pyproject.toml" "$DEST/"
cp "$ROOT/requirements.txt" "$DEST/"
cp "$ROOT/README.md" "$DEST/" 2>/dev/null || echo "# video-factory" > "$DEST/README.md"
cp -r "$ROOT/src" "$DEST/"
touch "$DEST/.gitkeep"
echo "Prepared embed: $DEST"
