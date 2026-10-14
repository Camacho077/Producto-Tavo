<#
.SYNOPSIS
    "No puedo entrar al sistema": revisa todo lo que tiene que estar bien para
    que el login funcione y dice, punto por punto, qué arreglar.

.DESCRIPTION
    Revisa, en orden:
      1. Docker encendido.
      2. Configuración: backend/.env, frontend/.env e infra/.env, y que el
         frontend apunte al MISMO puerto que el backend.
      3. Puertos: libres, propios, ocupados por otro programa o reservados
         por Windows (automatizaciones/dev/puertos.py --revisar).
      4. Contenedores de este producto (db, backend, frontend) y su salud.
      5. Backend: GET /health.
      6. Frontend: la página responde.
      7. Base de datos: migraciones al día y cuentas demo existentes.
      8. Login real con cada cuenta demo.

    No cambia nada. Sale con código 0 si todo está bien y 1 si algo falla.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File automatizaciones\dev\diagnostico.ps1
#>
param()

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = "utf-8"

$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backend = Join-Path $raiz "backend"
$frontend = Join-Path $raiz "frontend"
$compose = Join-Path $raiz "infra\docker-compose.yml"
$pythonVenv = Join-Path $backend "venv\Scripts\python.exe"
$script:problemas = 0

$CUENTAS = @(
    @("admin@dondetavo.demo", "Tavo2026*Admin"), @("caja@dondetavo.demo", "Tavo2026*Caja"),
    @("mesero@dondetavo.demo", "Tavo2026*Mesero"), @("cocina@dondetavo.demo", "Tavo2026*Cocina")
)

function Titulo($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "  ✔ $t" -ForegroundColor Green }
function Mal($t, $arreglo) {
    $script:problemas++
    Write-Host "  ✘ $t" -ForegroundColor Red
    if ($arreglo) { Write-Host "      → $arreglo" -ForegroundColor Yellow }
}
function Leer-Env($ruta) {
    $d = @{}
    if (Test-Path $ruta) {
        foreach ($l in Get-Content $ruta -Encoding UTF8) { if ($l -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $d[$Matches[1]] = $Matches[2].Trim() } }
    }
    return $d
}
function Puerto-De($url) { if ($url -match '://[^/]*:(\d+)') { return [int]$Matches[1] } return $null }

# ---------------------------------------------------------------- 1. Docker
Titulo "1. Docker"
$hayDocker = [bool](Get-Command docker -ErrorAction SilentlyContinue)
if (-not $hayDocker) {
    Mal "Docker no está instalado." "Instala Docker Desktop: https://www.docker.com/products/docker-desktop/"
} else {
    & docker info --format "{{.ServerVersion}}" *> $null
    if ($LASTEXITCODE -ne 0) { $hayDocker = $false; Mal "Docker no está encendido." "Abre Docker Desktop y espera 'Engine running'." }
    else { Ok "Docker encendido" }
}

