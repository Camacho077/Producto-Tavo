#requires -version 7
<#
Levanta TODA la demo compartible por internet con un solo comando:

  1. valida herramientas y que los puertos 8002 (backend) y 4175 (preview)
     estén libres;
  2. arranca el backend (uvicorn, sin --reload) en 8002;
  3. abre el túnel del backend y obtiene su URL pública;
  4. escribe frontend/.env.tunnel con esa URL y COMPILA el frontend en modo
     `tunnel` (VITE_API_URL queda incrustado en el paquete, por eso se
     compila después de conocer la URL);
  5. sirve la versión compilada con `vite preview` en 4175 (tipos MIME
     correctos; el servidor de desarrollo NO se expone: sirve cientos de
     .jsx sueltos, el túnel les pone text/plain y el navegador los bloquea);
  6. abre el túnel del frontend, comprueba por HTTP que los .js llegan con
     tipo MIME de JavaScript y que el backend responde por su túnel;
  7. imprime las dos URLs públicas e indica cuál compartir.

Queda corriendo hasta Ctrl+C; al salir cierra todo lo que levantó. Todo
depende de que ESTE computador siga prendido y conectado.

Uso:
    pwsh automatizaciones/demo/start-demo-tunel.ps1
    pwsh automatizaciones/demo/start-demo-tunel.ps1 -Forzar        # cierra lo que ocupe 8002/4175
    pwsh automatizaciones/demo/start-demo-tunel.ps1 -Tunel cloudflared
    pwsh automatizaciones/demo/start-demo-tunel.ps1 -SoloProbar   # prueba el flujo y cierra

Túnel: `localtunnel` (por defecto, vía npx, sin cuenta) o `cloudflared`
(si está instalado; sin página intermedia). Con localtunnel, el navegador
del invitado ve UNA página de aviso la primera vez y debe escribir la
"contraseña del túnel" (la IP pública de este equipo), que este script
imprime al final. Las llamadas del frontend a la API la saltan solas con
el header bypass-tunnel-reminder (ver frontend/src/lib/api.js).

