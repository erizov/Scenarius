# Show Scenarius ingestion totals (ru/en, authors, sources).
param(
    [switch]$Watch,
    [double]$Interval = 5,
    [int]$RecentMinutes = 5
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    $python = "python"
}

$argsList = @("-m", "scrapers.cli", "stats")
if ($Watch) { $argsList += "--watch" }
$argsList += @("--interval", $Interval, "--recent-minutes", $RecentMinutes)

Push-Location $root
try {
    & $python @argsList
} finally {
    Pop-Location
}
