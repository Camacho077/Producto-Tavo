<#
.SYNOPSIS
    Deja el proyecto listo para desarrollar en una máquina nueva (Windows).

.DESCRIPTION
    Pensado para quien acaba de clonar el repositorio. Es IDEMPOTENTE: se
    puede correr cuantas veces se quiera; lo que ya está hecho se salta.

      1. Revisa requisitos (Python 3.11+, Node 18+, Postgres o Docker).
      2. Copia backend/.env.example y frontend/.env.example a .env si no
         existen (con una SECRET_KEY aleatoria en el backend).
      3. Crea backend/venv e instala las dependencias de Python.
      4. Instala las dependencias de npm del frontend.
      5. Arranca Postgres con Docker si no hay uno escuchando en el 5432,
         y crea la base de datos si no existe.
      6. Corre `alembic upgrade head`.
      7. Crea la empresa y el usuario de prueba, y carga los datos de
         demostración (seed_demo.py).
      8. Corre el diagnóstico y muestra URLs y credenciales.

.PARAMETER Arrancar
    Al terminar, abre backend (8001) y frontend (5173) en dos ventanas nuevas.

.EXAMPLE
    # Desde la raíz del repositorio:
    powershell -ExecutionPolicy Bypass -File automatizaciones\setup.ps1
    powershell -ExecutionPolicy Bypass -File automatizaciones\setup.ps1 -Arrancar
#>
param([switch]$Arrancar)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = "utf-8"

$raiz = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $raiz "backend"
$frontend = Join-Path $raiz "frontend"
$pythonVenv = Join-Path $backend "venv\Scripts\python.exe"

# Credenciales de la cuenta de prueba (solo desarrollo).
$DEMO_EMPRESA = "Empresa Demo"
$DEMO_EMAIL = "demo@jscompany.co"
$DEMO_CLAVE = "Demo2026!"

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Bien($texto) { Write-Host "    [OK] $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "    [!] $texto" -ForegroundColor Yellow }
function Falla($texto, $arreglo) {
    Write-Host ""
    Write-Host "    [ERROR] $texto" -ForegroundColor Red
    if ($arreglo) { Write-Host "    -> $arreglo" -ForegroundColor Red }
    Write-Host ""
    exit 1
}
function Correr($descripcion, [scriptblock]$bloque) {
    & $bloque
    if ($LASTEXITCODE -ne 0) { Falla "$descripcion terminó con código $LASTEXITCODE" "Revisa la salida de arriba." }
}
function PuertoEscucha([int]$puerto) {
    $cliente = New-Object System.Net.Sockets.TcpClient
    try {
        $intento = $cliente.BeginConnect("127.0.0.1", $puerto, $null, $null)
        return ($intento.AsyncWaitHandle.WaitOne(500) -and $cliente.Connected)
    } catch { return $false } finally { $cliente.Close() }
}

# ---------------------------------------------------------------- 1. Requisitos
Paso "1/8 Revisando requisitos"

$python = $null
foreach ($opcion in @("py -3", "python")) {
    $candidato = $opcion.Split(" ")
    if (Get-Command $candidato[0] -ErrorAction SilentlyContinue) {
        $argsVersion = @($candidato | Select-Object -Skip 1) + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        try { $version = & $candidato[0] @argsVersion } catch { $version = $null }
        if ($LASTEXITCODE -eq 0 -and $version -and [version]$version -ge [version]"3.11") {
            $python = $candidato; break
        }
    }
}
if (-not $python) {
    Falla "No se encontró Python 3.11 o superior." "Instálalo desde https://www.python.org/downloads/ (marca 'Add python.exe to PATH') y abre una terminal nueva."
}
Bien "Python $version"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Falla "No se encontró Node.js." "Instala Node 20 LTS o superior desde https://nodejs.org y abre una terminal nueva."
}
$versionNode = (node --version).TrimStart("v")
if ([version]$versionNode -lt [version]"18.0") { Falla "Node $versionNode es muy viejo." "Instala Node 20 LTS o superior." }
Bien "Node $versionNode"

# ---------------------------------------------------------------- 2. Archivos .env
Paso "2/8 Archivos de configuración (.env)"

$envBackend = Join-Path $backend ".env"
if (Test-Path $envBackend) {
    Bien "backend/.env ya existe (no se toca)"
} else {
    $contenido = Get-Content (Join-Path $backend ".env.example") -Raw -Encoding UTF8
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $clave = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
    $contenido = $contenido -replace "(?m)^SECRET_KEY=.*$", "SECRET_KEY=$clave"
    [System.IO.File]::WriteAllText($envBackend, $contenido, (New-Object System.Text.UTF8Encoding($false)))
    Bien "backend/.env creado desde .env.example (con SECRET_KEY aleatoria)"
}

