#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/pi/tcm-diagnosis-system}"
KIOSK_URL="${TCM_APP_URL:-http://127.0.0.1:5000/}"
HOME_DIR="${HOME:-/home/pi}"
CONFIG_DIR="$HOME_DIR/.config"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
DESKTOP_DIR="$HOME_DIR/Desktop"
LAUNCHER="$HOME_DIR/start-tcm-kiosk.sh"

if [[ ! -d "$APP_DIR" ]]; then
  echo "App directory not found: $APP_DIR" >&2
  exit 1
fi

mkdir -p "$CONFIG_DIR" "$AUTOSTART_DIR" "$DESKTOP_DIR"

cat > "$CONFIG_DIR/tcm-diagnosis-kiosk.env" <<EOF
TCM_APP_URL=$KIOSK_URL
EOF

cp "$APP_DIR/deploy/raspberry-pi/start-tcm-kiosk.sh" "$LAUNCHER"
chmod +x "$LAUNCHER"

cp "$APP_DIR/deploy/raspberry-pi/tcm-diagnosis-kiosk.desktop" "$DESKTOP_DIR/tcm-diagnosis-kiosk.desktop"
cp "$APP_DIR/deploy/raspberry-pi/tcm-diagnosis-kiosk-autostart.desktop" "$AUTOSTART_DIR/tcm-diagnosis-kiosk.desktop"
chmod +x "$DESKTOP_DIR/tcm-diagnosis-kiosk.desktop" "$AUTOSTART_DIR/tcm-diagnosis-kiosk.desktop"

if command -v gio >/dev/null 2>&1; then
  gio set "$DESKTOP_DIR/tcm-diagnosis-kiosk.desktop" metadata::trusted true >/dev/null 2>&1 || true
fi

echo "Kiosk installed."
echo "Desktop shortcut: $DESKTOP_DIR/tcm-diagnosis-kiosk.desktop"
echo "Autostart entry:   $AUTOSTART_DIR/tcm-diagnosis-kiosk.desktop"
echo "Kiosk URL:         $KIOSK_URL"
echo "Restart the Pi desktop session, or double-click the desktop shortcut to start kiosk mode."
