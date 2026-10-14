# Producto Tavo — sistema para restaurantes

Sistema de gestión multi-tenant para restaurantes (órdenes y comanda, cocina,
caja, inventario de insumos con recetas, dashboard e IA). Su primer cliente es
"Donde Tavo", pero el código es genérico: cada restaurante es un tenant.

**Es una derivación del Producto JS** (ERP multi-tenant, commit `8146ea0`): de
ahí hereda login, permisos, alertas, validaciones, sistema de diseño, CORS y
aislamiento entre empresas. Qué se heredó y qué cambió: `CLAUDE.md` y
`docs/DECISIONES.md`.

> **Los dos productos corren a la vez en la misma máquina.** Este usa sus
> propios puertos, contenedores y base de datos (tabla en "Puertos"). Nunca
> uses aquí los del Producto JS (5173 / 4173 / 8001 / 5432).

## Estructura del repositorio

```
producto-tavo/
├── backend/            → API en FastAPI (Python)
├── frontend/           → Interfaz en React + Vite + Tailwind
├── automatizaciones/   → Scripts de alta de clientes y tareas programadas
└── infra/              → Docker Compose para levantar todo junto
```

## Requisitos

- Docker Desktop (encendido): Postgres, backend y frontend corren ahí
- Python 3.11+
- Node.js 20+ (18 como mínimo)

## Empezar desde cero (Windows)

Pasos exactos para quien llega nuevo al proyecto. Los `.env` **no se
versionan** (tienen secretos): cada máquina crea los suyos, y el script de
abajo lo hace por ti.

> **Tu base de datos es tuya.** Lo que hay en la base de otra persona
> (órdenes, cobros, ajustes, usuarios que creó) **no viaja por git**: git solo
> lleva el código. Tu Postgres empieza vacío y el script le carga los mismos
> datos de demostración. Si quieres empezar de nuevo, vuelve a cargarlos con
> `seed_demo.py --reset` (paso 4).

