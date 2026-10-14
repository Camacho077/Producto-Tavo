#!/usr/bin/env bash
# =============================================================================
# Deja el Producto Tavo funcionando en una máquina nueva (Linux, macOS o Git
# Bash en Windows) y lo COMPRUEBA. Equivalente a automatizaciones/setup.ps1:
# solo dice "Listo" si el backend responde y el login de la demo entra.
#
# IDEMPOTENTE: se puede correr cuantas veces se quiera; lo hecho se salta.
#   1. Requisitos (Python 3.11+, Node 18+, Docker ENCENDIDO)
#   2. Copia los .env.example a .env si no existen (SECRET_KEY aleatoria)
#   3. Puertos: si el 8002 / 5433 / 5175 no se puede usar, elige el siguiente
#      libre y lo escribe en backend/.env, frontend/.env e infra/.env
#   4. backend/venv + dependencias, npm ci del frontend
#   5. Postgres en Docker (espera a que esté listo) y migraciones
#   6. Datos de demostración si la base está VACÍA (nunca en producción)
#   7. Backend y frontend en Docker (espera el healthcheck)
#   8. Comprueba /health, el login de admin@dondetavo.demo y el frontend
#
# Uso, desde la raíz del repositorio:
#   bash automatizaciones/setup.sh
# =============================================================================
set -euo pipefail
export PYTHONIOENCODING=utf-8

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$RAIZ/backend"
FRONTEND="$RAIZ/frontend"
COMPOSE="$RAIZ/infra/docker-compose.yml"

