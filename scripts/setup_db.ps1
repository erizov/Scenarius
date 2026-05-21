# Create scenarius user/database on the PostgreSQL instance from .env.
param(
    [string]$SuperUser = "postgres",
    [string]$Target = "",
    [string]$DbHost = "",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$resolve = Join-Path $root "scripts\resolve_postgres.ps1"
$cfg = & $resolve

if ($Target) { $cfg.Target = $Target }
if ($DbHost) { $cfg.Host = $DbHost }
if ($Port -gt 0) { $cfg.Port = $Port }

$find = Join-Path $root "scripts\find_psql.ps1"
$psql = if ($cfg.PsqlBin -and (Test-Path $cfg.PsqlBin)) {
    $cfg.PsqlBin
} else {
    & $find -VersionHint $cfg.Target
}
if (-not $psql) { exit 1 }

$sql = Join-Path $root "scripts\setup_db.sql"

Write-Host "Target: $($cfg.Target) on $($cfg.Host):$($cfg.Port)"
Write-Host "Using psql: $psql"
Write-Host "Creating role/database scenarius..."
Write-Host "You may be prompted for the '$SuperUser' password."

& $psql -U $SuperUser -h $cfg.Host -p $cfg.Port -f $sql

if ($LASTEXITCODE -ne 0) {
    Write-Error "setup_db failed. Run .\scripts\detect_postgres.ps1 to check ports."
}

if ($cfg.Pgvector) {
    $ext = Join-Path $root "scripts\setup_db_extensions.sql"
    Write-Host "Enabling pgvector..."
    & $psql -U $SuperUser -h $cfg.Host -p $cfg.Port -d $cfg.Database -f $ext
}

Write-Host "Done. DATABASE_URL=$($cfg.DatabaseUrl)"
Write-Host "Run: alembic upgrade head"
