<#
Arranca el frontend en desarrollo, siempre en el MISMO puerto (5173).

vite.config.js tiene strictPort: true, así que si el 5173 está ocupado Vite
falla en vez de saltar a 5174 en silencio. Este script cierra primero las
instancias viejas de Vite de ESTE proyecto para que eso no pase.

Uso (Windows PowerShell 5.1 o PowerShell 7):
    powershell -ExecutionPolicy Bypass -File automatizaciones/dev/start-frontend.ps1
#>

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$frontend = Join-Path $raiz "frontend"
$PUERTO = 5173

Write-Host "==> Cerrando instancias viejas de Vite de este proyecto" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like "*vite*" } |
    ForEach-Object {
        Write-Host "    cerrando PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Seconds 1

$ocupado = Get-NetTCPConnection -LocalPort $PUERTO -State Listen -ErrorAction SilentlyContinue
if ($ocupado) {
    Write-Host "✘ El puerto $PUERTO sigue ocupado por el PID $($ocupado.OwningProcess)." -ForegroundColor Red
    Write-Host "  Ciérralo antes de continuar (Stop-Process -Id $($ocupado.OwningProcess) -Force)." -ForegroundColor Red
    exit 1
}

Write-Host "==> Frontend en http://localhost:$PUERTO" -ForegroundColor Green
Push-Location $frontend
try {
    npm run dev
} finally {
    Pop-Location
}
