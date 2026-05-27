#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_USER="${SUDO_USER:-$(id -un)}"
APP_GROUP="$(id -gn "$APP_USER")"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-5000}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
INSTALL_OLLAMA="${INSTALL_OLLAMA:-1}"
INSTALL_OFFLINE_STT="${INSTALL_OFFLINE_STT:-0}"
VOSK_MODEL_DIR="${VOSK_MODEL_DIR:-/home/$APP_USER/models}"

if [[ "$APP_USER" == "root" ]]; then
  echo "Please run this script as the normal Raspberry Pi desktop user, not root." >&2
  exit 1
fi

echo "== TCM Diagnosis System Pi 5 installer =="
echo "App dir:  $APP_DIR"
echo "App user: $APP_USER"
echo "Port:     $PORT"
echo

echo "== Installing system packages =="
sudo apt update
sudo apt install -y \
  curl \
  unzip \
  nginx \
  firefox-esr \
  python3 \
  python3-pip \
  python3-venv \
  x11-xserver-utils \
  fcitx5 \
  fcitx5-chewing \
  squeekboard

echo
echo "== Creating Python virtual environment =="
cd "$APP_DIR"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "== Preparing .env =="
if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

if ! grep -q '^PORT=' "$APP_DIR/.env"; then
  printf '\nPORT=%s\n' "$PORT" >> "$APP_DIR/.env"
fi
if ! grep -q '^OLLAMA_MODEL=' "$APP_DIR/.env"; then
  printf 'OLLAMA_MODEL=%s\n' "$OLLAMA_MODEL" >> "$APP_DIR/.env"
fi
if ! grep -q '^OLLAMA_HOST=' "$APP_DIR/.env"; then
  printf 'OLLAMA_HOST=http://127.0.0.1:11434\n' >> "$APP_DIR/.env"
fi

echo
echo "== Installing systemd service =="
sudo tee /etc/systemd/system/tcm-diagnosis.service >/dev/null <<EOF
[Unit]
Description=TCM Diagnosis System Flask App
After=network.target

[Service]
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/gunicorn --workers 1 --threads 2 --timeout 120 --bind 0.0.0.0:$PORT app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tcm-diagnosis
sudo systemctl restart tcm-diagnosis

echo
echo "== Installing kiosk launcher =="
APP_DIR="$APP_DIR" TCM_APP_URL="http://127.0.0.1:$PORT/" HOME="$APP_HOME" bash "$APP_DIR/deploy/raspberry-pi/install-kiosk.sh"
sudo chown -R "$APP_USER:$APP_GROUP" "$APP_HOME/.config" "$APP_HOME/Desktop" "$APP_HOME/start-tcm-kiosk.sh" 2>/dev/null || true

echo
echo "== Optional Ollama setup =="
if [[ "$INSTALL_OLLAMA" == "1" ]]; then
  if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
  fi
  sudo systemctl enable ollama >/dev/null 2>&1 || true
  sudo systemctl start ollama >/dev/null 2>&1 || true
  ollama pull "$OLLAMA_MODEL"
else
  echo "Skipped Ollama. To install later: INSTALL_OLLAMA=1 bash deploy/raspberry-pi5/install-pi5.sh"
fi

echo
echo "== Optional offline speech-to-text =="
if [[ "$INSTALL_OFFLINE_STT" == "1" ]]; then
  mkdir -p "$VOSK_MODEL_DIR"
  cd "$VOSK_MODEL_DIR"
  if [[ ! -d vosk-model-small-cn-0.22 ]]; then
    curl -L -o vosk-model-small-cn-0.22.zip https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
    unzip -o vosk-model-small-cn-0.22.zip
  fi
  if ! grep -q '^VOSK_MODEL_PATH=' "$APP_DIR/.env"; then
    printf '\nVOSK_MODEL_PATH=%s/vosk-model-small-cn-0.22\nVOSK_PRELOAD=1\n' "$VOSK_MODEL_DIR" >> "$APP_DIR/.env"
  fi
  sudo systemctl restart tcm-diagnosis
else
  echo "Skipped offline STT model. Online Google STT can be enabled by adding GOOGLE_CLOUD_SPEECH_API_KEY to .env."
fi

echo
echo "== Status =="
sudo systemctl --no-pager --full status tcm-diagnosis || true

echo
echo "Done."
echo "Open locally:  http://127.0.0.1:$PORT/"
echo "Open on LAN:   http://$(hostname -I | awk '{print $1}'):$PORT/"
echo "Kiosk shortcut: $APP_HOME/Desktop/tcm-diagnosis-kiosk.desktop"
echo
echo "Important next steps:"
echo "1. Edit $APP_DIR/.env if you need Google Speech API key."
echo "2. Reboot or double-click the kiosk shortcut to start full-screen mode."
