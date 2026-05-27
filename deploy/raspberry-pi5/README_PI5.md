# Raspberry Pi 5 Installation

This guide installs the TCM Diagnosis System on a Raspberry Pi 5 so it can run like a kiosk device.

## What This Installer Does

`install-pi5.sh` installs:

- Python virtual environment and `requirements.txt`
- Flask/Gunicorn systemd service
- Firefox ESR kiosk launcher and desktop shortcut
- Nginx package for later reverse proxy use
- Optional Ollama and `qwen2.5:1.5b`
- Optional Vosk offline speech-to-text model

It does not include private secrets. You must create or edit `.env` on the Pi 5.

## Recommended Hardware

- Raspberry Pi 5
- 64-bit Raspberry Pi OS / Debian Bookworm
- NVMe SSD or good SSD storage recommended
- USB microphone or reliable camera/mic module
- Touchscreen display

## Install From GitHub

On the Pi 5:

```bash
sudo apt update
sudo apt install -y git
cd /home/pi
git clone https://github.com/Mingdengdeng/tcm-diagnosis-system.git
cd tcm-diagnosis-system
chmod +x deploy/raspberry-pi5/install-pi5.sh
bash deploy/raspberry-pi5/install-pi5.sh
```

If your Pi username is not `pi`, use your own home directory:

```bash
cd ~
git clone https://github.com/Mingdengdeng/tcm-diagnosis-system.git
cd tcm-diagnosis-system
chmod +x deploy/raspberry-pi5/install-pi5.sh
bash deploy/raspberry-pi5/install-pi5.sh
```

## Install Without Ollama

If you only want to test the UI/rule engine first:

```bash
INSTALL_OLLAMA=0 bash deploy/raspberry-pi5/install-pi5.sh
```

The app will still run with deterministic fallback output when Ollama is unavailable.

## Install Offline Speech-To-Text

The default voice mode is online Google Speech-to-Text when a key is configured.

To also download the Vosk offline Mandarin fallback model:

```bash
INSTALL_OFFLINE_STT=1 bash deploy/raspberry-pi5/install-pi5.sh
```

This downloads a model to:

```text
/home/<user>/models/vosk-model-small-cn-0.22
```

## Configure `.env`

After install:

```bash
nano .env
```

Recommended values:

```env
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_HOST=http://127.0.0.1:11434
PORT=5000
GOOGLE_CLOUD_SPEECH_API_KEY=
GOOGLE_CLOUD_SPEECH_TIMEOUT=18
```

Do not upload `.env` to GitHub.

Restart after changing `.env`:

```bash
sudo systemctl restart tcm-diagnosis
```

## Open The App

Local:

```text
http://127.0.0.1:5000/
```

From another device on the same network:

```bash
hostname -I
```

Then open:

```text
http://PI_IP:5000/
```

## Kiosk Mode

The installer creates:

```text
/home/<user>/start-tcm-kiosk.sh
/home/<user>/Desktop/tcm-diagnosis-kiosk.desktop
/home/<user>/.config/autostart/tcm-diagnosis-kiosk.desktop
```

Double-click the desktop shortcut named `中醫診斷系統`.

The app has a hidden maintenance panel:

1. Tap the top-left corner 6 times quickly.
2. Use the panel to refresh the app, check status, or exit kiosk.

## Useful Commands

Check service:

```bash
sudo systemctl status tcm-diagnosis
```

View logs:

```bash
journalctl -u tcm-diagnosis -f
```

Restart app:

```bash
sudo systemctl restart tcm-diagnosis
```

Update later:

```bash
cd ~/tcm-diagnosis-system
git pull
bash deploy/raspberry-pi5/install-pi5.sh
```

## Camera/ROI Integration

Your friend's Pi 5 camera module can later send ROI data to the app through the existing face observation API:

```text
POST /api/face-observation
POST /api/session/face
```

The ROI data should be used as routing hints for follow-up questions, not as a direct disease diagnosis.
