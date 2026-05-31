# Wrapper PowerShell para o load test harness (Sprint 19 PR3).
#
# Uso:
#   .\tests\load\run.ps1 up                    # sobe stack isolado
#   .\tests\load\run.ps1 migrate               # roda alembic upgrade head
#   .\tests\load\run.ps1 seed -Scale smoke     # popula DB com dataset sintético
#   .\tests\load\run.ps1 k6 -Scenario healthcheck
#   .\tests\load\run.ps1 k6 -Scenario das_mensal
#   .\tests\load\run.ps1 down                  # encerra + remove volumes

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("up", "down", "migrate", "seed", "k6", "logs", "status")]
    [string]$Action = "status",

    [ValidateSet("smoke", "moderate", "full")]
    [string]$Scale = "smoke",

    [string]$Scenario = "healthcheck",

    [string]$Duration = "1m",

    [int]$Rate = 20
)

$ErrorActionPreference = "Stop"
$ComposeFile = Join-Path $PSScriptRoot "docker-compose.load.yml"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Invoke-Compose {
    param([string[]]$Args)
    & docker compose -f $ComposeFile @Args
    if ($LASTEXITCODE -ne 0) { throw "docker compose falhou (exit $LASTEXITCODE)" }
}

switch ($Action) {
    "up" {
        Write-Host ">>> Subindo stack de load test (postgres + redis + api)..."
        Invoke-Compose @("up", "-d", "postgres", "redis", "api")
        Write-Host ">>> Stack pronto. API em http://localhost:8001"
    }
    "down" {
        Write-Host ">>> Encerrando stack + removendo volumes..."
        Invoke-Compose @("down", "-v")
    }
    "migrate" {
        Write-Host ">>> Aplicando migrations no Postgres de loadtest..."
        $env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
        Set-Location $ProjectRoot
        $env:DATABASE_URL = "postgresql+asyncpg://fiscal:fiscal@localhost:5435/fiscal"
        poetry run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "alembic falhou" }
    }
    "seed" {
        Write-Host ">>> Seedando preset '$Scale' contra DB de loadtest..."
        $env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
        Set-Location $ProjectRoot
        $env:DATABASE_URL = "postgresql+asyncpg://fiscal:fiscal@localhost:5435/fiscal"
        poetry run python -m scripts.seed.seed_1k_tenants --scale $Scale `
            --output (Join-Path $PSScriptRoot ".seed\empresas.json")
        if ($LASTEXITCODE -ne 0) { throw "seed falhou" }
    }
    "k6" {
        $scenarioFile = "/load/scenarios/$Scenario.js"
        Write-Host ">>> Rodando k6 scenario: $Scenario ($Duration)..."
        Invoke-Compose @(
            "run", "--rm",
            "-e", "DURATION=$Duration",
            "-e", "RATE=$Rate",
            "k6", "run", $scenarioFile
        )
    }
    "logs" {
        Invoke-Compose @("logs", "-f", "--tail=100", "api")
    }
    "status" {
        Invoke-Compose @("ps")
    }
}
