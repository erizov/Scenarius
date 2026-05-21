# Start Scenarius web UI (FastAPI + uvicorn).
. "$PSScriptRoot\ui_common.ps1"
Initialize-UiPaths

if (Test-UiRunning) {
    $uiPid = Get-UiPid
    Write-Host "UI already running (PID $uiPid): $(Get-UiUrl)comment"
    exit 0
}

$stale = Get-PortListenerPids -Port $UiPort
if ($stale.Count -gt 0) {
    Write-Host "Clearing stale listeners on port $UiPort..."
    Stop-UiPortListeners | Out-Null
    Start-Sleep -Seconds 1
}

Write-Host "Starting Scenarius UI on $(Get-UiUrl)"
$proc = Start-Process `
    -FilePath $UiVenvPython `
    -ArgumentList @(
        "-m", "uvicorn",
        "app.main:app",
        "--host", $UiHost,
        "--port", "$UiPort"
    ) `
    -WorkingDirectory $UiRoot `
    -PassThru `
    -WindowStyle Hidden

Set-Content -Path $UiPidFile -Value $proc.Id -Encoding ascii
Start-Sleep -Seconds 3

$listening = Get-NetTCPConnection `
    -LocalPort $UiPort `
    -State Listen `
    -ErrorAction SilentlyContinue

if (-not $listening) {
    if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
        Write-Host "UI failed to start. Try manually:"
        Write-Host "  .venv\Scripts\python.exe -m uvicorn app.main:app --reload"
        if (Test-Path $UiPidFile) {
            Remove-Item $UiPidFile -Force
        }
        exit 1
    }
}

Write-Host "UI started (PID $($proc.Id))"
Write-Host "  Comment: $(Get-UiUrl)comment"
Write-Host "  Corpus:  $(Get-UiUrl)"
