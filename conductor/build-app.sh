#!/bin/bash
# Builds /Applications/Conductor.app: a tiny shim that hands Conductor.command to Terminal
# (same pattern as Surface Console: a new app bundle has no access to the external drive,
# Terminal already does, and passing a path is not a file access).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${1:-/Applications/Conductor.app}"
WORK="$(mktemp -d)"

# icon: svg -> 1024 png -> iconset -> icns
qlmanage -t -s 1024 -o "$WORK" "$HERE/icon.svg" >/dev/null 2>&1
PNG="$WORK/icon.svg.png"
[ -f "$PNG" ] || { echo "icon render failed"; exit 1; }
SET="$WORK/icon.iconset"; mkdir -p "$SET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$PNG" --out "$SET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); sips -z $d $d "$PNG" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$WORK/icon.icns"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$WORK/icon.icns" "$APP/Contents/Resources/icon.icns"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleDisplayName</key><string>Conductor</string>
  <key>CFBundleName</key><string>Conductor</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundleIdentifier</key><string>com.uxieee.conductor</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/launch" <<LAUNCH
#!/bin/bash
# Hands Conductor.command to Terminal via LaunchServices (plain open, never open -a Terminal:
# the -a form races Terminal's cold launch and drops the document).
CMD="$HERE/Conductor.command"
if ! open "\$CMD" 2>/dev/null; then
  osascript -e 'display dialog "Conductor could not start. Open Conductor/app/Conductor.command directly." with title "Conductor" buttons {"OK"} default button "OK"'
fi
LAUNCH
chmod +x "$APP/Contents/MacOS/launch" "$HERE/Conductor.command"
touch "$APP"
rm -rf "$WORK"
echo "built $APP"
