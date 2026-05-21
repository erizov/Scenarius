# List PostgreSQL instances and ports on this machine.
$ErrorActionPreference = "SilentlyContinue"

Write-Host "Scenarius PostgreSQL targets (see data/postgres_instances.yaml):"
Write-Host ""
Write-Host "  docker  -> localhost:5435  (pgvector included, docker compose up db -d)"
Write-Host "  pg16    -> localhost:5434  (native PostgreSQL 16)"
Write-Host "  pg17    -> localhost:5433  (native PostgreSQL 17)"
Write-Host "  pg15    -> localhost:5432  (E:/Postgres/15, no pgvector)"
Write-Host ""

$resolve = Join-Path $PSScriptRoot "resolve_postgres.ps1"
if (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) ".env")) {
    $cfg = & $resolve
    Write-Host "Current .env -> POSTGRES_TARGET=$($cfg.Target) port $($cfg.Port)"
    Write-Host "  $($cfg.DatabaseUrl)"
    Write-Host ""
}

Write-Host "Listening ports (Get-NetTCPConnection):"
$ports = @(5432, 5433, 5434, 5435)
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host "  port $port : LISTEN"
    } else {
        Write-Host "  port $port : (not listening)"
    }
}

Write-Host ""
Write-Host "psql binaries found:"
$bins = @(
    "E:\Postgres\15\bin\psql.exe",
    "$env:ProgramFiles\PostgreSQL\16\bin\psql.exe",
    "$env:ProgramFiles\PostgreSQL\17\bin\psql.exe",
    "$env:ProgramFiles\PostgreSQL\18\bin\psql.exe"
)
foreach ($bin in $bins) {
    if (Test-Path $bin) {
        Write-Host "  $bin"
    }
}
