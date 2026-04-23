#!/bin/bash
# Verifica la correttezza strutturale del bundle dopo build_macos_app.sh.
# Uso: bash scripts/smoke_test_bundle.sh [path/a/PyDF Tool.app]

set -euo pipefail

BUNDLE="${1:-dist/PyDF Tool.app}"
CONTENTS="$BUNDLE/Contents"
PYTHON="$CONTENTS/Frameworks/python/bin/python3"
PACKAGES="$CONTENTS/Resources/pydf-packages"
SRC="$CONTENTS/Resources/src"

PASS=0
FAIL=0

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "ok" ]; then
        echo "  ✓ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $desc — $result"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Smoke test: $BUNDLE ==="
echo ""
echo "--- Struttura bundle ---"

[ -d "$CONTENTS/MacOS" ]          && check "MacOS/ esiste"          "ok" || check "MacOS/ esiste"          "mancante"
[ -f "$CONTENTS/MacOS/pydf-tool-launcher" ] && check "launcher esiste" "ok" || check "launcher esiste" "mancante"
[ -x "$CONTENTS/MacOS/pydf-tool-launcher" ] && check "launcher eseguibile" "ok" || check "launcher eseguibile" "non eseguibile"
[ -d "$CONTENTS/Frameworks/python" ] && check "Frameworks/python/ esiste" "ok" || check "Frameworks/python/ esiste" "mancante"
[ -f "$PYTHON" ]                   && check "python3 esiste"         "ok" || check "python3 esiste"         "mancante"
[ -x "$PYTHON" ]                   && check "python3 eseguibile"     "ok" || check "python3 eseguibile"     "non eseguibile"
[ -d "$PACKAGES" ]                 && check "pydf-packages/ esiste"  "ok" || check "pydf-packages/ esiste"  "mancante"
[ -d "$SRC/pydf_tool" ]            && check "src/pydf_tool/ esiste"  "ok" || check "src/pydf_tool/ esiste"  "mancante"
[ -f "$CONTENTS/Info.plist" ]      && check "Info.plist esiste"      "ok" || check "Info.plist esiste"      "mancante"
[ -f "$CONTENTS/Resources/AppIcon.icns" ] && check "AppIcon.icns esiste" "ok" || check "AppIcon.icns esiste" "mancante"

echo ""
echo "--- Python embedded ---"

PY_VER=$("$PYTHON" --version 2>&1) && check "python3 --version: $PY_VER" "ok" || check "python3 --version" "fallito"

echo ""
echo "--- Import dipendenze ---"

PYPATH="$SRC:$PACKAGES"
import_check() {
    local mod="$1"
    PYTHONPATH="$PYPATH" "$PYTHON" -c "import $mod" 2>/dev/null \
        && check "import $mod" "ok" \
        || check "import $mod" "fallito"
}

import_check textual
import_check pdf2image
import_check pytesseract
import_check PIL
import_check pypdf
import_check pydf_tool

echo ""
echo "--- Entry point ---"

PYTHONPATH="$PYPATH" "$PYTHON" -m pydf_tool --help > /dev/null 2>&1 \
    && check "python -m pydf_tool --help" "ok" \
    || check "python -m pydf_tool --help" "fallito"

echo ""
echo "=== Risultato: $PASS passati, $FAIL falliti ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
