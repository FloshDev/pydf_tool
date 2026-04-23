#!/bin/bash
# Verifica la correttezza strutturale del bundle dopo build_macos_app.sh.
# Uso: bash scripts/smoke_test_bundle.sh [path/a/PyDF Tool.app]

set -euo pipefail

BUNDLE="${1:-dist/PyDF Tool.app}"
CONTENTS="$BUNDLE/Contents"
PYTHON="$CONTENTS/Frameworks/python/bin/python3"
PACKAGES="$CONTENTS/Resources/pydf-packages"
SRC="$CONTENTS/Resources/src"

if [ ! -d "$BUNDLE" ]; then
    echo "ERRORE: bundle non trovato: $BUNDLE" >&2
    exit 1
fi

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

if [ -d "$CONTENTS/MacOS" ]; then
    check "MacOS/ esiste" "ok"
else
    check "MacOS/ esiste" "mancante"
fi

if [ -f "$CONTENTS/MacOS/pydf-tool-launcher" ]; then
    check "launcher esiste" "ok"
else
    check "launcher esiste" "mancante"
fi

if [ -x "$CONTENTS/MacOS/pydf-tool-launcher" ]; then
    check "launcher eseguibile" "ok"
else
    check "launcher eseguibile" "non eseguibile"
fi

if [ -d "$CONTENTS/Frameworks/python" ]; then
    check "Frameworks/python/ esiste" "ok"
else
    check "Frameworks/python/ esiste" "mancante"
fi

if [ -f "$PYTHON" ]; then
    check "python3 esiste" "ok"
else
    check "python3 esiste" "mancante"
fi

if [ -x "$PYTHON" ]; then
    check "python3 eseguibile" "ok"
else
    check "python3 eseguibile" "non eseguibile"
fi

if [ -d "$PACKAGES" ]; then
    check "pydf-packages/ esiste" "ok"
else
    check "pydf-packages/ esiste" "mancante"
fi

if [ -d "$SRC/pydf_tool" ]; then
    check "src/pydf_tool/ esiste" "ok"
else
    check "src/pydf_tool/ esiste" "mancante"
fi

if [ -f "$CONTENTS/Info.plist" ]; then
    check "Info.plist esiste" "ok"
else
    check "Info.plist esiste" "mancante"
fi

if [ -f "$CONTENTS/Resources/AppIcon.icns" ]; then
    check "AppIcon.icns esiste" "ok"
else
    check "AppIcon.icns esiste" "mancante"
fi

echo ""
echo "--- Python embedded ---"

if PY_VER=$("$PYTHON" --version 2>&1); then
    check "python3 --version: $PY_VER" "ok"
else
    check "python3 --version" "fallito"
fi

echo ""
echo "--- Import dipendenze ---"

PYPATH="$SRC:$PACKAGES"
import_check() {
    local mod="$1"
    if PYTHONPATH="$PYPATH" "$PYTHON" -c "import $mod" 2>/dev/null; then
        check "import $mod" "ok"
    else
        check "import $mod" "fallito"
    fi
}

import_check textual
import_check pdf2image
import_check pytesseract
import_check PIL
import_check pypdf
import_check rich
import_check pydf_tool

echo ""
echo "--- Entry point ---"

if PYTHONPATH="$PYPATH" "$PYTHON" -m pydf_tool --help > /dev/null 2>&1; then
    check "python -m pydf_tool --help" "ok"
else
    check "python -m pydf_tool --help" "fallito"
fi

echo ""
echo "=== Risultato: $PASS passati, $FAIL falliti ==="
if [ "$FAIL" -eq 0 ]; then
    exit 0
else
    exit 1
fi
