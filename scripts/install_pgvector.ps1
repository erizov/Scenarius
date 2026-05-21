# Install pgvector prebuilt binaries for native PostgreSQL on Windows.
# Run from an elevated PowerShell (Run as administrator).
param(
    [int]$PgMajor = 18,
    [string]$PgRoot = "",
    [string]$ReleaseUrl = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not $PgRoot) {
    $PgRoot = Join-Path ${env:ProgramFiles} "PostgreSQL\$PgMajor"
}
if (-not (Test-Path $PgRoot)) {
    Write-Error "PostgreSQL $PgMajor not found at $PgRoot"
}

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error @"
Administrator rights required to copy into:
  $PgRoot\lib
  $PgRoot\share\extension
Re-run PowerShell as Administrator, then:
  .\scripts\install_pgvector.ps1 -PgMajor $PgMajor
"@
}

if (-not $ReleaseUrl) {
    $ReleaseUrl = "https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.2_${PgMajor}.0.2/vector.v0.8.2-pg${PgMajor}.zip"
}

$zip = Join-Path $env:TEMP "vector.pg${PgMajor}.zip"
$extract = Join-Path $env:TEMP "pgvector-pg${PgMajor}"
Write-Host "Downloading pgvector for PostgreSQL $PgMajor..."
Invoke-WebRequest -Uri $ReleaseUrl -OutFile $zip -UseBasicParsing
if (Test-Path $extract) {
    Remove-Item $extract -Recurse -Force
}
Expand-Archive $zip -DestinationPath $extract

Copy-Item (Join-Path $extract "lib\vector.dll") (Join-Path $PgRoot "lib\") -Force
Copy-Item (Join-Path $extract "share\extension\vector*") (
    Join-Path $PgRoot "share\extension\"
) -Force

Write-Host "pgvector files installed under $PgRoot"
Write-Host "Enable in database (as postgres superuser):"
Write-Host "  psql -U postgres -h localhost -p <port> -d scenarius -f scripts\setup_db_extensions.sql"
Write-Host "Then:"
Write-Host "  alembic upgrade head"
Write-Host "  python -m scrapers.cli embed-all"
