# JS Company — Sistema de Gestión (ERP)

Backend interno de gestión para negocios: Dashboard, Compras, Ventas, Seguridad
y un módulo de IA como add-on. Ver el brief completo del proyecto para contexto
de negocio, catálogo de precios y decisiones de producto.

## Estructura del repositorio

```
js-company-erp/
├── backend/            → API en FastAPI (Python)
├── frontend/           → Interfaz en React + Vite + Tailwind
├── automatizaciones/   → Scripts de alta de clientes y tareas programadas
└── infra/              → Docker Compose para levantar todo junto
```

## Requisitos

- Python 3.11+
- Node.js 20+ (18 como mínimo)
- PostgreSQL 16 (o Docker Desktop, para no instalarlo local)

## Empezar desde cero (Windows)

Pasos exactos para quien acaba de clonar el repositorio. Los `.env` **no se
versionan** (tienen secretos): cada máquina crea los suyos, y el script de
abajo lo hace por ti.

**1. Instala los requisitos** (una sola vez; abre una terminal NUEVA después
de instalar, para que tome el PATH):

- Python 3.11 o superior: <https://www.python.org/downloads/> — marca
  *"Add python.exe to PATH"*.
- Node.js 20 LTS: <https://nodejs.org>.
- Git: <https://git-scm.com/download/win>.
- **Postgres**, una de dos:
  - **Docker Desktop** (recomendado): <https://www.docker.com/products/docker-desktop/>.
    Solo tiene que estar abierto; el script arranca el contenedor de
    Postgres (`infra/docker-compose.yml`, servicio `db`) si no hay uno.
  - **PostgreSQL 16 instalado en Windows**: <https://www.postgresql.org/download/windows/>.
    Crea el usuario que espera `backend/.env` (desde *SQL Shell (psql)*
    como `postgres`):
    ```sql
    CREATE ROLE js_admin LOGIN PASSWORD 'js_admin' CREATEDB;
    ```
    La base `js_company_erp` la crea el script.

**2. Clona y corre el setup** (PowerShell, desde la carpeta donde quieras el
proyecto):

```powershell
git clone <url-del-repositorio> producto-js
cd producto-js
powershell -ExecutionPolicy Bypass -File automatizaciones\setup.ps1
```

`setup.ps1` es idempotente (se puede repetir sin romper nada) y hace, en
orden: revisa requisitos → copia `backend/.env.example` y
`frontend/.env.example` a `.env` si faltan (con una `SECRET_KEY` aleatoria)
→ crea `backend/venv` e instala dependencias → `npm ci` → arranca Postgres
con Docker si hace falta y crea la base → `alembic upgrade head` → crea la
cuenta de prueba y carga datos de demostración → corre el diagnóstico. Al
final imprime las URLs y las credenciales:

| | |
|---|---|
| Aplicación | <http://localhost:5173> |
| API / documentación | <http://localhost:8001/docs> |
| Cuenta de prueba | `demo@jscompany.co` / `Demo2026!` |

En Linux, macOS o Git Bash: `bash automatizaciones/setup.sh` (mismos pasos).

**3. Arranca** backend y frontend, cada uno en su terminal (o agrega
`-Arrancar` al setup y los abre en dos ventanas):

```powershell
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-backend.ps1    # 8001
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-frontend.ps1   # 5173
```

**Comando recomendado para el backend: `start-backend.ps1`** (activa el
venv, lee el puerto de la configuración, cierra instancias viejas, comprueba
que Windows deje abrir el 8001 e imprime la URL). Sin el script:
`cd backend` y `venv\Scripts\python -m app.main`. En VS Code, F5 →
"Backend + Frontend" (`.vscode/launch.json`) o Ctrl+Mayús+B → "Arrancar
backend y frontend" (`.vscode/tasks.json`). **`uvicorn app.main:app` sin
`--port 8001` arranca en el 8000 y el frontend no lo encuentra.**

**Si algo no funciona, corre el diagnóstico** antes de tocar nada. Revisa
los `.env`, las variables cargadas (sin mostrar secretos), la conexión a
Postgres, las migraciones, los orígenes CORS y los puertos, y dice el
arreglo concreto de cada problema:

