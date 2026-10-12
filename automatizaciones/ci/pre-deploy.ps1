#requires -version 7
<#
Script de pre-deploy: corre todo lo que debe pasar en verde antes de
desplegar una nueva versión del sistema. Pensado para correrlo a mano
(o desde un pipeline) justo antes de cada deploy.

Uso:
    pwsh automatizaciones/ci/pre-deploy.ps1
#>

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Step {
    param([string]$Nombre, [scriptblock]$Accion)
    Write-Host "==> $Nombre" -ForegroundColor Cyan
    & $Accion
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✘ FALLÓ: $Nombre" -ForegroundColor Red
        exit 1
    }
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "✘ Docker Desktop no está corriendo. Ábrelo e intenta de nuevo." -ForegroundColor Red
    exit 1
}

Write-Host "==> Levantando Postgres (infra/docker-compose.yml)" -ForegroundColor Cyan
docker compose -f "$raiz/infra/docker-compose.yml" up -d db
if ($LASTEXITCODE -ne 0) { exit 1 }

Push-Location "$raiz/backend"
try {
    Step "pytest (backend)" { venv\Scripts\python.exe -m pytest -q }
    Step "alembic check (migraciones al día)" { venv\Scripts\python.exe -m alembic check }
} finally {
    Pop-Location
}

Push-Location "$raiz/frontend"
try {
    Step "lint (frontend)" { npm run lint }
    Step "test (frontend, Vitest)" { npm run test }
    Step "build (frontend)" { npm run build }
} finally {
    Pop-Location
}

Write-Host "✔ Pre-deploy OK: todo listo para desplegar" -ForegroundColor Green
