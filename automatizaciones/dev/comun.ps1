<#
Piezas compartidas por los scripts de arranque del Producto Tavo
(se cargan con:  . "$PSScriptRoot\comun.ps1").

CONFIGURACIÓN CRÍTICA — NO se borra en limpiezas. Este equipo corre a la vez
el Producto JS (5173 / 4173 / 8001 / 5432). Por eso:

  * El mapa de puertos vive AQUÍ para los scripts, y debe coincidir con
    vite.config.js, backend/.env.example, infra/docker-compose.yml y
    .claude/launch.json (lo comprueba backend/tests/test_mapa_de_puertos.py).
  * Los scripts NUNCA cierran procesos "por nombre" (todo python con uvicorn,
    todo node con vite): eso tumbaría el otro producto. Solo se cierra lo que
    escucha en un puerto de ESTE producto, o lo que lleva la ruta de esta
    carpeta en su línea de comando.
#>

$script:MAPA_PUERTOS = [ordered]@{
    frontend = @{ Puerto = 5175; Que = "Frontend (Vite dev)"; Contenedor = "tavo-frontend" }
    preview  = @{ Puerto = 4175; Que = "Vista previa compilada (vite preview)"; Contenedor = $null }
    backend  = @{ Puerto = 8002; Que = "Backend (FastAPI)"; Contenedor = "tavo-backend" }
    postgres = @{ Puerto = 5433; Que = "Postgres (Docker, tavo-db)"; Contenedor = "tavo-db" }
    n8n      = @{ Puerto = 5679; Que = "n8n (Docker, tavo-n8n)"; Contenedor = "tavo-n8n" }
}

function Get-Ocupantes([int] $puerto) {
    @(Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Get-DescripcionProceso([int] $id) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if (-not $p) { return "PID $id (proceso ya terminado)" }
    $linea = "$($p.CommandLine)"
    if ($linea.Length -gt 140) { $linea = $linea.Substring(0, 140) + "…" }
    return "PID $id $($p.Name) — $linea"
}

# Rangos que Windows (Hyper-V / WSL / Docker) se reserva: nadie escucha en
# ellos, pero tampoco se pueden abrir (WinError 10013). Pasó con el 8000.
function Get-RangosReservados {
    $salida = & netsh interface ipv4 show excludedportrange protocol=tcp 2>$null
    $rangos = @()
    foreach ($linea in $salida) {
        if ($linea -match '^\s*(\d+)\s+(\d+)') { $rangos += , @([int]$Matches[1], [int]$Matches[2]) }
    }
    return , $rangos
}

# Contenedor de Docker que publica el puerto (o $null).
function Get-ContenedorEnPuerto([int] $puerto) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $null }
    $nombre = & docker ps --filter "publish=$puerto" --format "{{.Names}}" 2>$null | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) { return $null }
    return $nombre
}

# Cierra el backend de desarrollo que escucha en $puerto (y SOLO ese):
# el proceso dueño del puerto, sus ancestros python (el reloader de
# --reload y el lanzador del venv) y los workers `multiprocessing.spawn`
# hijos suyos (su línea dice parent_pid=<pid>), incluso si el reloader ya
# murió y Windows sigue reportándolo como dueño del puerto (pasó el
# 2026-09-16: workers zombi sirviendo código viejo). Devuelve los dueños
# que NO son python (Docker, otro programa): esos no se tocan.
function Stop-BackendEnPuerto([int] $puerto) {
    $ajenos = @()
    $procesos = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    foreach ($duenio in (Get-Ocupantes $puerto)) {
        $p = $procesos | Where-Object ProcessId -eq $duenio
        if ($p -and $p.Name -notlike "python*") { $ajenos += $duenio; continue }
        $familia = @($duenio)
        $familia += $procesos | Where-Object { $_.Name -like "python*" -and $_.CommandLine -match "parent_pid=$duenio\b" } |
            Select-Object -ExpandProperty ProcessId
        $actual = $p
        while ($actual) {
            $padre = $procesos | Where-Object ProcessId -eq $actual.ParentProcessId
            if (-not $padre -or $padre.Name -notlike "python*") { break }
            $familia += $padre.ProcessId
            $actual = $padre
        }
        foreach ($id in ($familia | Sort-Object -Unique)) {
            Write-Host "    cerrando $(Get-DescripcionProceso $id)"
            & taskkill.exe /PID $id /T /F 2>$null | Out-Null
        }
    }
    return , $ajenos
}