```powershell
cd backend
venv\Scripts\python -m app.diagnostico
venv\Scripts\python -m app.diagnostico --origen http://192.168.1.50:5173   # ¿ese origen pasa CORS?
```

Con el backend arriba, el mismo informe está en
<http://localhost:8001/diagnostico> (solo con `ENV=development`).

**Problemas típicos:**

- *El backend no arranca y dice "ERROR DE CONFIGURACIÓN"*: falta
  `backend/.env` o una variable obligatoria (`DATABASE_URL`, `SECRET_KEY`).
  El mensaje dice qué copiar; la plantilla con todas las variables
  comentadas es `backend/.env.example`.
- *`npm run dev` dice que falta `VITE_API_URL`*: copia
  `frontend/.env.example` a `frontend/.env`.
- *`ERR_CONNECTION_REFUSED` a `localhost:8001`*: el backend no está
  corriendo (o arrancó en otro puerto). Arráncalo con `start-backend.ps1`.
- *El puerto 8000 (o el 8001) está reservado* (`WinError 10013: Se intentó
  acceder a un socket de una forma que no está permitida por sus permisos de
  acceso`): Windows reserva rangos de puertos para Hyper-V/WSL/Docker al
  arrancar. Por eso el proyecto usa el **8001**, no el 8000 — no lo
  cambies. Para ver los rangos reservados:
  `netsh interface ipv4 show excludedportrange protocol=tcp` (el
  diagnóstico lo revisa solo). Si el 8001 también quedó dentro de un rango,
  en una PowerShell **como administrador**: `net stop winnat` y luego
  `net start winnat` (libera las reservas dinámicas; no toca tus datos).
- *`OPTIONS /api/v1/seguridad/login` responde 400 Bad Request*: el origen
  del frontend no está permitido por CORS. En desarrollo (`ENV=development`)
  se acepta cualquier origen local en cualquier puerto; si ves esto, revisa
  que `backend/.env` diga `ENV=development` (el diagnóstico lo muestra).

## Cómo levantar el proyecto en desarrollo

### Opción A — con Docker (recomendada, todo junto)

```bash
cd infra
docker compose up --build
```

Esto levanta Postgres, el backend en `http://localhost:8001` (docs interactivas
en `http://localhost:8001/docs`) y el frontend en `http://localhost:5173`.

### Opción B — manual (sin Docker)

