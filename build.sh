#!/usr/bin/env bash
# Build the standalone text-editor-bin executable with PyInstaller.
#
# Usage:
#   ./build.sh
#
# The resulting one-file binary is written to bin/ next to this script.

set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname -- "$APP_DIR")"
PYTHON="$ROOT_DIR/venv/bin/python"
BUILD_DIR="$APP_DIR/build/pyinstaller"
ENTRY_POINT="$APP_DIR/src/text_editor_tui/__main__.py"
OUTPUT_DIR="$APP_DIR/bin"
OUTPUT="$OUTPUT_DIR/text-editor-bin"

if [ ! -x "$PYTHON" ]; then
    echo "Error: Python not found at $PYTHON" >&2
    exit 1
fi
if [ ! -f "$ENTRY_POINT" ]; then
    echo "Error: entry point not found at $ENTRY_POINT" >&2
    exit 1
fi
if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "Error: PyInstaller is not installed in $ROOT_DIR/venv" >&2
    echo "Install it with: $PYTHON -m pip install pyinstaller" >&2
    exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

cd "$APP_DIR"

"$PYTHON" -m PyInstaller \
    --onefile \
    --noconfirm \
    --clean \
    --name text-editor-bin \
    --distpath "$OUTPUT_DIR" \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    --paths "$APP_DIR/src" \
    --collect-all textual \
    --collect-all rich \
    --collect-all pygments \
    --collect-all text_editor_tui \
    --copy-metadata textual \
    --copy-metadata rich \
    --copy-metadata pygments \
    --copy-metadata text_editor_tui \
    "$ENTRY_POINT"

chmod 755 "$OUTPUT"

echo
echo "Built: $OUTPUT"
ls -lh "$OUTPUT"
sha256sum "$OUTPUT"
