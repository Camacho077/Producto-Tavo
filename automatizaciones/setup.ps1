<#
.SYNOPSIS
    Deja el Producto Tavo funcionando en una máquina nueva (Windows) y lo
    COMPRUEBA: solo dice "Listo" si el backend responde y el login de la
    demo entra.

.DESCRIPTION
    Pensado para quien acaba de clonar el repositorio. Es IDEMPOTENTE: se
    puede correr cuantas veces se quiera; lo que ya está hecho se salta.

      1. Requisitos: Python 3.11+, Node 18+ y Docker Desktop ENCENDIDO.
      2. Copia backend/.env.example y frontend/.env.example a .env si faltan
         (con una SECRET_KEY aleatoria en el backend).
      3. Puertos: si el 8002 (o el 5433 / 5175) está reservado por Windows u
         ocupado por otro programa, elige el siguiente libre y lo escribe en
         backend/.env, frontend/.env e infra/.env, para que backend y
         frontend apunten al mismo (automatizaciones/dev/puertos.py).
      4. backend/venv con sus dependencias y npm ci del frontend.
      5. Postgres en Docker (espera a que esté listo) y migraciones.
      6. Datos de demostración: si la base está VACÍA (y nunca con
         ENV=production) carga Donde Tavo y Café Central (~5 min).
      7. Backend y frontend en Docker, esperando el healthcheck.
      8. Comprueba de verdad: GET /health, POST /seguridad/login con
         admin@dondetavo.demo y la página del frontend. Imprime la URL y las
         cuentas.

    Si algo falla, dice la causa y qué hacer. Para revisar después:
        powershell -ExecutionPolicy Bypass -File automatizaciones\dev\diagnostico.ps1

.EXAMPLE
    # Desde la raíz del repositorio:
    powershell -ExecutionPolicy Bypass -File automatizaciones\setup.ps1
#>
param()

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = "utf-8"

$raiz = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $raiz "backend"
$frontend = Join-Path $raiz "frontend"
$compose = Join-Path $raiz "infra\docker-compose.yml"
$pythonVenv = Join-Path $backend "venv\Scripts\python.exe"

