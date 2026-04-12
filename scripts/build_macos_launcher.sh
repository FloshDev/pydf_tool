#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="PyDF Tool"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
ICON_PNG="$ROOT_DIR/assets/icon/pydf-tool-icon-1024.png"
ICON_ICNS="$ROOT_DIR/assets/icon/pydf-tool.icns"
LAUNCHER_BIN="$APP_BUNDLE/Contents/MacOS/pydf-tool-launcher"
INFO_PLIST="$APP_BUNDLE/Contents/Info.plist"
RESOURCES_DIR="$APP_BUNDLE/Contents/Resources"

if [ ! -f "$ICON_PNG" ]; then
    echo "Icona PNG mancante: $ICON_PNG" >&2
    echo "Copia prima il master definitivo in assets/icon/pydf-tool-icon-1024.png" >&2
    exit 1
fi

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
    echo "La venv non e disponibile. Esegui prima: bash setup.sh" >&2
    exit 1
fi

rm -rf "$APP_BUNDLE"
mkdir -p "$DIST_DIR" "$APP_BUNDLE/Contents/MacOS" "$RESOURCES_DIR"

"$ROOT_DIR/.venv/bin/python" - <<PY
from PIL import Image

icon_png = r"""$ICON_PNG"""
icon_icns = r"""$ICON_ICNS"""

img = Image.open(icon_png)
img.save(icon_icns)
print(f"Icona .icns generata in: {icon_icns}")
PY

cp "$ICON_ICNS" "$RESOURCES_DIR/AppIcon.icns"

cat > "$LAUNCHER_BIN" <<EOF
#!/bin/bash

set -euo pipefail

REPO_ROOT="$ROOT_DIR"

TERMINAL_COMMAND=\$(cat <<'CMD'
cd "$ROOT_DIR"
printf '\\033]0;PyDF Tool\\007'
if [ ! -x ".venv/bin/python" ]; then
    printf '\\nPyDF Tool beta locale\\n\\n'
    printf 'Ambiente virtuale mancante in: %s/.venv\\n' "$ROOT_DIR"
    printf 'Esegui prima: cd "%s" && bash setup.sh\\n\\n' "$ROOT_DIR"
    exec \$SHELL -l
fi

source ".venv/bin/activate"
clear
printf 'PyDF Tool beta locale\\n'
printf 'Repo: %s\\n\\n' "$ROOT_DIR"
".venv/bin/pydf-tool"
exit_code=\$?
printf '\\nPyDF Tool terminato con stato %s\\n' "\$exit_code"
printf 'La sessione resta aperta in questa finestra.\\n'
exec \$SHELL -l
CMD
)

osascript - "\$TERMINAL_COMMAND" <<'OSA'
on run argv
    set shellCommand to item 1 of argv
    tell application "Terminal"
        activate
        do script shellCommand
    end tell
end run
OSA
EOF

chmod +x "$LAUNCHER_BIN"

cat > "$INFO_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>it</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>
    <string>pydf-tool-launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>local.pydf-tool.beta</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0-beta-local</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "Launcher creato in: $APP_BUNDLE"
