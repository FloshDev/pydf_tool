#!/bin/bash
# build_macos_app.sh — costruisce PyDF Tool.app standalone con Python embedded.
# Prerequisiti per girare: curl, shasum, sips, iconutil, hdiutil (tutti built-in macOS).
# Uso: bash scripts/build_macos_app.sh
# Env override: PBS_PYTHON_VERSION, PBS_DATE, APP_VERSION

set -euo pipefail

# ── Versioni ────────────────────────────────────────────────────────────────
PBS_PYTHON_VERSION="${PBS_PYTHON_VERSION:-3.12.10}"
PBS_DATE="${PBS_DATE:-20250409}"
APP_VERSION="${APP_VERSION:-1.0.0}"
PBS_ARCH="aarch64-apple-darwin"
PBS_TARBALL_NAME="cpython-${PBS_PYTHON_VERSION}+${PBS_DATE}-${PBS_ARCH}-install_only.tar.gz"
PBS_BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_DATE}"
PBS_URL="${PBS_BASE_URL}/${PBS_TARBALL_NAME}"
PBS_SHA256_URL="${PBS_URL}.sha256"

# ── Path ────────────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_NAME="PyDF Tool"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
CONTENTS="$APP_BUNDLE/Contents"
CACHE_DIR="$ROOT_DIR/.build-cache"
PBS_TARBALL="$CACHE_DIR/$PBS_TARBALL_NAME"

ICON_PNG="$ROOT_DIR/assets/icon/pydf-tool-icon-1024.png"
ICON_ICNS="$CONTENTS/Resources/AppIcon.icns"

echo "=== Build PyDF Tool $APP_VERSION ==="
echo "  Python:  $PBS_PYTHON_VERSION ($PBS_DATE)"
echo "  Bundle:  $APP_BUNDLE"
echo ""

# ── Prerequisiti ────────────────────────────────────────────────────────────
echo "--- Verifica prerequisiti di build ---"
for cmd in curl shasum sips iconutil hdiutil; do
    command -v "$cmd" > /dev/null || { echo "Errore: $cmd non trovato."; exit 1; }
done

if [ ! -f "$ICON_PNG" ]; then
    echo "Errore: icona PNG mancante: $ICON_PNG"
    exit 1
fi
echo "  OK"
echo ""

# ── Download python-build-standalone ────────────────────────────────────────
echo "--- Download python-build-standalone ---"
mkdir -p "$CACHE_DIR"

if [ ! -f "$PBS_TARBALL" ]; then
    echo "  Scarico $PBS_TARBALL_NAME..."
    curl -L --fail --progress-bar -o "$PBS_TARBALL" "$PBS_URL"
else
    echo "  Cache trovata: $PBS_TARBALL"
fi

echo "  Verifica SHA256..."
SHA256_FILE="$CACHE_DIR/${PBS_TARBALL_NAME}.sha256"
curl -L --fail --silent -o "$SHA256_FILE" "$PBS_SHA256_URL"
EXPECTED_SHA="$(awk '{print $1}' "$SHA256_FILE")"
ACTUAL_SHA="$(shasum -a 256 "$PBS_TARBALL" | awk '{print $1}')"
if [ "$EXPECTED_SHA" != "$ACTUAL_SHA" ]; then
    echo "Errore: SHA256 non corrisponde. Cancello la cache e riprova."
    rm -f "$PBS_TARBALL"
    exit 1
fi
echo "  SHA256 OK"
echo ""
