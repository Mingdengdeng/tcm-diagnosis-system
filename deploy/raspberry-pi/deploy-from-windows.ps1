param(
    [string]$PiHost = "raspberrypi4.local",
    [string]$PiUser = "pi",
    [string]$RemoteDir = "/home/pi/tcm-diagnosis-system"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$ArchiveName = "tcm-diagnosis-runtime-update.tgz"
$ArchivePath = Join-Path $ProjectRoot $ArchiveName
$RemoteTarget = "${PiUser}@${PiHost}"

Write-Host "Project root: $ProjectRoot"
Write-Host "Target Pi:     $RemoteTarget"
Write-Host "Remote dir:    $RemoteDir"
Write-Host ""

Write-Host "Removing old SSH host key for $PiHost if it exists..."
ssh-keygen -R $PiHost | Out-Null

Write-Host "Creating runtime update archive..."
Push-Location $ProjectRoot
if (Test-Path $ArchivePath) {
    Remove-Item $ArchivePath -Force
}

tar `
    --exclude="__pycache__" `
    --exclude=".pytest_cache" `
    --exclude="*.pyc" `
    --exclude="data/*.sqlite3" `
    --exclude="data/*.sqlite3-*" `
    --exclude="data/audio" `
    -czf $ArchiveName `
    app.py `
    requirements.txt `
    templates `
    static `
    tcm_demo `
    deploy/raspberry-pi/start-tcm-kiosk.sh
Pop-Location

Write-Host ""
Write-Host "Uploading archive. If prompted, enter the Pi password."
scp -o StrictHostKeyChecking=accept-new $ArchivePath "${RemoteTarget}:${RemoteDir}/${ArchiveName}"

Write-Host ""
Write-Host "Extracting on Pi and restarting service. If prompted, enter the Pi password."
ssh -o StrictHostKeyChecking=accept-new $RemoteTarget "cd $RemoteDir && tar -xzf $ArchiveName && rm $ArchiveName && if [ -f deploy/raspberry-pi/start-tcm-kiosk.sh ]; then cp deploy/raspberry-pi/start-tcm-kiosk.sh /home/pi/start-tcm-kiosk.sh && chmod +x /home/pi/start-tcm-kiosk.sh; fi && sudo systemctl restart tcm-diagnosis && sudo systemctl status tcm-diagnosis --no-pager"

Write-Host ""
Write-Host "Done. Open:"
Write-Host "  http://$PiHost`:5000/"
Write-Host "If you enabled internal HTTPS/Nginx, also try:"
Write-Host "  https://$PiHost/"
