# Resolve PostgreSQL connection from .env POSTGRES_* or POSTGRES_TARGET.
param(
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $EnvFile) {
    $EnvFile = Join-Path $root ".env"
}

$targets = @{
    docker = @{ Port = 5435; PsqlBin = $null; Pgvector = $true }
    pg18   = @{ Port = 5434; PsqlBin = "$env:ProgramFiles\PostgreSQL\18\bin\psql.exe"; Pgvector = $false }
    pg16   = @{ Port = 5434; PsqlBin = "$env:ProgramFiles\PostgreSQL\16\bin\psql.exe"; Pgvector = $false }
    pg17   = @{ Port = 5433; PsqlBin = "$env:ProgramFiles\PostgreSQL\17\bin\psql.exe"; Pgvector = $false }
    pg15   = @{ Port = 5432; PsqlBin = "E:\Postgres\15\bin\psql.exe"; Pgvector = $false }
}

$vars = @{}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $name, $value = $_ -split '=', 2
        $vars[$name.Trim()] = $value.Trim()
    }
}

$target = if ($vars["POSTGRES_TARGET"]) { $vars["POSTGRES_TARGET"] } else { "pg16" }
$meta = $targets[$target]
if (-not $meta) {
    Write-Error "Unknown POSTGRES_TARGET '$target'. Use: docker, pg18, pg16, pg17, pg15"
}

[PSCustomObject]@{
    Target   = $target
    Host     = if ($vars["POSTGRES_HOST"]) { $vars["POSTGRES_HOST"] } else { "localhost" }
    Port     = if ($vars["POSTGRES_PORT"]) { [int]$vars["POSTGRES_PORT"] } else { $meta.Port }
    User     = if ($vars["POSTGRES_USER"]) { $vars["POSTGRES_USER"] } else { "scenarius" }
    Password = if ($vars["POSTGRES_PASSWORD"]) { $vars["POSTGRES_PASSWORD"] } else { "scenarius" }
    Database = if ($vars["POSTGRES_DB"]) { $vars["POSTGRES_DB"] } else { "scenarius" }
    PsqlBin  = $meta.PsqlBin
    Pgvector = $meta.Pgvector
    DatabaseUrl = if ($vars["DATABASE_URL"]) {
        $vars["DATABASE_URL"]
    } else {
        $u = if ($vars["POSTGRES_USER"]) { $vars["POSTGRES_USER"] } else { "scenarius" }
        $p = if ($vars["POSTGRES_PASSWORD"]) { $vars["POSTGRES_PASSWORD"] } else { "scenarius" }
        $h = if ($vars["POSTGRES_HOST"]) { $vars["POSTGRES_HOST"] } else { "localhost" }
        $port = if ($vars["POSTGRES_PORT"]) { $vars["POSTGRES_PORT"] } else { $meta.Port }
        $db = if ($vars["POSTGRES_DB"]) { $vars["POSTGRES_DB"] } else { "scenarius" }
        "postgresql+psycopg://${u}:${p}@${h}:${port}/${db}"
    }
}
