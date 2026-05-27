#!/bin/bash
set -e

APP_DIR="${APP_DIR:-/home/pi/tcm-diagnosis-system}"
cd "$APP_DIR"

mkdir -p data/corrupt_backups
ts="$(date +%Y%m%d_%H%M%S)"

for file in \
  data/tcm_diagnosis.sqlite3 \
  data/tcm_diagnosis.sqlite3-wal \
  data/tcm_diagnosis.sqlite3-shm
do
  if [ -e "$file" ]; then
    mv "$file" "data/corrupt_backups/$(basename "$file").$ts.bak"
  fi
done

sudo systemctl restart tcm-diagnosis
sleep 8
systemctl is-active tcm-diagnosis
ss -ltnp | grep 5000 || true
curl -I --max-time 10 http://127.0.0.1:5000/ | head -n 1
ls -l data/corrupt_backups | tail -n 10
