# Find psql.exe on Windows (PostgreSQL installs it under Program Files).
param(
    [string]$VersionHint = "",
    [string[]]$Candidates = @()
)

if (-not $Candidates -or $Candidates.Count -eq 0) {
    $Candidates = @(
        "psql",
        "E:\Postgres\15\bin\psql.exe",
        "$env:ProgramFiles\PostgreSQL\16\bin\psql.exe",
        "$env:ProgramFiles\PostgreSQL\17\bin\psql.exe",
        "$env:ProgramFiles\PostgreSQL\18\bin\psql.exe"
    )
}

if ($VersionHint -eq "pg16") {
    $Candidates = @(
        "$env:ProgramFiles\PostgreSQL\16\bin\psql.exe"
    ) + $Candidates
} elseif ($VersionHint -eq "pg17") {
    $Candidates = @(
        "$env:ProgramFiles\PostgreSQL\17\bin\psql.exe"
    ) + $Candidates
} elseif ($VersionHint -eq "pg15") {
    $Candidates = @("E:\Postgres\15\bin\psql.exe") + $Candidates
}

foreach ($candidate in $Candidates) {
    if ($candidate -eq "psql") {
        $cmd = Get-Command psql -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
        continue
    }
    if (Test-Path $candidate) {
        return $candidate
    }
}

Write-Error "psql not found. Install PostgreSQL or add its bin folder to PATH."
return $null
