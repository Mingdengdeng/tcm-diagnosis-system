@echo off
setlocal

cd /d "%~dp0"

echo.
echo Deploying TCM Diagnosis System to Raspberry Pi 4...
echo Target: pi@raspberrypi4.local
echo.
echo If asked for password, enter the current password for the Pi user.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\deploy\raspberry-pi\deploy-from-windows.ps1"

echo.
echo Finished. If deploy succeeded, open:
echo   http://raspberrypi4.local:5000/
echo.
pause
