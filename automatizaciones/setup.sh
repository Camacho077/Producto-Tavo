#!/usr/bin/env bash
# =============================================================================
# Deja el proyecto listo para desarrollar en una máquina nueva
# (Linux, macOS o Git Bash en Windows). Equivalente a automatizaciones/setup.ps1.
#
# IDEMPOTENTE: se puede correr cuantas veces se quiera; lo hecho se salta.
#   1. Requisitos (Python 3.11+, Node 18+, Postgres o Docker)
#   2. Copia los .env.example a .env si no existen (SECRET_KEY aleatoria)
#   3. backend/venv + dependencias de Python
#   4. Dependencias de npm del frontend
#   5. Postgres (lo arranca con Docker si hace falta) y crea la base
#   6. alembic upgrade head
#   7. Empresa + usuario de prueba y datos de demostración (seed_demo.py)
#   8. Diagnóstico, URLs y credenciales
#
# Uso, desde la raíz del repositorio:
#   bash automatizaciones/setup.sh
# =============================================================================
set -euo pipefail
export PYTHONIOENCODING=utf-8

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$RAIZ/backend"
FRONTEND="$RAIZ/frontend"

DEMO_EMPRESA="Empresa Demo"
DEMO_EMAIL="demo@jscompany.co"
DEMO_CLAVE="Demo2026!"

paso()  { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
bien()  { printf '    \033[32m[OK]\033[0m %s\n' "$1"; }
aviso() { printf '    \033[33m[!]\033[0m %s\n' "$1"; }
falla() { printf '\n    \033[31m[ERROR] %s\033[0m\n' "$1"; [ -n "${2:-}" ] && printf '    \033[31m-> %s\033[0m\n' "$2"; echo; exit 1; }
puerto_escucha() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

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

# ---------------------------------------------------------------- 2. .env
paso "2/8 Archivos de configuración (.env)"
if [ -f "$BACKEND/.env" ]; then
  bien "backend/.env ya existe (no se toca)"
else
  CLAVE="$($PYTHON -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed "s|^SECRET_KEY=.*|SECRET_KEY=$CLAVE|" "$BACKEND/.env.example" > "$BACKEND/.env"
  bien "backend/.env creado desde .env.example (con SECRET_KEY aleatoria)"
fi
if [ -f "$FRONTEND/.env" ]; then
  bien "frontend/.env ya existe (no se toca)"
else
  cp "$FRONTEND/.env.example" "$FRONTEND/.env"
  bien "frontend/.env creado desde .env.example"
fi

# ---------------------------------------------------------------- 3. Python
paso "3/8 Entorno virtual de Python y dependencias"
[ -d "$BACKEND/venv" ] || { $PYTHON -m venv "$BACKEND/venv"; bien "backend/venv creado"; }
if [ -x "$BACKEND/venv/bin/python" ]; then PY="$BACKEND/venv/bin/python"; else PY="$BACKEND/venv/Scripts/python.exe"; fi
"$PY" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$PY" -m pip install --quiet --disable-pip-version-check -r "$BACKEND/requirements-dev.txt"
bien "Dependencias de Python instaladas"

# ---------------------------------------------------------------- 4. npm
paso "4/8 Dependencias del frontend (npm)"
( cd "$FRONTEND" && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund --loglevel=error; else npm install --no-audit --no-fund --loglevel=error; fi )
bien "Dependencias de npm instaladas"

# ---------------------------------------------------------------- 5. Postgres
paso "5/8 Base de datos (Postgres)"
if puerto_escucha 5432; then
  bien "Postgres escucha en el puerto 5432"
elif command -v docker >/dev/null; then
  aviso "No hay Postgres en el 5432: lo arranco con Docker (infra/docker-compose.yml, servicio db)"
  docker compose -f "$RAIZ/infra/docker-compose.yml" up -d db
else
  falla "No hay Postgres escuchando en el puerto 5432 y no está Docker." \
        "Instala Docker o PostgreSQL 16 con el usuario js_admin / clave js_admin (ver README, 'Empezar desde cero')."
fi

cd "$BACKEND"
"$PY" "$RAIZ/automatizaciones/dev/preparar_base.py"

# ---------------------------------------------------------------- 6. Migraciones
paso "6/8 Migraciones (alembic upgrade head)"
"$PY" -m alembic upgrade head
bien "Esquema al día"

# ---------------------------------------------------------------- 7. Datos
paso "7/8 Usuario y datos de prueba"
"$PY" "$RAIZ/automatizaciones/deploy/alta_tenant.py" --empresa "$DEMO_EMPRESA" --plan pro_ia \
  --admin-email "$DEMO_EMAIL" --admin-password "$DEMO_CLAVE" --si-no-existe
"$PY" "$RAIZ/automatizaciones/deploy/seed_demo.py" --email "$DEMO_EMAIL"

# ---------------------------------------------------------------- 8. Diagnóstico
paso "8/8 Diagnóstico del entorno"
"$PY" -m app.diagnostico || falla "El diagnóstico encontró errores." "Arregla los puntos marcados con ✘ y vuelve a correr este script."

cat <<FIN

==============================================================================
 Listo. Para trabajar, arranca cada parte en su propia terminal:
==============================================================================
   Backend :  cd backend && $PY -m uvicorn app.main:app --port 8001 --reload
   Frontend:  cd frontend && npm run dev

   Aplicación:        http://localhost:5173
   API (docs):        http://localhost:8001/docs
   Diagnóstico:       http://localhost:8001/diagnostico   (o: cd backend && $PY -m app.diagnostico)

   Cuenta de prueba:  $DEMO_EMAIL
   Contraseña:        $DEMO_CLAVE
   (empresa '$DEMO_EMPRESA' con categorías, productos, compras, ventas y pedidos de ejemplo)

FIN