$envFrontend = Join-Path $frontend ".env"
if (Test-Path $envFrontend) {
    Bien "frontend/.env ya existe (no se toca)"
} else {
    Copy-Item (Join-Path $frontend ".env.example") $envFrontend
    Bien "frontend/.env creado desde .env.example"
}

# ---------------------------------------------------------------- 3. Python
Paso "3/8 Entorno virtual de Python y dependencias"

if (-not (Test-Path $pythonVenv)) {
    $argsVenv = @($python | Select-Object -Skip 1) + @("-m", "venv", (Join-Path $backend "venv"))
    Correr "Crear el venv" { & $python[0] @argsVenv }
    Bien "backend/venv creado"
} else {
    Bien "backend/venv ya existe"
}
Correr "Actualizar pip" { & $pythonVenv -m pip install --quiet --disable-pip-version-check --upgrade pip }
Correr "pip install" { & $pythonVenv -m pip install --quiet --disable-pip-version-check -r (Join-Path $backend "requirements-dev.txt") }
Bien "Dependencias de Python instaladas"

# ---------------------------------------------------------------- 4. npm
Paso "4/8 Dependencias del frontend (npm)"
Push-Location $frontend
try {
    if (Test-Path "package-lock.json") {
        Correr "npm ci" { npm ci --no-audit --no-fund --loglevel=error }
    } else {
        Correr "npm install" { npm install --no-audit --no-fund --loglevel=error }
    }
} finally { Pop-Location }
Bien "Dependencias de npm instaladas"

# ---------------------------------------------------------------- 5. Postgres
Paso "5/8 Base de datos (Postgres)"

if (PuertoEscucha 5432) {
    Bien "Postgres escucha en el puerto 5432"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    Aviso "No hay Postgres en el 5432: lo arranco con Docker (infra/docker-compose.yml, servicio db)"
    Correr "docker compose up -d db" { docker compose -f (Join-Path $raiz "infra\docker-compose.yml") up -d db }
} else {
    Falla "No hay Postgres escuchando en el puerto 5432 y no está Docker." "Instala Docker Desktop (y vuelve a correr este script) o PostgreSQL 16 con el usuario js_admin / clave js_admin (ver README, 'Empezar desde cero')."
}

Push-Location $backend
try {
    Correr "Preparar la base" { & $pythonVenv (Join-Path $raiz "automatizaciones\dev\preparar_base.py") }

    # ------------------------------------------------------------ 6. Migraciones
    Paso "6/8 Migraciones (alembic upgrade head)"
    Correr "alembic upgrade head" { & $pythonVenv -m alembic upgrade head }
    Bien "Esquema al día"

    # ------------------------------------------------------------ 7. Datos de prueba
    Paso "7/8 Usuario y datos de prueba"
    Correr "Crear el usuario de prueba" {
        & $pythonVenv (Join-Path $raiz "automatizaciones\deploy\alta_tenant.py") --empresa $DEMO_EMPRESA --plan pro_ia `
            --admin-email $DEMO_EMAIL --admin-password $DEMO_CLAVE --si-no-existe
    }
    Correr "Cargar datos de demostración" {
        & $pythonVenv (Join-Path $raiz "automatizaciones\deploy\seed_demo.py") --email $DEMO_EMAIL
    }

    # ------------------------------------------------------------ 8. Diagnóstico
    Paso "8/8 Diagnóstico del entorno"
    & $pythonVenv -m app.diagnostico
    $diagnosticoOk = ($LASTEXITCODE -eq 0)
} finally { Pop-Location }

if (-not $diagnosticoOk) { Falla "El diagnóstico encontró errores." "Arregla los puntos marcados con ✘ y vuelve a correr este script." }

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host " Listo. Para trabajar, arranca cada parte en su propia terminal:" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "   Backend :  powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-backend.ps1"
Write-Host "   Frontend:  powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-frontend.ps1"
Write-Host ""
Write-Host "   Aplicación:        http://localhost:5173"
Write-Host "   API (docs):        http://localhost:8001/docs"
Write-Host "   Diagnóstico:       http://localhost:8001/diagnostico   (o: cd backend; venv\Scripts\python -m app.diagnostico)"
Write-Host ""
Write-Host "   Cuenta de prueba:  $DEMO_EMAIL" -ForegroundColor Yellow
Write-Host "   Contraseña:        $DEMO_CLAVE" -ForegroundColor Yellow
Write-Host "   (empresa '$DEMO_EMPRESA' con categorías, productos, compras, ventas y pedidos de ejemplo)"
Write-Host ""

if ($Arrancar) {
    $shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
    Start-Process $shell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $raiz "automatizaciones\dev\start-backend.ps1")
    Start-Process $shell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $raiz "automatizaciones\dev\start-frontend.ps1")
    Write-Host "   Backend y frontend abiertos en dos ventanas nuevas." -ForegroundColor Green
}
