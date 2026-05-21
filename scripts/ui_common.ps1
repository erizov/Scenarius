# Shared paths and settings for Scenarius UI scripts.
$ErrorActionPreference = "Stop"

$Script:UiRoot = Split-Path $PSScriptRoot -Parent
$Script:UiRunDir = Join-Path $UiRoot ".run"
$Script:UiPidFile = Join-Path $UiRunDir "ui.pid"
$Script:UiLogFile = Join-Path $UiRunDir "ui.log"
$Script:UiVenvPython = Join-Path $UiRoot ".venv\Scripts\python.exe"
$Script:UiHost = "127.0.0.1"
$Script:UiPort = 8008

function Read-DotEnvValue {
    param(
        [string]$Key,
        [string]$Default = ""
    )
    $envPath = Join-Path $UiRoot ".env"
    if (-not (Test-Path $envPath)) {
        return $Default
    }
    $line = Get-Content $envPath | Where-Object {
        $_ -match "^\s*$([regex]::Escape($Key))\s*="
    } | Select-Object -First 1
    if (-not $line) {
        return $Default
    }
    return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

function Initialize-UiPaths {
    if (-not (Test-Path $UiRunDir)) {
        New-Item -ItemType Directory -Path $UiRunDir | Out-Null
    }
    if (-not (Test-Path $UiVenvPython)) {
        throw "Missing venv Python at $UiVenvPython. Run: python -m venv .venv"
    }
    $hostValue = Read-DotEnvValue -Key "APP_HOST" -Default $UiHost
    $portValue = Read-DotEnvValue -Key "APP_PORT" -Default "$UiPort"
    $Script:UiHost = $hostValue
    $Script:UiPort = [int]$portValue
}

function Get-UiPid {
    if (-not (Test-Path $UiPidFile)) {
        return $null
    }
    $raw = (Get-Content $UiPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $raw) {
        return $null
    }
    return [int]$raw
}

function Test-UiRunning {
    $uiPid = Get-UiPid
    if (-not $uiPid) {
        return $false
    }
    return [bool](Get-Process -Id $uiPid -ErrorAction SilentlyContinue)
}

function Get-UiUrl {
    return "http://${UiHost}:$UiPort/"
}

function Get-PortListenerPids {
    param([int]$Port)
    $pids = @()
    $pattern = ":$Port\s"
    $lines = netstat -ano | Select-String $pattern | Select-String "LISTENING"
    foreach ($line in $lines) {
        if ($line -match "\s(\d+)\s*$") {
            $procId = [int]$Matches[1]
            if ($procId -gt 0 -and $pids -notcontains $procId) {
                $pids += $procId
            }
        }
    }
    return $pids
}

function Stop-UiPortListeners {
    $killed = @()
    foreach ($procId in (Get-PortListenerPids -Port $UiPort)) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        $killed += $procId
    }
    return $killed
}