$CUENTAS = @(
    @{ Rol = "Administrador"; Correo = "admin@dondetavo.demo";  Clave = "Tavo2026*Admin";  Entra = "Dashboard" },
    @{ Rol = "Cajero";        Correo = "caja@dondetavo.demo";   Clave = "Tavo2026*Caja";   Entra = "Caja" },
    @{ Rol = "Mesero";        Correo = "mesero@dondetavo.demo"; Clave = "Tavo2026*Mesero"; Entra = "Tomar pedido (celular)" },
    @{ Rol = "Cocinero";      Correo = "cocina@dondetavo.demo"; Clave = "Tavo2026*Cocina"; Entra = "Cocina (tablet)" }
)

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Bien($texto) { Write-Host "    [OK] $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "    [!] $texto" -ForegroundColor Yellow }
function Falla($texto, $arreglo) {
    Write-Host ""
    Write-Host "    [ERROR] $texto" -ForegroundColor Red
    if ($arreglo) { Write-Host "    -> $arreglo" -ForegroundColor Red }
    Write-Host "    -> Diagnóstico completo: powershell -ExecutionPolicy Bypass -File automatizaciones\dev\diagnostico.ps1" -ForegroundColor Red
    Write-Host ""
    exit 1
}
function Correr($descripcion, [scriptblock]$bloque) {
    & $bloque
    if ($LASTEXITCODE -ne 0) { Falla "$descripcion terminó con código $LASTEXITCODE" "Revisa la salida de arriba." }
}
function Docker-Compose { & docker compose -f $compose @args }
function Mostrar-Logs($servicio) {
    Write-Host "    --- últimas líneas de '$servicio' ---" -ForegroundColor DarkGray
    Docker-Compose logs --tail 25 $servicio 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
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

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Falla "No se encontró Docker." "Instala Docker Desktop (https://www.docker.com/products/docker-desktop/), ábrelo y vuelve a correr este script."
}
& docker info --format "{{.ServerVersion}}" *> $null
if ($LASTEXITCODE -ne 0) {
    Falla "Docker está instalado pero no está encendido." "Abre Docker Desktop, espera a que diga 'Engine running' y vuelve a correr este script."
}
Bien "Docker encendido"

# ---------------------------------------------------------------- 2. Archivos .env
Paso "2/8 Archivos de configuración (.env)"

$envBackend = Join-Path $backend ".env"
if (Test-Path $envBackend) {
    Bien "backend/.env ya existe (se conserva)"
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
    Bien "frontend/.env ya existe (se conserva)"
} else {
    Copy-Item (Join-Path $frontend ".env.example") $envFrontend
    Bien "frontend/.env creado desde .env.example"
}

# ---------------------------------------------------------------- 3. Puertos
Paso "3/8 Puertos de esta máquina"
$argsPuertos = @($python | Select-Object -Skip 1) + @((Join-Path $raiz "automatizaciones\dev\puertos.py"), "--json")
$salidaPuertos = & $python[0] @argsPuertos
if ($LASTEXITCODE -ne 0) { Falla "No se pudieron elegir los puertos." "Revisa la salida de arriba." }
$salidaPuertos | Select-Object -SkipLast 1 | ForEach-Object { Write-Host "  $_" }
$puertos = ($salidaPuertos | Select-Object -Last 1) | ConvertFrom-Json
$PUERTO_DB = [int]$puertos.puertos.db
$PUERTO_BACKEND = [int]$puertos.puertos.backend
$PUERTO_FRONTEND = [int]$puertos.puertos.frontend
foreach ($a in $puertos.avisos) { Aviso $a }
Bien "Postgres $PUERTO_DB · backend $PUERTO_BACKEND · frontend $PUERTO_FRONTEND (proyecto Docker '$($puertos.proyecto)')"

# ---------------------------------------------------------------- 4. Dependencias
Paso "4/8 Dependencias (Python y npm)"

if (-not (Test-Path $pythonVenv)) {
    $argsVenv = @($python | Select-Object -Skip 1) + @("-m", "venv", (Join-Path $backend "venv"))
    Correr "Crear el venv" { & $python[0] @argsVenv }
    Bien "backend/venv creado"
}
Correr "Actualizar pip" { & $pythonVenv -m pip install --quiet --disable-pip-version-check --upgrade pip }
Correr "pip install" { & $pythonVenv -m pip install --quiet --disable-pip-version-check -r (Join-Path $backend "requirements-dev.txt") }
Bien "Dependencias de Python instaladas"

Push-Location $frontend
try {
    if (Test-Path "package-lock.json") {
        Correr "npm ci" { npm ci --no-audit --no-fund --loglevel=error }
    } else {
        Correr "npm install" { npm install --no-audit --no-fund --loglevel=error }
    }
} finally { Pop-Location }
Bien "Dependencias de npm instaladas"

# ---------------------------------------------------------------- 5. Postgres y migraciones
Paso "5/8 Base de datos (Postgres en Docker) y migraciones"
Docker-Compose up -d --wait --wait-timeout 120 db
if ($LASTEXITCODE -ne 0) {
    Mostrar-Logs "db"
    Falla "Postgres no quedó listo." "Revisa los mensajes de arriba (¿el puerto $PUERTO_DB lo tomó otro programa?)."
}
Bien "Postgres listo en el puerto $PUERTO_DB"

Push-Location $backend
try {
    Correr "Preparar la base" { & $pythonVenv (Join-Path $raiz "automatizaciones\dev\preparar_base.py") }
    Correr "alembic upgrade head" { & $pythonVenv -m alembic upgrade head }
    Bien "Esquema al día"

    # ------------------------------------------------------------ 6. Datos demo
    Paso "6/8 Datos de demostración"
    $estado = (& $pythonVenv (Join-Path $raiz "automatizaciones\dev\estado_base.py")) | ConvertFrom-Json
    if ($estado.env -eq "production") {
        Aviso "ENV=production: los datos de demostración NO se cargan."
    } elseif (-not $estado.usuarios) {
        Write-Host "    La base está vacía: cargo Donde Tavo y Café Central (unos 5 minutos)..."
        Correr "Cargar datos de demostración" { & $pythonVenv (Join-Path $raiz "automatizaciones\deploy\seed_demo.py") }
        Bien "Datos de demostración cargados"
    } elseif ($estado.cuentas_demo.Count -lt 4) {
        Aviso "La base ya tiene datos pero faltan cuentas demo ($($estado.cuentas_demo -join ', ')). No la toco."
        Aviso "Para cargarlas: cd backend; venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py"
    } else {
        Bien "La base ya tiene datos y las 4 cuentas demo (no se recarga)"
    }
} finally { Pop-Location }

# ---------------------------------------------------------------- 7. Backend y frontend
Paso "7/8 Backend y frontend (Docker)"
$servicios = @()
if ($puertos.estados.backend -eq "propio" -and -not (& docker ps --filter "name=^$($puertos.proyecto)-backend$" --format "{{.Names}}")) {
    Bien "Ya hay un backend de esta carpeta corriendo en el $PUERTO_BACKEND (lo uso tal cual)"
} else { $servicios += "backend" }
if ($puertos.estados.frontend -eq "propio" -and -not (& docker ps --filter "name=^$($puertos.proyecto)-frontend$" --format "{{.Names}}")) {
    Bien "Ya hay un frontend de esta carpeta corriendo en el $PUERTO_FRONTEND (lo uso tal cual)"
} else { $servicios += "frontend" }

if ($servicios.Count) {
    Write-Host "    Construyendo y arrancando: $($servicios -join ', ') (la primera vez tarda unos minutos)..."
    $extra = if ($servicios -notcontains "backend") { @("--no-deps") } else { @() }
    Docker-Compose --profile frontend up -d --build --wait --wait-timeout 300 @extra @servicios
    if ($LASTEXITCODE -ne 0) {
        foreach ($s in $servicios) { Mostrar-Logs $s }
        Falla "El backend o el frontend no quedaron arriba." "El motivo está en las líneas de arriba (el backend explica en español qué le falta)."
    }
    Bien "Contenedores arriba: $($servicios -join ', ')"
}

# ---------------------------------------------------------------- 8. Comprobación
Paso "8/8 Comprobando que de verdad se puede entrar"
$api = "http://localhost:$PUERTO_BACKEND/api/v1"
$salud = $null
for ($i = 0; $i -lt 30 -and -not $salud; $i++) {
    try { $salud = Invoke-RestMethod "http://localhost:$PUERTO_BACKEND/health" -TimeoutSec 5 } catch { Start-Sleep -Seconds 2 }
}
if (-not $salud -or $salud.status -ne "ok") {
    Falla "El backend no responde en http://localhost:$PUERTO_BACKEND/health." "Mira sus mensajes: docker compose -f infra/docker-compose.yml logs backend"
}
Bien "Backend responde en http://localhost:$PUERTO_BACKEND/health"

try {
    $cuerpo = @{ email = $CUENTAS[0].Correo; password = $CUENTAS[0].Clave } | ConvertTo-Json
    $sesion = Invoke-RestMethod "$api/seguridad/login" -Method Post -Body $cuerpo -ContentType "application/json" -TimeoutSec 15
} catch {
    $detalle = $_.ErrorDetails.Message
    Falla "El login de $($CUENTAS[0].Correo) falló: $detalle" "Si la base no tiene la demo: cd backend; venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py"
}
if (-not $sesion.access_token) { Falla "El login no devolvió token." "Revisa: docker compose -f infra/docker-compose.yml logs backend" }
Bien "Login de $($CUENTAS[0].Correo) correcto"

$web = $null
for ($i = 0; $i -lt 45 -and -not $web; $i++) {
    try { $web = Invoke-WebRequest "http://localhost:$PUERTO_FRONTEND/" -UseBasicParsing -TimeoutSec 5 } catch { Start-Sleep -Seconds 2 }
}
if (-not $web -or $web.StatusCode -ne 200) {
    Falla "El frontend no responde en http://localhost:$PUERTO_FRONTEND." "Mira sus mensajes: docker compose -f infra/docker-compose.yml --profile frontend logs frontend"
}
$apiFrontend = (Get-Content $envFrontend -Encoding UTF8 | Select-String "^VITE_API_URL=").Line -replace "^VITE_API_URL=", ""
Bien "Frontend responde en http://localhost:$PUERTO_FRONTEND (llama a $api)"
if ($apiFrontend -ne $api) { Aviso "frontend/.env dice VITE_API_URL=$apiFrontend (para 'npm run dev' local); el contenedor usa $api." }

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host " Listo: el backend responde y el login de la demo entra." -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "   Abre:  http://localhost:$PUERTO_FRONTEND" -ForegroundColor Green
Write-Host "   API:   http://localhost:$PUERTO_BACKEND/docs"
Write-Host ""
Write-Host ("   {0,-14} {1,-24} {2,-17} {3}" -f "Rol", "Correo", "Contraseña", "Entra a")
foreach ($c in $CUENTAS) { Write-Host ("   {0,-14} {1,-24} {2,-17} {3}" -f $c.Rol, $c.Correo, $c.Clave, $c.Entra) -ForegroundColor Yellow }
Write-Host ""
Write-Host "   Recargar los datos demo:  cd backend; venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py --reset"
Write-Host "   Si algo deja de andar:    powershell -ExecutionPolicy Bypass -File automatizaciones\dev\diagnostico.ps1"
Write-Host "   Apagar:                   docker compose -f infra/docker-compose.yml --profile frontend stop"
Write-Host ""
