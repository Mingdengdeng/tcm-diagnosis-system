# Raspberry Pi 4 Deployment

This guide moves the TCM Diagnosis System to a Raspberry Pi 4 on a local network.

Pi 4 note: run the Flask/rule-engine app first. Ollama with `qwen2.5:1.5b` may be slow on Pi 4, especially on 2GB/4GB models. The app still works without Ollama because it falls back to deterministic rule-based output.

## 1. Prepare Raspberry Pi OS

Use Raspberry Pi OS 64-bit if possible.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx unzip
```

## 2. Copy Project To The Pi

From your Windows machine, copy the prepared upload folder or zip to the Pi.

Recommended target path:

```bash
/home/pi/tcm-diagnosis-system
```

If using the zip:

```bash
mkdir -p /home/pi/tcm-diagnosis-system
unzip tcm-diagnosis-system-upload.zip -d /home/pi/tcm-diagnosis-system
cd /home/pi/tcm-diagnosis-system
```

## 3. Create Python Environment

```bash
cd /home/pi/tcm-diagnosis-system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure Environment

```bash
cp deploy/raspberry-pi/.env.example .env
nano .env
```

For Pi 4, keep:

```bash
FLASK_DEBUG=0
PORT=5000
TCM_ADMIN_PIN=change_this_pin
OLLAMA_MODEL=qwen2.5:1.5b
```

If Ollama is not installed, leave the values as-is. The app will use rule-based fallback when Ollama is unavailable.

## 5.1 Voice-To-Text

The app supports two voice modes:

- Online: Google Cloud Speech-to-Text standard model, `zh-TW`, with TCM symptom phrase hints.
- Offline: Vosk fallback on the Pi.

For online voice recognition, add this to `/home/pi/tcm-diagnosis-system/.env`:

```bash
GOOGLE_CLOUD_SPEECH_API_KEY=your_google_cloud_speech_api_key
GOOGLE_CLOUD_SPEECH_MODEL=
GOOGLE_CLOUD_SPEECH_TIMEOUT=18
```

This uses the regular Google Speech-to-Text model, not the medical model. Leave `GOOGLE_CLOUD_SPEECH_MODEL` empty for `zh-TW` unless you have tested a specific supported model. Restart the app after changing `.env`:

```bash
sudo systemctl restart tcm-diagnosis
```

### Optional: Offline Voice-To-Text

The browser can record audio only on `https://...` or `localhost`. To convert Mandarin speech to text offline on the Pi, install Vosk and a small Chinese model:

```bash
cd /home/pi/tcm-diagnosis-system
source .venv/bin/activate
pip install vosk==0.3.45
mkdir -p /home/pi/models
cd /home/pi/models
wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
unzip vosk-model-small-cn-0.22.zip
```

Then add this to `/home/pi/tcm-diagnosis-system/.env`:

```bash
VOSK_MODEL_PATH=/home/pi/models/vosk-model-small-cn-0.22
VOSK_PRELOAD=1
```

Restart the app:

```bash
sudo systemctl restart tcm-diagnosis
```

## 5. Test Manually

```bash
source .venv/bin/activate
python app.py
```

Open from another device on the same Wi-Fi:

```text
http://RASPBERRY_PI_IP:5000/
```

Find the Pi IP:

```bash
hostname -I
```

Stop manual run with `Ctrl+C`.

## 6. Install Systemd Service

```bash
sudo cp deploy/raspberry-pi/tcm-diagnosis.service /etc/systemd/system/tcm-diagnosis.service
sudo systemctl daemon-reload
sudo systemctl enable tcm-diagnosis
sudo systemctl start tcm-diagnosis
sudo systemctl status tcm-diagnosis
```

View logs:

```bash
journalctl -u tcm-diagnosis -f
```

## 7. Add Nginx Reverse Proxy

```bash
sudo cp deploy/raspberry-pi/nginx-tcm-diagnosis.conf /etc/nginx/sites-available/tcm-diagnosis
sudo ln -s /etc/nginx/sites-available/tcm-diagnosis /etc/nginx/sites-enabled/tcm-diagnosis
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Open:

```text
http://RASPBERRY_PI_IP/
```

## 8. Kiosk Mode For A Product-Like Device

Kiosk mode makes the Pi open the diagnosis system full-screen from a desktop shortcut or automatically after login.

Install Chromium if it is not already installed:

```bash
sudo apt install -y chromium-browser
```

Install the kiosk launcher:

```bash
cd /home/pi/tcm-diagnosis-system
chmod +x deploy/raspberry-pi/install-kiosk.sh
deploy/raspberry-pi/install-kiosk.sh
```

This creates:

- `/home/pi/start-tcm-kiosk.sh`
- `/home/pi/Desktop/tcm-diagnosis-kiosk.desktop`
- `/home/pi/.config/autostart/tcm-diagnosis-kiosk.desktop`

To start kiosk manually, double-click the desktop shortcut named `中醫診斷系統`.

To open the hidden maintenance panel inside the app:

1. Tap/click the top-left hidden corner 6 times quickly.
2. Enter the admin PIN from `.env`.
3. Use the panel to refresh the app, check database status, enter/leave browser fullscreen, or exit kiosk.

To change the kiosk URL, edit:

```bash
nano /home/pi/.config/tcm-diagnosis-kiosk.env
```

Example:

```bash
TCM_APP_URL=http://127.0.0.1:5000/
```

## 9. Optional: Install Ollama

Only do this after the app works without AI.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:1.5b
```

Then restart the app:

```bash
sudo systemctl restart tcm-diagnosis
```

If responses are too slow on Pi 4, keep Ollama off and rely on the rule engine until you move AI inference to a stronger server.

## 10. Local Network Usage

For clinic/kiosk usage:

- Keep the Pi and tablets on the same Wi-Fi.
- Use the Pi IP address in the browser.
- Do not expose the Pi directly to the public internet without HTTPS, firewall, and privacy review.

## 11. Common Commands

Restart app:

```bash
sudo systemctl restart tcm-diagnosis
```

Check app:

```bash
systemctl status tcm-diagnosis
```

Check Nginx:

```bash
sudo nginx -t
sudo systemctl status nginx
```
