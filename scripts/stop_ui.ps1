# Stop Scenarius web UI and free the configured port.
. "$PSScriptRoot\ui_common.ps1"
Initialize-UiPaths

$uiPid = Get-UiPid
if ($uiPid) {
    $proc = Get-Process -Id $uiPid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $uiPid -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped UI (PID $uiPid)."
    }
}

$portPids = Stop-UiPortListeners
foreach ($procId in $portPids) {
    if ($procId -ne $uiPid) {
        Write-Host "Stopped stale listener on port $UiPort (PID $procId)."
    }
}

if (-not $uiPid -and $portPids.Count -eq 0) {
    Write-Host "UI is not running on port $UiPort."
}

if (Test-Path $UiPidFile) {
    Remove-Item $UiPidFile -Force
}