paso()  { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
bien()  { printf '    \033[32m[OK]\033[0m %s\n' "$1"; }
aviso() { printf '    \033[33m[!]\033[0m %s\n' "$1"; }
falla() {
  printf '\n    \033[31m[ERROR] %s\033[0m\n' "$1"
  [ -n "${2:-}" ] && printf '    \033[31m-> %s\033[0m\n' "$2"
  printf '    \033[31m-> Diagnóstico: python automatizaciones/dev/puertos.py --revisar ; docker compose -f infra/docker-compose.yml ps\033[0m\n\n'
  exit 1
}
dc() { docker compose -f "$COMPOSE" "$@"; }
logs() { printf '    --- últimas líneas de %s ---\n' "$1"; dc --profile frontend logs --tail 25 "$1" 2>&1 | sed 's/^/    /' || true; }
json() { $PYTHON -c "import json,sys; d=json.loads(sys.stdin.read().splitlines()[-1]); print(eval(sys.argv[1], {}, {'d': d}))" "$1"; }

# ---------------------------------------------------------------- 1. Requisitos
paso "1/8 Revisando requisitos"
PYTHON=""
for candidato in python3 python "py -3"; do
  if $candidato -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON="$candidato"; break
  fi
done
[ -n "$PYTHON" ] || falla "No se encontró Python 3.11 o superior." "Instálalo (https://www.python.org/downloads/) y abre una terminal nueva."
bien "Python $($PYTHON -c 'import platform; print(platform.python_version())')"

command -v node >/dev/null || falla "No se encontró Node.js." "Instala Node 20 LTS o superior (https://nodejs.org)."
node -e 'process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)' || falla "Node $(node --version) es muy viejo." "Instala Node 20 LTS o superior."
bien "Node $(node --version)"

command -v docker >/dev/null || falla "No se encontró Docker." "Instala Docker Desktop (https://www.docker.com/products/docker-desktop/), ábrelo y vuelve a correr este script."
docker info >/dev/null 2>&1 || falla "Docker está instalado pero no está encendido." "Abre Docker Desktop, espera 'Engine running' y vuelve a correr este script."
bien "Docker encendido"

# ---------------------------------------------------------------- 2. .env
paso "2/8 Archivos de configuración (.env)"
if [ -f "$BACKEND/.env" ]; then
  bien "backend/.env ya existe (se conserva)"
else
  CLAVE="$($PYTHON -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed "s|^SECRET_KEY=.*|SECRET_KEY=$CLAVE|" "$BACKEND/.env.example" > "$BACKEND/.env"
  bien "backend/.env creado desde .env.example (con SECRET_KEY aleatoria)"
fi
if [ -f "$FRONTEND/.env" ]; then
  bien "frontend/.env ya existe (se conserva)"
else
  cp "$FRONTEND/.env.example" "$FRONTEND/.env"
  bien "frontend/.env creado desde .env.example"
fi

# ---------------------------------------------------------------- 3. Puertos
paso "3/8 Puertos de esta máquina"
SALIDA="$($PYTHON "$RAIZ/automatizaciones/dev/puertos.py" --json)" || falla "No se pudieron elegir los puertos." "Revisa la salida de arriba."
printf '%s\n' "$SALIDA" | sed '$d' | sed 's/^/  /'
PROYECTO="$(printf '%s' "$SALIDA" | json "d['proyecto']")"
P_DB="$(printf '%s' "$SALIDA" | json "d['puertos']['db']")"
P_BACK="$(printf '%s' "$SALIDA" | json "d['puertos']['backend']")"
P_FRONT="$(printf '%s' "$SALIDA" | json "d['puertos']['frontend']")"
E_BACK="$(printf '%s' "$SALIDA" | json "d['estados']['backend']")"
E_FRONT="$(printf '%s' "$SALIDA" | json "d['estados']['frontend']")"
bien "Postgres $P_DB · backend $P_BACK · frontend $P_FRONT (proyecto Docker '$PROYECTO')"

# ---------------------------------------------------------------- 4. Dependencias
paso "4/8 Dependencias (Python y npm)"
[ -d "$BACKEND/venv" ] || { $PYTHON -m venv "$BACKEND/venv"; bien "backend/venv creado"; }
if [ -x "$BACKEND/venv/bin/python" ]; then PY="$BACKEND/venv/bin/python"; else PY="$BACKEND/venv/Scripts/python.exe"; fi
"$PY" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$PY" -m pip install --quiet --disable-pip-version-check -r "$BACKEND/requirements-dev.txt"
bien "Dependencias de Python instaladas"
( cd "$FRONTEND" && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund --loglevel=error; else npm install --no-audit --no-fund --loglevel=error; fi )
bien "Dependencias de npm instaladas"

# ---------------------------------------------------------------- 5. Postgres y migraciones
paso "5/8 Base de datos (Postgres en Docker) y migraciones"
dc up -d --wait --wait-timeout 120 db || { logs db; falla "Postgres no quedó listo." "¿El puerto $P_DB lo tomó otro programa?"; }
bien "Postgres listo en el puerto $P_DB"
cd "$BACKEND"
"$PY" "$RAIZ/automatizaciones/dev/preparar_base.py"
"$PY" -m alembic upgrade head
bien "Esquema al día"

# ---------------------------------------------------------------- 6. Datos demo
paso "6/8 Datos de demostración"
ESTADO="$("$PY" "$RAIZ/automatizaciones/dev/estado_base.py")"
ENV_ACTUAL="$(printf '%s' "$ESTADO" | json "d['env']")"
USUARIOS="$(printf '%s' "$ESTADO" | json "d['usuarios'] or 0")"
DEMO="$(printf '%s' "$ESTADO" | json "len(d['cuentas_demo'])")"
if [ "$ENV_ACTUAL" = "production" ]; then
  aviso "ENV=production: los datos de demostración NO se cargan."
elif [ "$USUARIOS" = "0" ]; then
  echo "    La base está vacía: cargo Donde Tavo y Café Central (unos 5 minutos)..."
  "$PY" "$RAIZ/automatizaciones/deploy/seed_demo.py"
  bien "Datos de demostración cargados"
elif [ "$DEMO" -lt 4 ]; then
  aviso "La base ya tiene datos pero faltan cuentas demo. No la toco."
  aviso "Para cargarlas: cd backend && $PY ../automatizaciones/deploy/seed_demo.py"
else
  bien "La base ya tiene datos y las 4 cuentas demo (no se recarga)"
fi
cd "$RAIZ"

# ---------------------------------------------------------------- 7. Backend y frontend
paso "7/8 Backend y frontend (Docker)"
SERVICIOS=()
if [ "$E_BACK" = "propio" ] && [ -z "$(docker ps --filter "name=^${PROYECTO}-backend\$" --format '{{.Names}}')" ]; then
  bien "Ya hay un backend de esta carpeta corriendo en el $P_BACK (lo uso tal cual)"
else SERVICIOS+=(backend); fi
if [ "$E_FRONT" = "propio" ] && [ -z "$(docker ps --filter "name=^${PROYECTO}-frontend\$" --format '{{.Names}}')" ]; then
  bien "Ya hay un frontend de esta carpeta corriendo en el $P_FRONT (lo uso tal cual)"
else SERVICIOS+=(frontend); fi
if [ ${#SERVICIOS[@]} -gt 0 ]; then
  echo "    Construyendo y arrancando: ${SERVICIOS[*]} (la primera vez tarda unos minutos)..."
  EXTRA=(); [[ " ${SERVICIOS[*]} " == *" backend "* ]] || EXTRA=(--no-deps)
  dc --profile frontend up -d --build --wait --wait-timeout 300 ${EXTRA[@]+"${EXTRA[@]}"} "${SERVICIOS[@]}" || {
    for s in "${SERVICIOS[@]}"; do logs "$s"; done
    falla "El backend o el frontend no quedaron arriba." "El motivo está en las líneas de arriba (el backend explica en español qué le falta)."
  }
  bien "Contenedores arriba: ${SERVICIOS[*]}"
fi

# ---------------------------------------------------------------- 8. Comprobación
paso "8/8 Comprobando que de verdad se puede entrar"
API="http://localhost:$P_BACK/api/v1"
for _ in $(seq 1 30); do curl -fsS "http://localhost:$P_BACK/health" >/dev/null 2>&1 && break; sleep 2; done
curl -fsS "http://localhost:$P_BACK/health" | grep -q '"ok"' || falla "El backend no responde en http://localhost:$P_BACK/health." "Mira sus mensajes: docker compose -f infra/docker-compose.yml logs backend"
bien "Backend responde en http://localhost:$P_BACK/health"
RESPUESTA="$(curl -sS -X POST "$API/seguridad/login" -H 'Content-Type: application/json' -d '{"email":"admin@dondetavo.demo","password":"Tavo2026*Admin"}')"
printf '%s' "$RESPUESTA" | grep -q '"access_token"' || falla "El login de admin@dondetavo.demo falló: $RESPUESTA" "Si la base no tiene la demo: cd backend && $PY ../automatizaciones/deploy/seed_demo.py"
bien "Login de admin@dondetavo.demo correcto"
for _ in $(seq 1 45); do curl -fsS "http://localhost:$P_FRONT/" >/dev/null 2>&1 && break; sleep 2; done
curl -fsS "http://localhost:$P_FRONT/" >/dev/null || falla "El frontend no responde en http://localhost:$P_FRONT." "Mira sus mensajes: docker compose -f infra/docker-compose.yml --profile frontend logs frontend"
bien "Frontend responde en http://localhost:$P_FRONT (llama a $API)"

cat <<FIN

==============================================================================
 Listo: el backend responde y el login de la demo entra.
==============================================================================

   Abre:  http://localhost:$P_FRONT
   API:   http://localhost:$P_BACK/docs

   Rol            Correo                   Contraseña        Entra a
   Administrador  admin@dondetavo.demo     Tavo2026*Admin    Dashboard
   Cajero         caja@dondetavo.demo      Tavo2026*Caja     Caja
   Mesero         mesero@dondetavo.demo    Tavo2026*Mesero   Tomar pedido (celular)
   Cocinero       cocina@dondetavo.demo    Tavo2026*Cocina   Cocina (tablet)

   Recargar los datos demo:  cd backend && $PY ../automatizaciones/deploy/seed_demo.py --reset
   Apagar:                   docker compose -f infra/docker-compose.yml --profile frontend stop

FIN
