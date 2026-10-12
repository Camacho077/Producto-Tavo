<#
Arranca el backend en desarrollo, siempre en el MISMO puerto (8001).

Por qué 8001 y no 8000: en esta máquina el 8000 quedó inutilizable
(WinError 10013 / bindings fantasma de Windows-Hyper-V). El puerto del
backend es fijo y explícito a propósito: cuando el puerto cambia sin
avisar, el frontend sigue llamando al viejo y el error aparece como un
fallo de CORS que no tiene nada que ver con la configuración de CORS.

Antes de arrancar, cierra cualquier uvicorn viejo de ESTE proyecto, que es
la causa de haber terminado con dos backends vivos a la vez.

Uso (Windows PowerShell 5.1 o PowerShell 7):
    powershell -ExecutionPolicy Bypass -File automatizaciones/dev/start-backend.ps1
#>

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backend = Join-Path $raiz "backend"

Write-Host "==> Activando el entorno virtual (backend\venv)" -ForegroundColor Cyan
$activar = Join-Path $backend "venv\Scripts\Activate.ps1"
if (-not (Test-Path $activar)) {
    Write-Host "✘ No existe backend\venv. Corre primero automatizaciones\setup.ps1." -ForegroundColor Red
    exit 1
}
. $activar

# El puerto sale de la configuración del backend (PORT en backend/.env,
# 8001 por defecto en app/core/config.py): un solo lugar manda.
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

Write-Host "==> Cerrando instancias viejas de uvicorn de este proyecto" -ForegroundColor Cyan
# 1) Reloaders de uvicorn (su línea de comando dice uvicorn app.main).
# 2) Workers huérfanos: uvicorn --reload arranca el servidor real como hijo
#    "multiprocessing.spawn" (su línea de comando NO dice uvicorn). Si el
#    reloader muere, el worker queda vivo con el puerto tomado y el nuevo
#    backend no puede arrancar. Pasó el 2026-09-16: había dos workers zombi
#    sirviendo código viejo en el 8001.
# 3) Cualquier otro proceso que tenga el puerto en LISTEN.
$pids = @()
$pids += Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*app.main*" -or $_.CommandLine -like "*multiprocessing.spawn*" } |
    Select-Object -ExpandProperty ProcessId
$pids += Get-NetTCPConnection -LocalPort $PUERTO -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess
$pids | Sort-Object -Unique | Where-Object { $_ -and $_ -ne $PID } | ForEach-Object {
    Write-Host "    cerrando PID $_"
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
}

# Esperar a que el puerto quede libre de verdad (hasta 10 s).
for ($i = 0; $i -lt 20; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort $PUERTO -State Listen -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 500
}

$ocupado = Get-NetTCPConnection -LocalPort $PUERTO -State Listen -ErrorAction SilentlyContinue
if ($ocupado) {
    Write-Host "✘ El puerto $PUERTO sigue ocupado por el PID $($ocupado.OwningProcess)." -ForegroundColor Red
    Write-Host "  Ciérralo antes de continuar (Stop-Process -Id $($ocupado.OwningProcess) -Force)." -ForegroundColor Red
    exit 1
}

# Libre no basta: Windows puede tener el puerto dentro de un rango reservado
# (Hyper-V/WSL) y entonces nadie escucha pero tampoco se puede abrir
# (WinError 10013). Se prueba abriéndolo de verdad un instante.
try {
    $prueba = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $PUERTO)
    $prueba.Start()
    $prueba.Stop()
} catch {
    Write-Host "✘ Windows no deja abrir el puerto $PUERTO (¿rango reservado?)." -ForegroundColor Red
    Write-Host "  Revisa: netsh interface ipv4 show excludedportrange protocol=tcp" -ForegroundColor Red
    Write-Host "  Arreglo (PowerShell como administrador): net stop winnat; net start winnat" -ForegroundColor Red
    exit 1
}

Write-Host "==> Backend en http://localhost:$PUERTO (docs: http://localhost:$PUERTO/docs)" -ForegroundColor Green
Push-Location $backend
try {
    & python -m uvicorn app.main:app --port $PUERTO --reload
} finally {
    Pop-Location
}
