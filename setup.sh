#!/bin/bash
# Setup script per PyDF Tool su Python.org Python 3.12 macOS
# Crea la venv, installa le dipendenze e patcha il wrapper pydf-tool.
# Esegui questo script ogni volta che ricrei la venv da zero,
# o dopo ogni `pip install -e .` manuale.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
SRC_PATH="$SCRIPT_DIR/src"

echo "==> Creazione ambiente virtuale..."
python3 -m venv "$VENV"

echo "==> Installazione dipendenze..."
source "$VENV/bin/activate"
pip install -e .

echo "==> Iniezione PYTHONPATH nello script di attivazione..."
# PYTHONPATH nel file activate sopravvive ai reinstall di pip (pip non tocca activate).
# Questo garantisce che pydf_tool sia trovabile anche se il wrapper viene rigenerato.
ACTIVATE="$VENV/bin/activate"
PYTHONPATH_LINE="export PYTHONPATH=\"$SRC_PATH\${PYTHONPATH:+:\$PYTHONPATH}\""
if ! grep -qF "# PyDF Tool PYTHONPATH" "$ACTIVATE"; then
    printf '\n# PyDF Tool PYTHONPATH workaround UF_HIDDEN\n%s\n' "$PYTHONPATH_LINE" >> "$ACTIVATE"
fi

echo "==> Patch wrapper pydf-tool (workaround UF_HIDDEN, backup)..."
PYTHON_BIN="$VENV/bin/python3.12"
WRAPPER="$VENV/bin/pydf-tool"

python3 - "$PYTHON_BIN" "$SRC_PATH" "$WRAPPER" << 'PYEOF'
import sys, textwrap

python_bin = sys.argv[1]
src_path   = sys.argv[2]
wrapper    = sys.argv[3]

content = textwrap.dedent(f"""\
    #!/bin/sh
    '''exec' "{python_bin}" "$0" "$@"
    ' '''
    # -*- coding: utf-8 -*-
    import re
    import sys
    import os as _os

    # Workaround Python.org Python 3.12 macOS: la cartella .venv riceve il flag
    # UF_HIDDEN; site.py salta tutti i .pth file hidden e pydf_tool risulta
    # invisibile. Questo blocco inietta src/ in sys.path prima dell'import.
    _src = "{src_path}"
    if _os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)

    from pydf_tool.cli import main
    if __name__ == '__main__':
        sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
        sys.exit(main())
    """)

with open(wrapper, "w") as f:
    f.write(content)

import os, stat
os.chmod(wrapper, os.stat(wrapper).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print(f"Wrapper patchato: {wrapper}")
PYEOF

echo ""
echo "Setup completato."
echo ""
echo "Per usare il tool:"
echo "  source .venv/bin/activate"
echo "  pydf-tool"
echo ""
echo "Dopo modifiche al codice in src/: esci dalla TUI e rilancia pydf-tool."
echo "Dopo pip install -e . manuale:    riesegui bash setup.sh"
