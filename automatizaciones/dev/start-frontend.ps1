<#
Arranca el frontend del Producto Tavo en desarrollo, siempre en el MISMO
puerto (5175; el 5173 es del Producto JS, que corre a la vez en esta máquina).

vite.config.js tiene strictPort: true, así que si el 5175 está ocupado Vite
falla en vez de saltar al siguiente puerto en silencio. Este script cierra
antes el Vite viejo de ESTE producto: el que lleva la ruta de esta carpeta en
su línea de comando o escucha en el 5175. Nunca "todo node con vite", que
tumbaría el frontend del Producto JS.

Uso (Windows PowerShell 5.1 o PowerShell 7):
    powershell -ExecutionPolicy Bypass -File automatizaciones/dev/start-frontend.ps1
#>

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$frontend = Join-Path $raiz "frontend"
. (Join-Path $PSScriptRoot "comun.ps1")
$PUERTO = $MAPA_PUERTOS.frontend.Puerto

Write-Host "==> Cerrando el Vite viejo de este producto" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like "*vite*" -and $_.CommandLine -like "*$frontend*" } |
    ForEach-Object {
        Write-Host "    cerrando $(Get-DescripcionProceso $_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
foreach ($id in (Get-Ocupantes $PUERTO)) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if ($p -and $p.Name -eq "node.exe") {
        Write-Host "    cerrando $(Get-DescripcionProceso $id)"
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "verificar-puertos.ps1") -Servicios frontend
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "==> Frontend en http://localhost:$PUERTO" -ForegroundColor Green
Push-Location $frontend
try {
    npm run dev
} finally {
    Pop-Location
}
