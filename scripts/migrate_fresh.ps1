# Reset DB and run Alembic migrations using .env POSTGRES_* settings.
param(
    [string]$SuperUser = "postgres"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$resolve = Join-Path $root "scripts\resolve_postgres.ps1"
$cfg = & $resolve

$find = Join-Path $root "scripts\find_psql.ps1"
$psql = if ($cfg.PsqlBin -and (Test-Path $cfg.PsqlBin)) {
    $cfg.PsqlBin
} else {
    & $find -VersionHint $cfg.Target
}

Write-Host "Target: $($cfg.Target) port $($cfg.Port)"
Write-Host "Resetting partial schema in $($cfg.Database)..."
& $psql -U $SuperUser -h $cfg.Host -p $cfg.Port -d $cfg.Database `
    -f (Join-Path $root "scripts\reset_migrations.sql")

Write-Host "Running alembic upgrade head..."
Push-Location $root
try {
    alembic upgrade head
} finally {
    Pop-Location
}

Write-Host "Done."
