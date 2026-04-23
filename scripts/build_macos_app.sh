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

# ── Struttura bundle ─────────────────────────────────────────────────────────
echo "--- Crea struttura bundle ---"
rm -rf "$APP_BUNDLE"
mkdir -p \
    "$CONTENTS/MacOS" \
    "$CONTENTS/Frameworks" \
    "$CONTENTS/Resources/pydf-packages" \
    "$CONTENTS/Resources/src"
echo "  OK"
echo ""

# ── Installa Python embedded ─────────────────────────────────────────────────
echo "--- Installa Python embedded ---"
tar xzf "$PBS_TARBALL" -C "$CONTENTS/Frameworks/"
EMBEDDED_PYTHON="$CONTENTS/Frameworks/python/bin/python3"
if [ ! -x "$EMBEDDED_PYTHON" ]; then
    echo "Errore: $EMBEDDED_PYTHON non trovato dopo estrazione."
    echo "Struttura estratta:"
    ls "$CONTENTS/Frameworks/"
    exit 1
fi
PYTHON_VERSION_OUTPUT=$("$EMBEDDED_PYTHON" --version)
echo "  $PYTHON_VERSION_OUTPUT"
echo ""

# ── Installa dipendenze Python ───────────────────────────────────────────────
echo "--- Installa dipendenze Python ---"
PACKAGES_DIR="$CONTENTS/Resources/pydf-packages"
"$EMBEDDED_PYTHON" -m pip install \
    --target "$PACKAGES_DIR" \
    --quiet \
    "pdf2image==1.17.0" \
    "textual>=0.70.0" \
    "pypdf==6.8.0" \
    "pytesseract==0.3.13" \
    "Pillow>=10.3.0,<12.0"
echo "  Dipendenze installate in $PACKAGES_DIR"
echo ""

# ── Copia sorgenti ───────────────────────────────────────────────────────────
echo "--- Copia sorgenti ---"
cp -r "$ROOT_DIR/src/pydf_tool" "$CONTENTS/Resources/src/"
echo "  src/pydf_tool copiato"
echo ""
# ── Launcher ─────────────────────────────────────────────────────────────────
echo "--- Genera launcher ---"
LAUNCHER="$CONTENTS/MacOS/pydf-tool-launcher"

cat > "$LAUNCHER" << 'LAUNCHER_OUTER'
#!/bin/bash
BUNDLE="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_EMBEDDED="$BUNDLE/Frameworks/python/bin/python3"
PYPATH="$BUNDLE/Resources/src:$BUNDLE/Resources/pydf-packages"

TMPSCRIPT=$(mktemp /tmp/pydf-launch-XXXXXXXX) || TMPSCRIPT="/tmp/pydf-launch-fallback-$$.sh"
cat > "$TMPSCRIPT" << PYDF_CMD
#!/bin/bash
export PYTHONPATH="$PYPATH"
printf '\033]0;PyDF Tool\007'
clear
"$PYTHON_EMBEDDED" -m pydf_tool
exit_code=\$?
printf '\nPyDF Tool terminato con stato %s.\n' "\$exit_code"
printf 'La sessione resta aperta in questa finestra.\n'
exec \$SHELL -l
PYDF_CMD
chmod +x "$TMPSCRIPT"

osascript - "$TMPSCRIPT" <<'OSA'
on run argv
    set scriptPath to item 1 of argv
    tell application "Terminal"
        activate
        do script scriptPath
    end tell
end run
OSA
LAUNCHER_OUTER

chmod +x "$LAUNCHER"
echo "  Launcher scritto"
echo ""

# ── Info.plist ───────────────────────────────────────────────────────────────
echo "--- Genera Info.plist ---"
cat > "$CONTENTS/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>it</string>
    <key>CFBundleDisplayName</key>
    <string>PyDF Tool</string>
    <key>CFBundleExecutable</key>
    <string>pydf-tool-launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>dev.flosh.pydf-tool</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>PyDF Tool</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$APP_VERSION</string>
    <key>CFBundleVersion</key>
    <string>$APP_VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF
echo "  Info.plist scritto (versione $APP_VERSION)"
echo ""

# ── Icona ────────────────────────────────────────────────────────────────────
echo "--- Genera AppIcon.icns ---"
ICONSET_DIR="$CACHE_DIR/AppIcon.iconset"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

for size in 16 32 64 128 256 512; do
    sips -z $size $size "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}.png" > /dev/null
    double=$((size * 2))
    sips -z $double $double "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" > /dev/null
done

iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"
echo "  AppIcon.icns generato"
echo ""

# ── DMG ──────────────────────────────────────────────────────────────────────
echo "--- Crea DMG ---"
DMG_NAME="PyDF-Tool-v${APP_VERSION}.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"
DMG_STAGING="$CACHE_DIR/dmg-staging"
rm -f "$DIST_DIR"/PyDF-Tool-v*.dmg
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -r "$APP_BUNDLE" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"
hdiutil create \
    -volname "PyDF Tool" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "$DMG_PATH"
rm -rf "$DMG_STAGING"
rm -rf "$APP_BUNDLE"
echo "  DMG creato: $DMG_PATH"
echo ""

# ── Fine ─────────────────────────────────────────────────────────────────────
echo "=== Build completato ==="
echo "  DMG:    $DMG_PATH"
echo ""
echo "Installa: monta il DMG e trascina PyDF Tool in Applicazioni."