**Backend** (siempre en el puerto **8001**, ver "Puertos en desarrollo"):
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajustar DATABASE_URL si aplica
alembic upgrade head            # crea las tablas
python -m app.main              # arranca en el 8001 (PORT de .env), con recarga
```

> **No corras `uvicorn app.main:app --reload` a secas.** El CLI de uvicorn
> no lee la configuración del proyecto y se va a su puerto por defecto, el
> **8000**: el backend arranca "bien", pero el frontend llama al **8001** y
> no lo encuentra (el navegador lo reporta como `ERR_CONNECTION_REFUSED` o
> como un falso error de CORS). Usa `start-backend.ps1`, `python -m app.main`
> o, si quieres uvicorn directo, pásale siempre `--port 8001`.

**Frontend** (siempre en el puerto **5173**):
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

En Windows, en vez de los comandos de arranque a mano, conviene usar los
scripts que además cierran instancias viejas y fallan si el puerto está
ocupado (la causa de casi todos los falsos errores de CORS de este
proyecto):

```powershell
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-backend.ps1    # backend en 8001
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-frontend.ps1   # frontend en 5173
```

### Puertos en desarrollo

Los puertos son **fijos a propósito**. Cuando un puerto cambia sin avisar,
el frontend sigue llamando al viejo y el navegador lo reporta como un error
de CORS que no tiene nada que ver con la configuración de CORS — eso costó
varias rondas de depuración en este proyecto.

| Servicio  | Puerto | Dónde se configura |
|-----------|--------|--------------------|
| Backend (FastAPI/uvicorn) | `8001` | `PORT` en `backend/app/core/config.py` / `backend/.env` (lo leen `python -m app.main` y `start-backend.ps1`), `.vscode/launch.json`, `infra/docker-compose.yml` (host `8001` → contenedor `8000`), `frontend/.env` (`VITE_API_URL`) |
| Frontend (Vite)           | `5173` | `frontend/vite.config.js` (`server.port` + `strictPort: true`) |
| Preview compilado (demo por túnel) | `4173` | `frontend/vite.config.js` (`preview.port` + `strictPort: true`); ver "Compartir una demo por internet" |
| Postgres                  | `5432` | `infra/docker-compose.yml` |

**Por qué el backend usa 8001 y no 8000:** en Windows el 8000 puede quedar
inutilizable (`WinError 10013`, o bindings fantasma que sobreviven al
proceso que los creó) por reservas de puerto de Hyper-V/WSL2. Revisa los
rangos reservados con `netsh int ipv4 show excludedportrange protocol=tcp`.
Dentro del contenedor Docker el backend sigue escuchando en 8000 — eso no
choca con nada porque es otro namespace de red; solo el puerto del host
cambia a 8001.

**Vite falla si el 5173 está ocupado** (`strictPort: true`) en vez de saltar
a 5174 en silencio. Si te pasa, cierra la instancia vieja de Vite — el
script `start-frontend.ps1` ya lo hace por ti.

`backend/.env` → `CORS_ORIGINS` se usa tal cual en producción. En
desarrollo (`ENV=development`) además se acepta **cualquier origen local en
cualquier puerto** (o sin puerto) vía `allow_origin_regex` (ver
`backend/app/core/cors.py`): `localhost`, `127.0.0.1`, `[::1]` y las IPs de
red privada (`10.x`, `172.16–31.x`, `192.168.x`), porque Vite (`server.host:
true`) también imprime una URL "Network" y abrirla daba 400 en el preflight
del login. Así da igual en qué puerto o URL levante el frontend en otra
máquina. Ese regex **no** aplica en producción, y `ENV` solo admite
`development` o `production` (un valor mal escrito ya no apaga el regex en
silencio: el backend no arranca y lo dice).

Si ves un error de CORS en el navegador, antes de tocar nada verifica que
el backend esté corriendo y respondiendo en `http://localhost:8001/health`
— un backend caído se ve en el navegador como un falso error de CORS
("CORS Failed", código de estado `null`), porque nunca llega a responder el
preflight `OPTIONS`.

Si `backend/.env` tiene un `CORS_ORIGINS` mal escrito (JSON inválido o
vacío), `uvicorn` no arranca: falla al cargar `Settings` con un mensaje en
español explicando el formato esperado (ver `backend/app/core/config.py`).
Este caso también lo cubre `pytest` (falla toda la suite al importar la
app) y el test dedicado `backend/tests/test_startup.py`, que levanta el
backend como proceso real y pega contra `/health`.

## Compartir una demo por internet (túnel)

Para que otra persona pruebe la app desde su casa sin desplegar nada:

```powershell
pwsh automatizaciones/demo/start-demo-tunel.ps1          # un solo comando
pwsh automatizaciones/demo/start-demo-tunel.ps1 -Forzar  # si 8001/4173 están ocupados, los libera
```

El script valida herramientas y puertos, arranca el backend en `8001`, abre
el túnel del backend, **compila** el frontend con esa URL pública
(`npx vite build --mode tunnel`, que lee `frontend/.env.tunnel`), sirve la
versión compilada con `vite preview` en `4173`, abre el túnel del frontend,
comprueba por HTTP que los `.js` llegan con tipo MIME de JavaScript y que
el backend acepta el origen público por CORS, y al final imprime:

- **la URL que se comparte** (la del frontend, `https://xxxx.loca.lt`);
- la URL pública del backend (no se comparte: ya va incrustada en la app);
- con localtunnel, la *contraseña del túnel* (la IP pública de tu equipo)
  que el invitado escribe una sola vez en la página de aviso.

**Qué debe quedar encendido durante la demo:** la ventana del script
(Ctrl+C la termina y cierra todo), el backend en `8001`, el preview en
`4173` y los dos túneles. **Todo depende de que tu computador siga prendido,
sin suspenderse y con internet**: si se apaga, la demo deja de funcionar. Las
URLs cambian en cada arranque; vuelve a compartir la nueva.

