#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${TCM_KIOSK_CONFIG:-$HOME/.config/tcm-diagnosis-kiosk.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  set +a
fi

APP_URL="${TCM_APP_URL:-http://127.0.0.1:5000/}"
BROWSER="${TCM_KIOSK_BROWSER:-}"
PROFILE_DIR="${TCM_KIOSK_PROFILE:-$HOME/.cache/tcm-diagnosis-kiosk-firefox}"
WINDOW_WIDTH="${TCM_KIOSK_WIDTH:-1280}"
WINDOW_HEIGHT="${TCM_KIOSK_HEIGHT:-800}"
KIOSK_MODE="${TCM_KIOSK_MODE:-1}"

if [[ -z "$BROWSER" ]]; then
  BROWSER="$(command -v firefox-esr || command -v firefox || true)"
fi

if [[ -z "$BROWSER" ]]; then
  echo "Firefox ESR is not installed or not found in PATH." >&2
  exit 1
fi

for _ in $(seq 1 45); do
  if curl -fsS "$APP_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

xset s off >/dev/null 2>&1 || true
xset -dpms >/dev/null 2>&1 || true
xset s noblank >/dev/null 2>&1 || true

# Keep physical keyboards in English/US by default. The app has its own
# touch keyboard and voice input for Traditional Chinese text.
export GTK_IM_MODULE=xim
export QT_IM_MODULE=xim
export XMODIFIERS=@im=none
export MOZ_ENABLE_WAYLAND=1

mkdir -p "$HOME/.config/fcitx5"
cat > "$HOME/.config/fcitx5/profile" <<'EOF'
[Groups/0]
Name="Traditional Chinese"
Default Layout=us
DefaultIM=keyboard-us

[Groups/0/Items/0]
Name=keyboard-us
Layout=

[Groups/0/Items/1]
Name=chewing
Layout=

[GroupOrder]
0="Traditional Chinese"
EOF

if command -v fcitx5 >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x fcitx5 >/dev/null 2>&1; then
  fcitx5 -d >/tmp/tcm-fcitx5.log 2>&1 || true
elif command -v fcitx5-remote >/dev/null 2>&1; then
  fcitx5-remote -r >/dev/null 2>&1 || true
fi

if command -v fcitx5-remote >/dev/null 2>&1; then
  fcitx5-remote -s keyboard-us >/dev/null 2>&1 || true
fi

if command -v squeekboard >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x squeekboard >/dev/null 2>&1; then
  squeekboard >/tmp/tcm-squeekboard.log 2>&1 &
fi

mkdir -p "$PROFILE_DIR"
cat > "$PROFILE_DIR/user.js" <<'EOF'
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("dom.webnotifications.enabled", false);
user_pref("media.navigator.permission.disabled", true);
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
EOF

mkdir -p "$PROFILE_DIR/chrome"
cat > "$PROFILE_DIR/chrome/userChrome.css" <<'EOF'
#TabsToolbar,
#nav-bar,
#PersonalToolbar,
#titlebar {
  visibility: collapse !important;
}

#browser,
#appcontent,
#tabbrowser-tabbox {
  margin: 0 !important;
  padding: 0 !important;
}
EOF

if [[ "$KIOSK_MODE" == "1" ]]; then
  exec "$BROWSER" \
    --no-remote \
    --profile "$PROFILE_DIR" \
    --kiosk "$APP_URL" \
    --width "$WINDOW_WIDTH" \
    --height "$WINDOW_HEIGHT"
fi

exec "$BROWSER" \
  --no-remote \
  --profile "$PROFILE_DIR" \
  --new-window "$APP_URL" \
  --width "$WINDOW_WIDTH" \
  --height "$WINDOW_HEIGHT"