Puertos: 5175 (desarrollo) y 8002 (backend) siguen siendo los fijos del
proyecto; 4175 es ADICIONAL para el preview compilado, no un reemplazo.
#>
[CmdletBinding()]
param(
    [switch] $Forzar,
    [ValidateSet("auto", "localtunnel", "cloudflared")] [string] $Tunel = "auto",
    [int] $EsperaTunelSeg = 45,
    # Solo para verificación automatizada: hace todo el flujo y las
    # comprobaciones y cierra, sin quedarse esperando Ctrl+C.
    [switch] $SoloProbar
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backend = Join-Path $raiz "backend"
$frontend = Join-Path $raiz "frontend"
$logs = Join-Path $raiz "automatizaciones\demo\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

. (Join-Path $raiz "automatizaciones\dev\comun.ps1")
$PUERTO_BACKEND = $MAPA_PUERTOS.backend.Puerto
$PUERTO_PREVIEW = $MAPA_PUERTOS.preview.Puerto
$procesos = @()
$codigoSalida = 0

# Lanza una excepción: el bloque principal la atrapa, la imprime en rojo,
# cierra lo que haya levantado y termina con código 1.
function Fallar($mensaje) { throw "✘ $mensaje" }

function Paso($texto) { Write-Host "==> $texto" -ForegroundColor Cyan }

function Ocupante($puerto) {
    Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

function ValidarPuerto($puerto, $nombre) {
    $c = Ocupante $puerto
    if (-not $c) { return }
    $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($Forzar) {
        Write-Host "    puerto $puerto ($nombre) ocupado por PID $($c.OwningProcess) ($($proc.ProcessName)); cerrando por -Forzar"
        # Solo se cierra lo que escucha en ESTE puerto (del mapa del Producto
        # Tavo). En el backend, con su reloader y sus workers
        # (Stop-BackendEnPuerto, automatizaciones/dev/comun.ps1): nunca "todo
        # python con uvicorn", que tumbaría el backend del Producto JS.
        for ($i = 0; $i -lt 20 -and (Ocupante $puerto); $i++) {
            if ($puerto -eq $PUERTO_BACKEND) {
                Stop-BackendEnPuerto $puerto | Out-Null
            } else {
                Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue |
                    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
            }
            Start-Sleep -Milliseconds 500
        }
        if (Ocupante $puerto) { Fallar "El puerto $puerto sigue ocupado tras intentar cerrarlo." }
    } else {
        Fallar "El puerto $puerto ($nombre) está ocupado por el PID $($c.OwningProcess) ($($proc.ProcessName)). Ciérralo o vuelve a correr con -Forzar."
    }
}

# Arranca un proceso en segundo plano con su salida en un log y lo registra para cerrarlo al final.
function Lanzar($nombre, $comando, $directorio) {
    $out = Join-Path $logs "$nombre.out.log"
    $err = Join-Path $logs "$nombre.err.log"
    Remove-Item $out, $err -ErrorAction SilentlyContinue
    # Comillas dobles envolventes: cmd /c quita el primer y el último par de
    # comillas, así los ejecutables con espacios en la ruta ("Producto JS")
    # llegan intactos.
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$comando`"" -WorkingDirectory $directorio -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err
    $script:procesos += [pscustomobject]@{ Nombre = $nombre; Proceso = $p; Out = $out; Err = $err }
    return $p
}

function EsperarUrlDeTunel($nombre, $patron, $segundos) {
    $entrada = $script:procesos | Where-Object Nombre -eq $nombre
    $limite = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $limite) {
        $texto = (Get-Content $entrada.Out, $entrada.Err -Raw -ErrorAction SilentlyContinue) -join "`n"
        if ($texto -match $patron) { return $Matches[1].TrimEnd("/") }
        if ($entrada.Proceso.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    $texto = (Get-Content $entrada.Out, $entrada.Err -Raw -ErrorAction SilentlyContinue) -join "`n"
    Fallar "No se obtuvo la URL pública del túnel '$nombre' en $segundos s. Salida del túnel:`n$texto"
}

function EsperarPuerto($puerto, $nombre, $segundos = 40) {
    $limite = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $limite) {
        if (Ocupante $puerto) { return }
        Start-Sleep -Milliseconds 500
    }
    $entrada = $script:procesos | Where-Object Nombre -eq $nombre
    $texto = (Get-Content $entrada.Out, $entrada.Err -Raw -ErrorAction SilentlyContinue) -join "`n"
    Fallar "$nombre no empezó a escuchar en el puerto $puerto en $segundos s. Log:`n$texto"
}

function Cerrar {
    Write-Host ""
    Paso "Cerrando la demo"
    foreach ($e in ($script:procesos | Sort-Object -Descending { $_.Proceso.Id })) {
        if (-not $e.Proceso.HasExited) {
            # cmd.exe lanzó hijos (node/python): se cierra el árbol completo.
            & taskkill.exe /PID $e.Proceso.Id /T /F 2>$null | Out-Null
            Write-Host "    cerrado $($e.Nombre)"
        }
    }
    # Por si algún hijo sobrevivió al cierre del árbol (npx relanza node):
    # se cierran los túneles y el preview de ESTE proyecto por su comando.
    # El preview se reconoce por la RUTA de este frontend: un `vite preview`
    # a secas también sería el del Producto JS, que corre a la vez.
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -match "localtunnel.*--port (8002|4175)" -or ($_.CommandLine -like "*vite*preview*" -and $_.CommandLine -like "*$frontend*") } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

try {
    # ------------------------------------------------------------------ 1. validaciones
    Paso "Validando herramientas y puertos"
    foreach ($h in "node", "npm", "npx") {
        if (-not (Get-Command $h -ErrorAction SilentlyContinue)) { Fallar "No se encontró '$h' en el PATH. Instala Node.js." }
    }
    $python = Join-Path $backend "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { Fallar "No existe backend\venv. Crea el entorno virtual e instala requirements.txt (ver README)." }
    if (-not (Test-Path (Join-Path $backend ".env"))) { Fallar "Falta backend\.env (copia backend\.env.example)." }
    $env_backend = Get-Content (Join-Path $backend ".env") -Raw
    if ($env_backend -notmatch "(?m)^ENV=development") {
        Fallar "backend\.env debe tener ENV=development: solo en desarrollo el CORS acepta los dominios de túnel (app/core/cors.py)."
    }
    if ($Tunel -eq "auto") { $Tunel = if (Get-Command cloudflared -ErrorAction SilentlyContinue) { "cloudflared" } else { "localtunnel" } }
    if ($Tunel -eq "cloudflared" -and -not (Get-Command cloudflared -ErrorAction SilentlyContinue)) { Fallar "cloudflared no está instalado (winget install Cloudflare.cloudflared) o usa -Tunel localtunnel." }
    Write-Host "    túnel: $Tunel"
    ValidarPuerto $PUERTO_BACKEND "backend"
    ValidarPuerto $PUERTO_PREVIEW "preview"
    Write-Host "    puertos $PUERTO_BACKEND y $PUERTO_PREVIEW libres"

    # ------------------------------------------------------------------ 2. backend
    Paso "Arrancando el backend en http://localhost:$PUERTO_BACKEND (sin --reload)"
    Lanzar "backend" "`"$python`" -m uvicorn app.main:app --host 127.0.0.1 --port $PUERTO_BACKEND" $backend | Out-Null
    EsperarPuerto $PUERTO_BACKEND "backend"
    $salud = Invoke-RestMethod "http://localhost:$PUERTO_BACKEND/health" -TimeoutSec 10
    Write-Host "    /health -> $($salud | ConvertTo-Json -Compress)"

    # ------------------------------------------------------------------ 3. túnel del backend
    Paso "Abriendo el túnel del backend"
    function ComandoTunel($puerto) {
        if ($Tunel -eq "cloudflared") { return "cloudflared tunnel --url http://localhost:$puerto --no-autoupdate" }
        return "npx --yes localtunnel --port $puerto"
    }
    $patronUrl = if ($Tunel -eq "cloudflared") { "(https://[a-z0-9-]+\.trycloudflare\.com)" } else { "your url is: (https://[a-z0-9-]+\.loca\.lt)" }
    Lanzar "tunel-backend" (ComandoTunel $PUERTO_BACKEND) $raiz | Out-Null
    $urlBackend = EsperarUrlDeTunel "tunel-backend" $patronUrl $EsperaTunelSeg
    Write-Host "    backend público: $urlBackend"

    # ------------------------------------------------------------------ 4. compilar el frontend con la URL pública
    Paso "Compilando el frontend en modo 'tunnel' (VITE_API_URL=$urlBackend/api/v1)"
    @(
        "# Generado por automatizaciones/demo/start-demo-tunel.ps1 el $(Get-Date -Format 'yyyy-MM-dd HH:mm'). No editar a mano."
        "# La URL cambia en cada demo: se vuelve a generar cada vez que corre el script."
        "VITE_API_URL=$urlBackend/api/v1"
    ) | Set-Content (Join-Path $frontend ".env.tunnel") -Encoding utf8
    $logBuild = Join-Path $logs "build.log"
    Push-Location $frontend
    try {
        & cmd.exe /c "npx vite build --mode tunnel > `"$logBuild`" 2>&1"
        $codigo = $LASTEXITCODE
    } finally { Pop-Location }
    Get-Content $logBuild -Tail 3 | ForEach-Object { Write-Host "    $_" }
    if ($codigo -ne 0) { Fallar "La compilación del frontend falló (ver $logBuild)." }
    $js = Get-ChildItem (Join-Path $frontend "dist\assets") -Filter "index-*.js" | Select-Object -First 1
    if (-not $js) { Fallar "No se encontró dist/assets/index-*.js tras compilar." }
    if (-not (Select-String -Path $js.FullName -Pattern ([regex]::Escape("$urlBackend/api/v1")) -Quiet)) {
        Fallar "El paquete compilado NO contiene la URL pública del backend; contiene otra VITE_API_URL."
    }
    Write-Host "    paquete: $($js.Name) (contiene $urlBackend/api/v1)"

    # ------------------------------------------------------------------ 5. preview
    Paso "Sirviendo la versión compilada con vite preview en http://localhost:$PUERTO_PREVIEW"
    Lanzar "preview" "npx vite preview --host --port $PUERTO_PREVIEW --strictPort" $frontend | Out-Null
    EsperarPuerto $PUERTO_PREVIEW "preview"

    # ------------------------------------------------------------------ 6. túnel del frontend + comprobaciones
    Paso "Abriendo el túnel del frontend"
    Lanzar "tunel-frontend" (ComandoTunel $PUERTO_PREVIEW) $raiz | Out-Null
    $urlFrontend = EsperarUrlDeTunel "tunel-frontend" $patronUrl $EsperaTunelSeg
    Write-Host "    frontend público: $urlFrontend"

    Paso "Comprobando por el túnel que los archivos llegan bien"
    $cab = @{ "bypass-tunnel-reminder" = "1" }
    $html = Invoke-WebRequest "$urlFrontend/" -Headers $cab -TimeoutSec 30
    $tipoHtml = $html.Headers["Content-Type"]
    $rutaJs = [regex]::Match($html.Content, 'src="(/assets/index-[^"]+\.js)"').Groups[1].Value
    if (-not $rutaJs) { Fallar "El index.html público no referencia /assets/index-*.js. ¿Se está sirviendo otra cosa? Content-Type: $tipoHtml" }
    $rjs = Invoke-WebRequest "$urlFrontend$rutaJs" -Headers $cab -TimeoutSec 30
    $tipoJs = "$($rjs.Headers['Content-Type'])"
    Write-Host "    GET $urlFrontend/          -> $($html.StatusCode) $tipoHtml"
    Write-Host "    GET $urlFrontend$rutaJs -> $($rjs.StatusCode) $tipoJs ($([math]::Round($rjs.RawContentLength / 1024)) KB)"
    if ($tipoJs -notmatch "^(application|text)/javascript") { Fallar "El JavaScript NO llega con tipo MIME de JavaScript sino '$tipoJs': el navegador lo bloqueará." }
    $rs = Invoke-WebRequest "$urlBackend/health" -Headers $cab -TimeoutSec 30
    Write-Host "    GET $urlBackend/health -> $($rs.StatusCode) $($rs.Content)"
    $pre = Invoke-WebRequest "$urlBackend/api/v1/seguridad/login" -Method Options -Headers @{ Origin = $urlFrontend; "Access-Control-Request-Method" = "POST"; "Access-Control-Request-Headers" = "content-type,bypass-tunnel-reminder"; "bypass-tunnel-reminder" = "1" } -TimeoutSec 30
    $acao = "$($pre.Headers['Access-Control-Allow-Origin'])"
    Write-Host "    OPTIONS $urlBackend/api/v1/seguridad/login (Origin: $urlFrontend) -> $($pre.StatusCode) Access-Control-Allow-Origin: $acao"
    if ($acao -ne $urlFrontend) { Fallar "El backend no acepta por CORS el origen del frontend público. Revisa ENV=development y app/core/cors.py." }

    $claveTunel = $null
    if ($Tunel -eq "localtunnel") { try { $claveTunel = (Invoke-RestMethod "https://loca.lt/mytunnelpassword" -TimeoutSec 15).Trim() } catch { $claveTunel = "(no se pudo obtener; consulta https://loca.lt/mytunnelpassword)" } }

    # ------------------------------------------------------------------ 7. resumen
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  DEMO LISTA" -ForegroundColor Green
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  COMPARTE ESTA URL (la aplicación):   $urlFrontend" -ForegroundColor Green
    Write-Host "  Backend público (NO compartir; ya va incrustado en la app): $urlBackend"
    if ($claveTunel) {
        Write-Host ""
        Write-Host "  localtunnel muestra una página de aviso la primera vez que alguien abre" -ForegroundColor Yellow
        Write-Host "  la URL. Debe escribir esta contraseña del túnel (tu IP pública): $claveTunel" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  Debe quedar encendido mientras dure la demo: este script (Ctrl+C la termina),"
    Write-Host "  el backend en :$PUERTO_BACKEND, el preview en :$PUERTO_PREVIEW y los dos túneles. Las URLs"
    Write-Host "  cambian en cada arranque: vuelve a compartir la nueva. Si este computador"
    Write-Host "  se apaga, se suspende o pierde internet, la demo deja de funcionar."
    Write-Host "  Logs: $logs"
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green

    if ($SoloProbar) { Write-Host "  (-SoloProbar: flujo verificado; cerrando)"; return }

    # ------------------------------------------------------------------ vigilancia
    while ($true) {
        Start-Sleep -Seconds 5
        foreach ($e in $procesos) {
            if ($e.Proceso.HasExited) {
                $texto = (Get-Content $e.Out, $e.Err -Raw -ErrorAction SilentlyContinue) -join "`n"
                Fallar "'$($e.Nombre)' se cerró solo (código $($e.Proceso.ExitCode)). Últimas líneas:`n$(($texto -split "`n" | Select-Object -Last 15) -join "`n")"
            }
        }
    }
} catch {
    Write-Host ""
    Write-Host "$($_.Exception.Message)" -ForegroundColor Red
    $codigoSalida = 1
} finally {
    Cerrar
}
exit ($codigoSalida ?? 0)