Por qué se comparte la versión compilada y no `npm run dev`: el servidor de
desarrollo sirve cientos de módulos `.jsx` sueltos y el WebSocket de HMR
apunta a `localhost:5173`; a través del túnel llegan lentos (≈9 s por
archivo), con `text/plain` y el navegador los bloquea
(`NS_ERROR_CORRUPTED_CONTENT`, "tipo MIME no permitido"). `vite preview`
sirve `dist/` con `text/javascript` (el tipo MIME estándar de JavaScript
según RFC 9239) y un solo paquete.

Piezas que lo hacen posible (configuración activa, no borrar en limpiezas):

| Pieza | Dónde |
|-------|-------|
| `allowedHosts: ['.loca.lt', '.ngrok-free.app', '.trycloudflare.com']` en `server` y `preview` (el punto acepta cualquier subdominio) y `preview.port = 4173` con `strictPort` | `frontend/vite.config.js` |
| `VITE_API_URL` pública para el build: `frontend/.env.tunnel` (lo genera el script; plantilla en `.env.tunnel.example`). En build la URL queda incrustada en el paquete, por eso no puede ser `localhost` | `frontend/.env.tunnel` |
| Header `bypass-tunnel-reminder` en las llamadas de la API (salta la página de aviso de localtunnel en las XHR) | `frontend/src/lib/api.js` |
| CORS de desarrollo: `allow_origin_regex` acepta `https://*.loca.lt`, `https://*.ngrok-free.app` y `https://*.trycloudflare.com` **solo con `ENV=development`** | `backend/app/core/cors.py` (bloque crítico), tests en `backend/tests/test_cors_config.py` |

Túnel alternativo: si tienes `cloudflared` instalado
(`winget install Cloudflare.cloudflared`), el script lo usa solo (no tiene
página de aviso); fuerza uno u otro con `-Tunel localtunnel|cloudflared`.
`5173` (desarrollo) y `8001` (backend) siguen siendo los puertos fijos;
`4173` es adicional, no un reemplazo.

## Dar de alta un cliente nuevo (tenant)

```bash
cd automatizaciones/deploy
python alta_tenant.py \
  --empresa "Nombre del negocio" \
  --plan estandar \
  --admin-email admin@negocio.com \
  --admin-password "clave-temporal" \
  --color-primario "#1E3A5F"
```

Esto crea el tenant, su rol de Administrador y el primer usuario, sin tocar
código ni desplegar nada nuevo — el mismo backend/frontend sirve a todos
los clientes (arquitectura multi-tenant).

## Convenciones del proyecto

- Cada módulo de negocio (dashboard, compras, ventas, seguridad, ia) vive
  en su propia carpeta tanto en backend (`app/modules/<modulo>`) como en
  frontend (`src/modules/<modulo>`), para poder activarlos o desactivarlos
  por cliente sin tocar los demás.
- Todas las tablas de datos de negocio heredan `TenantMixin`
  (`backend/app/db/mixins.py`) para quedar amarradas a la empresa dueña
  del dato.
- La personalización visual por cliente (colores, logo, tipografía) vive
  en `Tenant.theme_config` (backend) y se aplica en el frontend vía
  `src/theme/tokens.js`, sin necesidad de tocar el código de cada módulo.

## Estado técnico actual

- CRUD real de Compras (productos, categorías, proveedores, compras) y
  Ventas (ventas, pedidos), con control de stock automático.
- Login real (`/api/v1/seguridad/login`) con sesión persistida en el
  frontend y manejo de sesión expirada.
- Todo endpoint de negocio resuelve `tenant_id` desde el JWT (nunca de un
  parámetro que el cliente pueda manipular) vía `backend/app/core/deps.py`.
- Migraciones de Alembic generadas y aplicadas (`backend/alembic/versions/`).
- Antes de cualquier deploy, correr `automatizaciones/ci/pre-deploy.ps1`
  (tests de backend y frontend + build + chequeo de migraciones pendientes).
