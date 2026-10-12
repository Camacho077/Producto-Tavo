<#
Revisa los puertos del Producto Tavo ANTES de arrancar y dice, para cada uno,
si está libre, si Windows lo tiene reservado o quién lo ocupa.

Mapa (docs/DECISIONES.md §1; ninguno se repite con el Producto JS):
    frontend 5175 · preview 4175 · backend 8002 · postgres 5433 · n8n 5679

Uso (Windows PowerShell 5.1 o PowerShell 7):
    powershell -ExecutionPolicy Bypass -File automatizaciones/dev/verificar-puertos.ps1
    ... verificar-puertos.ps1 -Servicios backend,frontend   # solo esos
    ... verificar-puertos.ps1 -PermitirPropios              # un contenedor tavo-* en su
                                                            # puerto cuenta como bien

Sale con código 0 si todo está libre (o en manos de su propio contenedor con
-PermitirPropios) y 1 si algún puerto está reservado u ocupado por otro.
#>
[CmdletBinding()]
param(
    # Con `powershell -File`, "backend,frontend" llega como UNA cadena: se
    # separa a mano (ValidateSet la rechazaba entera).
    [string[]] $Servicios = @("frontend", "preview", "backend", "postgres", "n8n"),
    [switch] $PermitirPropios
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
. (Join-Path $PSScriptRoot "comun.ps1")

$Servicios = @($Servicios | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$desconocidos = @($Servicios | Where-Object { -not $MAPA_PUERTOS.Contains($_) })
if ($desconocidos.Count) {
    Write-Host "✘ Servicio desconocido: $($desconocidos -join ', '). Usa: $($MAPA_PUERTOS.Keys -join ', ')." -ForegroundColor Red
    exit 1
}

$rangos = Get-RangosReservados
$problemas = 0

Write-Host "==> Puertos del Producto Tavo" -ForegroundColor Cyan
foreach ($servicio in $Servicios) {
    $dato = $MAPA_PUERTOS[$servicio]
    $puerto = $dato.Puerto
    $etiqueta = "{0,-9} {1,5}  {2}" -f $servicio, $puerto, $dato.Que

    $rango = $rangos | Where-Object { $_[0] -le $puerto -and $puerto -le $_[1] } | Select-Object -First 1
    if ($rango) {
        $problemas++
        Write-Host "  ✘ $etiqueta" -ForegroundColor Red
        Write-Host "      RESERVADO por Windows (rango $($rango[0])-$($rango[1])): nadie escucha, pero no se puede abrir (WinError 10013)." -ForegroundColor Red
        Write-Host "      Arreglo (PowerShell como administrador): net stop winnat; net start winnat" -ForegroundColor Red
        continue
    }

    $ocupantes = Get-Ocupantes $puerto
    if (-not $ocupantes) {
        Write-Host "  ✔ $etiqueta — libre" -ForegroundColor Green
        continue
    }

    $contenedor = Get-ContenedorEnPuerto $puerto
    if ($contenedor -and $PermitirPropios -and $contenedor -eq $dato.Contenedor) {
        Write-Host "  ✔ $etiqueta — en uso por su contenedor $contenedor (de este producto)" -ForegroundColor Green
        continue
    }

    $problemas++
    Write-Host "  ✘ $etiqueta — OCUPADO" -ForegroundColor Red
    if ($contenedor) {
        Write-Host "      lo publica el contenedor Docker '$contenedor'" -ForegroundColor Red
        if ($contenedor -like "tavo-*") {
            Write-Host "      (es de este producto: docker compose -f infra/docker-compose.yml stop $($contenedor -replace '^tavo-', ''))" -ForegroundColor Red
        } else {
            Write-Host "      (NO es de este producto: revisa qué proyecto de Docker publica el $puerto)" -ForegroundColor Red
        }
    }
    foreach ($id in $ocupantes) {
        Write-Host "      $(Get-DescripcionProceso $id)" -ForegroundColor Red
    }
    Write-Host "      Para cerrarlo: Stop-Process -Id $($ocupantes[0]) -Force   (verifica antes que no sea del Producto JS)" -ForegroundColor Red
}

if ($problemas) {
    Write-Host "✘ $problemas puerto(s) con problema. Nada se arrancó." -ForegroundColor Red
    exit 1
}
Write-Host "✔ Puertos listos." -ForegroundColor Green
exit 0
