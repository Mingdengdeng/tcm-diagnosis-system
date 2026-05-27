#!/bin/bash
set -e

APP_URL="${1:-http://127.0.0.1:5000/}"
PI_USER_HOME="/home/pi"
KIOSK_SCRIPT="$PI_USER_HOME/start-tcm-kiosk.sh"
AUTOSTART_DIR="$PI_USER_HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/tcm-kiosk.desktop"

cat > "$KIOSK_SCRIPT" <<EOF
#!/bin/bash
export DISPLAY=:0
xset s off || true
xset -dpms || true
xset s noblank || true

while ! curl -fsS "$APP_URL" >/dev/null 2>&1; do
  sleep 1
done

if command -v chromium-browser >/dev/null 2>&1; then
  BROWSER=chromium-browser
elif command -v chromium >/dev/null 2>&1; then
  BROWSER=chromium
else
  BROWSER=chromium-browser
fi

exec "\$BROWSER" \\
  --kiosk \\
  --noerrdialogs \\
  --disable-infobars \\
  --disable-session-crashed-bubble \\
  --disable-features=TranslateUI \\
  --autoplay-policy=no-user-gesture-required \\
  "$APP_URL"
EOF

chmod +x "$KIOSK_SCRIPT"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=TCM Diagnosis Kiosk
Comment=Open TCM Diagnosis System in kiosk mode
Exec=$KIOSK_SCRIPT
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod 644 "$AUTOSTART_FILE"

if systemctl list-unit-files | grep -q '^tcm-diagnosis.service'; then
  sudo systemctl enable tcm-diagnosis >/dev/null 2>&1 || true
  sudo systemctl restart tcm-diagnosis || true
fi

echo "Kiosk setup complete."
echo "Autostart file: $AUTOSTART_FILE"
echo "Kiosk script:   $KIOSK_SCRIPT"
echo "App URL:        $APP_URL"
