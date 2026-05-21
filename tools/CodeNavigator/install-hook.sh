#!/usr/bin/env bash
# Register CodeNavigator pre-commit hook for this git repo.
# Usage: bash install-hook.sh [repo-root]
REPO="${1:-.}"
HOOKS_DIR="$(git -C "$REPO" rev-parse --git-dir)/hooks"
SRC="$(dirname "$0")/.githooks/pre-commit"
DST="$HOOKS_DIR/pre-commit"

if [ -f "$DST" ]; then
    echo "Existing hook at $DST — skipping. Manual merge required."
    exit 1
fi
cp "$SRC" "$DST"
chmod +x "$DST"
echo "Hook installed: $DST"
