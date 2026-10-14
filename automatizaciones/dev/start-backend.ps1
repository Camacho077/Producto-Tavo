<#
Arranca el backend del Producto Tavo en desarrollo, siempre en el MISMO
puerto (8002, PORT en backend/.env).

Por qué 8002: el 8001 es del Producto JS, que corre a la vez en esta máquina,
y el 8000 quedó inutilizable en Windows (WinError 10013 / rangos reservados
por Hyper-V). Cuando el puerto cambia sin avisar, el frontend sigue llamando
al viejo y el error aparece como un fallo de CORS que no tiene nada que ver
con la configuración de CORS. Mapa completo: docs/DECISIONES.md §1.

Antes de arrancar cierra el backend viejo de ESTE producto (lo que escuche en
el 8002, con su reloader y sus workers) y nada más: nunca "todo python con
uvicorn", que tumbaría el backend del Producto JS.

Uso (Windows PowerShell 5.1 o PowerShell 7):
    powershell -ExecutionPolicy Bypass -File automatizaciones/dev/start-backend.ps1
#>

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backend = Join-Path $raiz "backend"
. (Join-Path $PSScriptRoot "comun.ps1")

Write-Host "==> Activando el entorno virtual (backend\venv)" -ForegroundColor Cyan
$activar = Join-Path $backend "venv\Scripts\Activate.ps1"
if (-not (Test-Path $activar)) {
    Write-Host "✘ No existe backend\venv. Corre primero automatizaciones\setup.ps1." -ForegroundColor Red
    exit 1
}
. $activar

# El puerto sale de la configuración del backend (PORT en backend/.env,
# 8002 por defecto en app/core/config.py): un solo lugar manda.
Push-Location $backend
try {
    $PUERTO = [int](& python -c "from app.core.config import settings; print(settings.PORT)")
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0 -or -not $PUERTO) {
    Write-Host "✘ No se pudo leer la configuración del backend (mensaje arriba)." -ForegroundColor Red
    exit 1
}
Write-Host "    puerto configurado: $PUERTO"
# El frontend debe llamar a ESTE puerto (VITE_API_URL en frontend/.env). En
# una máquina donde el 8002 no se puede usar, el setup elige otro y escribe
# los dos archivos (automatizaciones/dev/puertos.py).
$envFrontend = Join-Path $raiz "frontend\.env"
$apiFrontend = if (Test-Path $envFrontend) { ((Get-Content $envFrontend -Encoding UTF8 | Select-String "^VITE_API_URL=").Line -replace "^VITE_API_URL=", "") } else { "" }
if ($apiFrontend -and $apiFrontend -notmatch ":$PUERTO/") {
    Write-Host "  ! El frontend llama a $apiFrontend pero el backend usará el ${PUERTO}: el login dará ERR_CONNECTION_REFUSED." -ForegroundColor Yellow
    Write-Host "    Arreglo: corre automatizaciones\setup.ps1 (alinea backend/.env y frontend/.env) y reinicia el frontend." -ForegroundColor Yellow
}

Write-Host "==> Cerrando el backend viejo de este producto (solo el que escucha en el $PUERTO)" -ForegroundColor Cyan
$ajenos = Stop-BackendEnPuerto $PUERTO
if ($ajenos.Count) {
    $contenedor = Get-ContenedorEnPuerto $PUERTO
    if ($contenedor -eq $MAPA_PUERTOS.backend.Contenedor) {
        Write-Host "✘ El backend ya corre en Docker ($contenedor) en el $PUERTO." -ForegroundColor Red
        Write-Host "  Úsalo tal cual, o detenlo para desarrollar con recarga:" -ForegroundColor Red
        Write-Host "    docker compose -f infra/docker-compose.yml stop backend" -ForegroundColor Red
        exit 1
    }
}

# Esperar a que el puerto quede libre de verdad (hasta 10 s).
for ($i = 0; $i -lt 20; $i++) {
    if (-not (Get-Ocupantes $PUERTO)) { break }
    Start-Sleep -Milliseconds 500
}

# Libre, no reservado por Windows, y si no, quién lo tiene.
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "verificar-puertos.ps1") -Servicios backend
if ($LASTEXITCODE -ne 0) { exit 1 }

# Libre no basta: se prueba abrirlo de verdad un instante (Windows puede
# negarlo aunque no aparezca en la lista de rangos reservados).
try {
    $prueba = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $PUERTO)
    $prueba.Start()
    $prueba.Stop()
} catch {
    Write-Host "✘ Windows no deja abrir el puerto $PUERTO (¿rango reservado?)." -ForegroundColor Red
    Write-Host "  Revisa: netsh interface ipv4 show excludedportrange protocol=tcp" -ForegroundColor Red
    Write-Host "  Arreglo: corre automatizaciones\setup.ps1, que elige otro puerto libre y actualiza los .env;" -ForegroundColor Red
    Write-Host "  o libera las reservas (PowerShell como administrador): net stop winnat; net start winnat" -ForegroundColor Red
    exit 1
}

Write-Host "==> Backend en http://localhost:$PUERTO (docs: http://localhost:$PUERTO/docs)" -ForegroundColor Green
Push-Location $backend
try {
    & python -m uvicorn app.main:app --port $PUERTO --reload
} finally {
    Pop-Location
}
