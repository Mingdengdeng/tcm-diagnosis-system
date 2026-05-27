#!/bin/bash
set -e

pkill -u pi -f 'tcm-diagnosis-kiosk-firefox' >/dev/null 2>&1 || true
pkill -u pi -f 'firefox.*127.0.0.1:5000' >/dev/null 2>&1 || true
pkill -u pi -f 'firefox-esr.*127.0.0.1:5000' >/dev/null 2>&1 || true
pkill -u pi -f 'tcm-diagnosis-kiosk-chromium' >/dev/null 2>&1 || true
pkill -u pi -f 'chromium.*127.0.0.1:5000' >/dev/null 2>&1 || true
sleep 1

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

nohup /home/pi/start-tcm-kiosk.sh >/tmp/tcm-kiosk.log 2>&1 &
sleep 3

if pgrep -u pi -a 'firefox|firefox-esr' >/dev/null 2>&1; then
  pgrep -u pi -a 'firefox|firefox-esr' | head -n 3
  echo "Kiosk restarted."
else
  echo "Kiosk did not start. Log:"
  cat /tmp/tcm-kiosk.log
  exit 1
fi