**0. Acepta la invitación.** Te llega un correo de GitHub ("invited you to
collaborate on Camacho077/Producto-Tavo"): ábrelo y pulsa *Accept
invitation* (o entra a <https://github.com/Camacho077/Producto-Tavo/invitations>
con tu cuenta). El repositorio es privado: sin aceptar, no podrás clonarlo.

**1. Instala los requisitos** (una sola vez; abre una terminal NUEVA después
de instalar, para que tome el PATH):

- **Docker Desktop**: <https://www.docker.com/products/docker-desktop/>.
  Ábrelo y espera a que diga *Engine running*: el setup lo necesita
  encendido (corre ahí Postgres, el backend y el frontend).
- **Python 3.11 o superior**: <https://www.python.org/downloads/> — marca
  *"Add python.exe to PATH"*.
- **Node.js 20 LTS**: <https://nodejs.org>.
- **Git**: <https://git-scm.com/download/win>.

**2. Clona y corre el setup** (PowerShell, desde la carpeta donde quieras el
proyecto):

```powershell
git clone https://github.com/Camacho077/Producto-Tavo.git producto-tavo
cd producto-tavo
powershell -ExecutionPolicy Bypass -File automatizaciones\setup.ps1
```

En Linux, macOS o Git Bash: `bash automatizaciones/setup.sh` (mismos pasos).

`setup.ps1` es idempotente (se puede repetir sin romper nada) y hace, en
orden:

1. Revisa Python, Node y que Docker esté **encendido**.
2. Copia `backend/.env.example` y `frontend/.env.example` a `.env` si faltan
   (con una `SECRET_KEY` aleatoria).
3. **Elige los puertos de tu máquina** (`automatizaciones/dev/puertos.py`):
   8002 para el backend, 5433 para Postgres y 5175 para el frontend, salvo
   que Windows los tenga reservados u otro programa los use; entonces toma
   el siguiente libre, **avisa** y lo escribe en `backend/.env`,
   `frontend/.env` e `infra/.env`, para que backend y frontend apunten al
   mismo.
4. Crea `backend/venv` con sus dependencias y corre `npm ci`.
5. Levanta Postgres en Docker (espera a que esté listo) y aplica las
   migraciones.
6. **Si tu base está vacía**, carga los datos de demostración: el
   restaurante "Donde Tavo" con 90 días de historia y "Café Central" para
   probar el aislamiento. Tarda unos 5 minutos y nunca se hace con
   `ENV=production`.
7. Levanta el backend y el frontend en Docker. El backend espera a Postgres,
   migra y tiene *healthcheck*.
8. **Comprueba de verdad** que `/health` responde, que el login con
   `admin@dondetavo.demo` entra y que la página carga. Solo entonces dice
   **"Listo"** e imprime la URL y la tabla de cuentas. Si algo falla, dice la
   causa y qué hacer.

**3. Ábrelo** en la URL que imprime el setup (normalmente
<http://localhost:5175>) y entra con una cuenta de la demo. Existen **solo
en desarrollo**: con `ENV=production` el script se niega a crearlas. Cada rol
entra a su propia pantalla y solo ve lo suyo; ábrelo en el dispositivo de
cada rol, o con el modo de dispositivo del navegador:

| Rol | Correo | Contraseña | Entra a | Dispositivo |
|---|---|---|---|---|
| Administrador | `admin@dondetavo.demo` | `Tavo2026*Admin` | Dashboard | escritorio |
| Cajero | `caja@dondetavo.demo` | `Tavo2026*Caja` | Caja | escritorio |
| Mesero | `mesero@dondetavo.demo` | `Tavo2026*Mesero` | Tomar pedido | celular |
| Cocinero | `cocina@dondetavo.demo` | `Tavo2026*Cocina` | Cocina | tablet |
| Admin de otra empresa | `admin@cafecentral.demo` | `Central2026*Admin` | Dashboard de Café Central | escritorio |

También existen `mesero2@` y `mesero3@dondetavo.demo` (`Tavo2026*Mesero`) y
`cocina2@dondetavo.demo` (`Tavo2026*Cocina`).

**4. Recargar los datos demo** cuando quieras. Las fechas son relativas al
día en que se cargan: para que "Hoy" tenga órdenes en cocina, mesas
ocupadas y caja abierta, recárgalos el día que vayas a mostrarlo (desde
`backend/`):

```powershell
venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py --reset   # borra y recrea las dos empresas demo
venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py           # solo carga si hoy no hay datos
```

**Para programar con recarga en caliente** (opcional): detén los
contenedores de backend y frontend
(`docker compose -f infra/docker-compose.yml --profile frontend stop backend frontend`)
y arranca cada parte en su terminal:

```powershell
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-backend.ps1    # puerto de PORT en backend/.env
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-frontend.ps1   # 5175
```

**`uvicorn app.main:app` a secas no sirve**: arranca en el 8000, donde el
frontend no lo busca (por eso el proyecto lo detiene con un mensaje). Usa
siempre `start-backend.ps1` (o `cd backend` y `venv\Scripts\python -m app.main`).

## Si no puedes entrar

Corre el diagnóstico. No cambia nada; revisa todo lo que tiene que estar
bien para que el login funcione y dice qué arreglar en cada punto:

```powershell
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\diagnostico.ps1
```

Revisa: Docker encendido; los tres `.env` y que el frontend apunte al MISMO
puerto que el backend; los puertos (libres, ocupados por otro programa o
reservados por Windows); los contenedores y su salud; `/health` del
backend; que la página cargue; las migraciones; que existan las cuentas
demo; y el login real con cada una. **Casi siempre basta con volver a
correr `automatizaciones\setup.ps1`**: alinea los puertos, levanta lo que
falte y carga la demo si la base está vacía.

Qué significa cada mensaje del login:

| Mensaje | Causa | Qué hacer |
|---|---|---|
| *No se pudo conectar con el servidor en http://localhost:8002/api/v1. Verifica que el backend esté corriendo.* | Nada escucha en ese puerto: el backend no arrancó, se cayó, arrancó en otro puerto (`uvicorn` a secas usa el 8000) o el frontend apunta a otro (`VITE_API_URL`). | Corre el diagnóstico y luego `setup.ps1`. Si usas `npm run dev`, reinícialo después de cambiar `frontend/.env`. |
| *Correo o contraseña incorrectos.* | El backend responde, pero esa cuenta no existe en TU base o la clave no coincide. | Si tu base no tiene la demo: `seed_demo.py --reset` (paso 4). |
| Cualquier otro texto | Es el motivo exacto que devolvió el backend (p. ej. "Usuario inactivo"). | Lo que diga el mensaje. |

Otros casos:

- *El 8002 está reservado u ocupado en tu Windows* (`WinError 10013`): el
  setup lo detecta y usa el siguiente libre, avisando. Para ver los rangos
  reservados: `netsh interface ipv4 show excludedportrange protocol=tcp`.
  Para liberarlos (PowerShell **como administrador**): `net stop winnat` y
  luego `net start winnat`; no toca tus datos.
- *El contenedor del backend se cae al arrancar*: mira su motivo con
  `docker compose -f infra/docker-compose.yml logs backend`. Siempre dice
  en español qué falta: el `.env`, Postgres que no respondió o una migración
  que falló.
- *La base está vacía*: es lo normal en una máquina nueva. **Tus datos no
  viajan por git**, ni los de nadie. El setup carga la demo solo si la base
  no tiene ningún usuario.
- *`OPTIONS /api/v1/seguridad/login` responde 400*: el origen del frontend
  no pasa CORS. En desarrollo (`ENV=development`) se acepta cualquier origen
  local; revisa `ENV` en `backend/.env`.

Diagnóstico de la configuración del backend (variables, CORS, Postgres),
desde `backend/`: `venv\Scripts\python -m app.diagnostico`.

## Cómo levantar el proyecto en desarrollo

### Opción A — con Docker (Postgres + backend + n8n)

```powershell
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\verificar-puertos.ps1
docker compose -f infra/docker-compose.yml up -d --build
```

Levanta, con nombre de proyecto `tavo` (nunca el del Producto JS):
`tavo-db` (Postgres en el **5433**, base `tavo_erp`), `tavo-backend`
(`http://localhost:8002`, docs en `/docs`; aplica las migraciones al
arrancar) y `tavo-n8n` (`http://localhost:5679`). El frontend se corre con
Vite (`start-frontend.ps1`, puerto 5175); para tenerlo también en Docker:
`docker compose -f infra/docker-compose.yml --profile frontend up -d`.

Solo Postgres (para desarrollar el backend con recarga):
`docker compose -f infra/docker-compose.yml up -d db`.

### Opción B — manual (sin Docker)

**Backend** (siempre en el puerto **8002**, ver "Puertos en desarrollo"):
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajustar DATABASE_URL si aplica
alembic upgrade head            # crea las tablas
python -m app.main              # arranca en el 8002 (PORT de .env), con recarga
```

> **`uvicorn app.main:app --reload` a secas no arranca.** El CLI de uvicorn
> no lee la configuración del proyecto y se iría a su puerto por defecto, el
> **8000**, donde el frontend (que llama al **8002**) no lo encuentra; por
> eso `app/core/arranque.py` lo detiene con un mensaje. Usa
> `start-backend.ps1`, `python -m app.main` o `--port 8002`.

**Frontend** (siempre en el puerto **5175**):
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
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-backend.ps1    # backend en 8002
powershell -ExecutionPolicy Bypass -File automatizaciones\dev\start-frontend.ps1   # frontend en 5175
```

### Puertos

Los puertos son **fijos a propósito** y **ninguno se repite con el Producto
JS**, que corre a la vez en la misma máquina. Cuando un puerto cambia sin
avisar, el frontend sigue llamando al viejo y el navegador lo reporta como un
error de CORS que no tiene nada que ver con la configuración de CORS.

| Servicio | Producto JS (no tocar) | **Producto Tavo** | Dónde se configura (Tavo) |
|---|---|---|---|
| Frontend (Vite dev) | 5173 | **5175** | `frontend/vite.config.js` (`server.port` + `strictPort`), `package.json` (`predev`) |
| Vista previa compilada | 4173 | **4175** | `frontend/vite.config.js` (`preview.port` + `strictPort`) |
| Backend (FastAPI) | 8001 | **8002** | `PORT` en `app/core/config.py` / `backend/.env`, `frontend/.env` (`VITE_API_URL`), `infra/docker-compose.yml`, `.vscode/`, `.claude/launch.json` |
| Postgres (en el equipo) | 5432 | **5433** | `infra/docker-compose.yml` (`5433:5432`), `DATABASE_URL` |
| n8n | — | **5679** | `infra/docker-compose.yml` (`5679:5678`) |

Contenedores `tavo-db`, `tavo-backend`, `tavo-n8n` (y `tavo-frontend` con
el perfil `frontend`), volúmenes `tavo_db_data` y `tavo_n8n_data`, proyecto
de Compose `tavo`. El compose del Producto JS no tiene nombre propio y
Docker lo llama `infra` (como su carpeta): sin `name: tavo`, este compose
habría usado sus mismos contenedores y su volumen de datos.

**Antes de arrancar**, `automatizaciones\dev\verificar-puertos.ps1` revisa
los cinco puertos: libre, reservado por Windows (con el arreglo) u ocupado
(con el proceso o contenedor que lo tiene). Los scripts de arranque lo
llaman solos.

**`uvicorn app.main:app` a secas no arranca**: el CLI de uvicorn no lee la
configuración e iría al 8000, así que `app/core/arranque.py` lo detiene con
un mensaje que dice cómo arrancarlo (`python -m app.main`,
`start-backend.ps1` o `--port 8002`).

**Por qué 8002 y no 8000:** en Windows el 8000 puede quedar inutilizable
(`WinError 10013`, o bindings fantasma que sobreviven al proceso que los
creó) por reservas de puerto de Hyper-V/WSL2; el 8002 es del Producto JS.
Revisa los rangos reservados con
`netsh int ipv4 show excludedportrange protocol=tcp`.

**Vite falla si el 5175 está ocupado** (`strictPort: true`) en vez de
saltar al siguiente en silencio. `start-frontend.ps1` cierra antes el Vite
viejo de ESTE producto (por la ruta de la carpeta), nunca el del Producto JS.

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
el backend esté corriendo y respondiendo en `http://localhost:8002/health`
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
pwsh automatizaciones/demo/start-demo-tunel.ps1 -Forzar  # si 8002/4175 están ocupados, los libera
```

El script valida herramientas y puertos, arranca el backend en `8002`, abre
el túnel del backend, **compila** el frontend con esa URL pública
(`npx vite build --mode tunnel`, que lee `frontend/.env.tunnel`), sirve la
versión compilada con `vite preview` en `4175`, abre el túnel del frontend,
comprueba por HTTP que los `.js` llegan con tipo MIME de JavaScript y que
el backend acepta el origen público por CORS, y al final imprime:

- **la URL que se comparte** (la del frontend, `https://xxxx.loca.lt`);
- la URL pública del backend (no se comparte: ya va incrustada en la app);
- con localtunnel, la *contraseña del túnel* (la IP pública de tu equipo)
  que el invitado escribe una sola vez en la página de aviso.

**Qué debe quedar encendido durante la demo:** la ventana del script
(Ctrl+C la termina y cierra todo), el backend en `8002`, el preview en
`4175` y los dos túneles. **Todo depende de que tu computador siga prendido,
sin suspenderse y con internet**: si se apaga, la demo deja de funcionar. Las
URLs cambian en cada arranque; vuelve a compartir la nueva.

Por qué se comparte la versión compilada y no `npm run dev`: el servidor de
desarrollo sirve cientos de módulos `.jsx` sueltos y el WebSocket de HMR
apunta a `localhost:5175`; a través del túnel llegan lentos (≈9 s por
archivo), con `text/plain` y el navegador los bloquea
(`NS_ERROR_CORRUPTED_CONTENT`, "tipo MIME no permitido"). `vite preview`
sirve `dist/` con `text/javascript` (el tipo MIME estándar de JavaScript
según RFC 9239) y un solo paquete.

Piezas que lo hacen posible (configuración activa, no borrar en limpiezas):

| Pieza | Dónde |
|-------|-------|
| `allowedHosts: ['.loca.lt', '.ngrok-free.app', '.trycloudflare.com']` en `server` y `preview` (el punto acepta cualquier subdominio) y `preview.port = 4175` con `strictPort` | `frontend/vite.config.js` |
| `VITE_API_URL` pública para el build: `frontend/.env.tunnel` (lo genera el script; plantilla en `.env.tunnel.example`). En build la URL queda incrustada en el paquete, por eso no puede ser `localhost` | `frontend/.env.tunnel` |
| Header `bypass-tunnel-reminder` en las llamadas de la API (salta la página de aviso de localtunnel en las XHR) | `frontend/src/lib/api.js` |
| CORS de desarrollo: `allow_origin_regex` acepta `https://*.loca.lt`, `https://*.ngrok-free.app` y `https://*.trycloudflare.com` **solo con `ENV=development`** | `backend/app/core/cors.py` (bloque crítico), tests en `backend/tests/test_cors_config.py` |

Túnel alternativo: si tienes `cloudflared` instalado
(`winget install Cloudflare.cloudflared`), el script lo usa solo (no tiene
página de aviso); fuerza uno u otro con `-Tunel localtunnel|cloudflared`.
`5175` (desarrollo) y `8002` (backend) siguen siendo los puertos fijos;
`4175` es adicional, no un reemplazo.

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