# ---------------------------------------------------------------- 2. Configuración
Titulo "2. Configuración (.env)"
$eb = Leer-Env (Join-Path $backend ".env")
$ef = Leer-Env (Join-Path $frontend ".env")
$ei = Leer-Env (Join-Path $raiz "infra\.env")
if (-not $eb.Count) { Mal "Falta backend/.env." "Corre automatizaciones\setup.ps1 (lo crea desde backend/.env.example)." } else { Ok "backend/.env existe" }
if (-not $ef.Count) { Mal "Falta frontend/.env." "Corre automatizaciones\setup.ps1 (o copia frontend/.env.example a frontend/.env)." } else { Ok "frontend/.env existe" }
$proyecto = if ($ei.TAVO_PROYECTO) { $ei.TAVO_PROYECTO } else { "tavo" }
$pBack = if ($eb.PORT) { [int]$eb.PORT } else { 8002 }
$pFront = if ($ei.FRONTEND_PORT) { [int]$ei.FRONTEND_PORT } else { 5175 }
$pDb = if ($ei.DB_PORT) { [int]$ei.DB_PORT } else { 5433 }
$apiFrontend = $ef.VITE_API_URL
if ($apiFrontend) {
    if ((Puerto-De $apiFrontend) -ne $pBack) {
        Mal "El frontend llama al puerto $(Puerto-De $apiFrontend) (VITE_API_URL=$apiFrontend) pero el backend usa el $pBack (PORT en backend/.env)." `
            "Corre automatizaciones\setup.ps1: alinea los dos .env. Si usas 'npm run dev', reinícialo después."
    } else { Ok "Frontend y backend apuntan al mismo puerto ($pBack)" }
} elseif ($ef.Count) { Mal "frontend/.env no tiene VITE_API_URL." "Agrega: VITE_API_URL=http://localhost:$pBack/api/v1" }
if ($eb.DATABASE_URL -and (Puerto-De $eb.DATABASE_URL) -ne $pDb) {
    Mal "DATABASE_URL usa el puerto $(Puerto-De $eb.DATABASE_URL) pero Postgres en Docker se publica en el $pDb." "Corre automatizaciones\setup.ps1 para alinearlos."
}
if ($ei.Count -and $ei.BACKEND_PORT -and [int]$ei.BACKEND_PORT -ne $pBack) {
    Mal "infra/.env publica el backend en el $($ei.BACKEND_PORT) pero backend/.env dice PORT=$pBack." "Corre automatizaciones\setup.ps1 para alinearlos."
}

# ---------------------------------------------------------------- 3. Puertos
Titulo "3. Puertos (Postgres $pDb · backend $pBack · frontend $pFront)"
$python = if (Test-Path $pythonVenv) { $pythonVenv } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if ($python) {
    $salida = & $python (Join-Path $PSScriptRoot "puertos.py") --revisar 2>&1
    foreach ($l in $salida) {
        if ("$l" -match '^\s*!') {
            $script:problemas++
            Write-Host "  ✘ $("$l".Trim().TrimStart('!').Trim())" -ForegroundColor Red
            Write-Host "      → Ese puerto no se puede usar en esta máquina. Corre automatizaciones\setup.ps1: elige otro libre y actualiza los .env." -ForegroundColor Yellow
        } else { Write-Host "  $("$l".Trim())" -ForegroundColor Green }
    }
} else { Mal "No hay Python para revisar los puertos." "Instala Python 3.11+ y corre automatizaciones\setup.ps1." }

# ---------------------------------------------------------------- 4. Contenedores
Titulo "4. Contenedores ($proyecto-*)"
if ($hayDocker) {
    foreach ($s in @("db", "backend", "frontend")) {
        $nombre = "$proyecto-$s"
        $info = & docker inspect --format "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.State.ExitCode}}" $nombre 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $info) {
            if ($s -eq "db") { Mal "No existe el contenedor $nombre (Postgres)." "Corre automatizaciones\setup.ps1." }
            else { Write-Host "  · $nombre no existe (normal si corres $s con start-$s.ps1 / npm run dev)" -ForegroundColor DarkGray }
            continue
        }
        $estado, $salud, $codigo = "$info".Split("|")
        if ($estado -ne "running" -and $s -ne "db" -and @("0", "137", "143") -contains $codigo) {
            # Detenido a mano (stop / reinicio de Docker): no es un error en sí;
            # los puntos 5 y 6 dicen si de verdad hay backend y frontend.
            Write-Host "  · $nombre detenido. Para usarlo: docker compose -f infra/docker-compose.yml --profile frontend up -d $s" -ForegroundColor DarkGray
        } elseif ($estado -ne "running") {
            Mal "$nombre está '$estado' (código $codigo): se cayó." "Mira por qué: docker compose -f infra/docker-compose.yml --profile frontend logs --tail 30 $s"
            & docker logs --tail 8 $nombre 2>&1 | ForEach-Object { Write-Host "      | $_" -ForegroundColor DarkGray }
        } elseif ($salud -and $salud -ne "healthy") {
            Mal "$nombre está corriendo pero su salud es '$salud'." "docker compose -f infra/docker-compose.yml logs --tail 30 $s  (si dice 'starting', espera unos segundos)"
            & docker logs --tail 8 $nombre 2>&1 | ForEach-Object { Write-Host "      | $_" -ForegroundColor DarkGray }
        } else { Ok "$nombre $estado$(if ($salud) { " ($salud)" })" }
    }
}

# ---------------------------------------------------------------- 5. Backend
Titulo "5. Backend (http://localhost:$pBack)"
$saludOk = $false
try {
    $r = Invoke-RestMethod "http://localhost:$pBack/health" -TimeoutSec 5
    if ($r.status -eq "ok") { $saludOk = $true; Ok "GET /health responde ok ($($r.app))" } else { Mal "GET /health respondió $($r | ConvertTo-Json -Compress)" "" }
} catch {
    Mal "Nada responde en http://localhost:$pBack/health (es el ERR_CONNECTION_REFUSED del login)." `
        "Arranca el backend: corre automatizaciones\setup.ps1 (Docker) o automatizaciones\dev\start-backend.ps1 (local). Nunca 'uvicorn' a secas: va al 8000."
}

# ---------------------------------------------------------------- 6. Frontend
Titulo "6. Frontend (http://localhost:$pFront)"
try {
    $w = Invoke-WebRequest "http://localhost:$pFront/" -UseBasicParsing -TimeoutSec 5
    if ($w.StatusCode -eq 200) { Ok "La página responde en http://localhost:$pFront" } else { Mal "La página respondió $($w.StatusCode)." "" }
} catch {
    Mal "Nada responde en http://localhost:$pFront." "Corre automatizaciones\setup.ps1 (Docker) o automatizaciones\dev\start-frontend.ps1 (local, puerto 5175)."
}

# ---------------------------------------------------------------- 7. Base de datos
Titulo "7. Base de datos (migraciones y cuentas demo)"
if (Test-Path $pythonVenv) {
    Push-Location $backend
    try { $e = (& $pythonVenv (Join-Path $PSScriptRoot "estado_base.py") 2>$null | Select-Object -Last 1) | ConvertFrom-Json } catch { $e = $null } finally { Pop-Location }
    if (-not $e -or -not $e.conecta) {
        Mal "No se pudo conectar a Postgres con DATABASE_URL de backend/.env$(if ($e.error) { ": $($e.error)" })." "¿Está arriba el contenedor $proyecto-db? docker compose -f infra/docker-compose.yml up -d db"
    } else {
        if ($e.al_dia) { Ok "Migraciones al día ($($e.migracion))" }
        else { Mal "La base está en la migración '$($e.migracion)' y el código en '$($e.ultima)'." "cd backend; venv\Scripts\python -m alembic upgrade head" }
        $faltan = @($CUENTAS | ForEach-Object { $_[0] } | Where-Object { $e.cuentas_demo -notcontains $_ })
        if (-not $e.usuarios) { Mal "La base está VACÍA: no hay ningún usuario (tus datos no viajan por git)." "cd backend; venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py" }
        elseif ($faltan.Count) { Mal "Faltan cuentas demo: $($faltan -join ', ')." "cd backend; venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py --reset" }
        else { Ok "Las 4 cuentas demo existen ($($e.usuarios) usuarios en total)" }
    }
} else { Mal "No existe backend\venv." "Corre automatizaciones\setup.ps1." }

# ---------------------------------------------------------------- 8. Login
Titulo "8. Login con las cuentas demo"
if ($saludOk) {
    foreach ($c in $CUENTAS) {
        try {
            $t = Invoke-RestMethod "http://localhost:$pBack/api/v1/seguridad/login" -Method Post -ContentType "application/json" `
                -Body (@{ email = $c[0]; password = $c[1] } | ConvertTo-Json) -TimeoutSec 10
            if ($t.access_token) { Ok "$($c[0]) entra" } else { Mal "$($c[0]): sin token." "" }
        } catch {
            Mal "$($c[0]) no entra: $($_.ErrorDetails.Message)" "Carga la demo: cd backend; venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py --reset"
        }
    }
} else { Write-Host "  · se omite: el backend no responde (punto 5)" -ForegroundColor DarkGray }

Write-Host ""
if ($script:problemas) {
    Write-Host "✘ $script:problemas problema(s). Arregla los marcados con ✘ (empieza por el primero) y vuelve a correr este diagnóstico." -ForegroundColor Red
    exit 1
}
Write-Host "✔ Todo en orden. Abre http://localhost:$pFront" -ForegroundColor Green
exit 0
