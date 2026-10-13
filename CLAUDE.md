# Producto Tavo — sistema para restaurantes (multi-tenant)

## Qué es esto
Sistema de gestión para restaurantes: órdenes de pedido con comanda, pantalla
de cocina, caja, inventario de insumos con recetas (costo y margen por plato),
dashboard e IA. Lo usa el equipo del restaurante (administrador, cajero,
mesero, cocinero), no el comensal. **Primer cliente: "Donde Tavo"**
(restaurante dentro de una universidad, 12 años sin sistema). Se venderá a
otros restaurantes: Donde Tavo es su primer TENANT, nunca algo cableado en el
código. Nombre provisional del producto: "JS Restaurante".

## Derivación del Producto JS (2026-10-12)
- Nace de una copia del **Producto JS** (ERP multi-tenant,
  `C:\Users\camac\Desktop\Producto JS`, repo `Camacho077/Producto-JS`) en su
  commit `8146ea0`, exportada con `git archive`. Repositorio git propio, sin
  historial ni remoto compartido.
- **NUNCA se escribe en la carpeta del Producto JS.** Si una tarea parece
  requerirlo, se para y se pregunta.
- **Se hereda sin tocar**: login y registro, alertas, validaciones (incluido
  el bloqueo al escribir), permisos por rol (y por plan) en el backend,
  documentos legales y política de datos, auditoría de cookies, sistema de
  diseño monocromo, tipografías, animaciones y reglas de rendimiento,
  gráficas, componentes compartidos, CORS y aislamiento entre empresas.
  Todas las reglas de abajo siguen vigentes salvo lo que diga este bloque.
- **Cambia** (fases 1–12, plan en `docs/DECISIONES.md` §0): branding (logo y
  nombre en un archivo de branding), datos de prueba y módulos. Marcas se
  QUITA; Compras pasa a compra de INSUMOS; Ventas → Caja; Pedidos → Órdenes
  de pedido con comanda; Proveedores, Usuarios, Roles, Dashboard e IA se
  adaptan. Quitar un módulo es borrarlo de verdad (rutas, tablas con su
  migración, tests, menú): nada de código muerto.
- Mientras no avance la fase correspondiente, el código y el texto de abajo
  todavía hablan del ERP (Ventas, Pedidos…): es lo heredado.
- **Avance** (detalle en `docs/DECISIONES.md` §0): fase 0 verificada; fase 1
  (branding en `frontend/src/config/branding.jsx` + espejo
  `backend/app/core/branding.py`, Marcas eliminada, módulo `ajustes`:
  negocio, logo, operación en `Tenant.configuracion` leída por
  `ConfiguracionRestaurante`, impresoras, jornada, zonas y mesas; imágenes
  WebP en `app/modules/imagenes`, públicas por UUID); fase 2 (el inventario
  es de INSUMOS: módulos `catalogo` (platos/combos con receta, modificadores,
  agotado hoy), `inventario` (insumos, unidades, movimientos, promedio
  ponderado) y `compras` de insumos; costo del plato en vivo y permiso
  `costos.ver`); fase 3 (mermas con motivo, conteos físicos con ajuste
  valorizado, historial general `/inventario/movimientos`, permiso
  `movimientos`, carga inicial desde plantilla Excel/CSV en
  `app/modules/inventario/carga.py`: se revisa fila por fila y se aplica
  todo o nada); fase 4 (módulo `ordenes`: orden con consecutivo por
  jornada, comandas por envío, descuento de insumos en una transacción,
  anular con motivo devolviendo el `consumo` guardado, tablero, mesas y
  `lib/impresion.js` con el conector del navegador; los Pedidos del ERP se
  borraron); fase 5 (módulo `cocina`: comandas en vivo por consulta corta,
  Tomar/Finalizar, permiso `cocina` aparte); fase 6 (módulo `caja` reemplaza a
  `ventas`: cobro = venta con comprobante INTERNO, varios medios, propina,
  impuesto desglosado, dividir cuenta, apertura/cierre con cuadre; módulo
  `gastos`); fase 7 (inicio y menú por rol con `inicioDeRol`, modo enfocado
  para un rol de una sola pantalla, PWA con `public/sw.js` solo en build);
  fase 8 (`app/modules/reportes/consultas.py` define vendido, ingresos,
  costo y utilidades para dashboard y Reportes; donas de máx. 6 partes).
  Lo de "Stock = suma de movimientos" y "Proveedores ↔
  Productos" de abajo es HISTÓRICO: hoy aplica a los insumos.

## Mapa de puertos — CONFIGURACIÓN CRÍTICA (no se borra en limpiezas)
Los dos productos corren AL MISMO TIEMPO en la misma máquina. Ningún puerto,
contenedor, volumen ni base se comparte:

| Servicio | Producto JS (no tocar) | Producto Tavo |
|---|---|---|
| Frontend (Vite dev) | 5173 | **5175** |
| Vista previa compilada | 4173 | **4175** |
| Backend (FastAPI) | 8001 | **8002** |
| Postgres (puerto en el equipo) | 5432 | **5433** |
| n8n | — | **5679** |

- Docker: `infra/docker-compose.yml` con `name: tavo`, contenedores
  `tavo-db` / `tavo-backend` / `tavo-n8n` (y `tavo-frontend` con el perfil
  `frontend`), volúmenes `tavo_db_data` / `tavo_n8n_data`, base `tavo_erp`
  con usuario `tavo_admin`. El compose del Producto JS no tiene nombre y
  Docker lo llama `infra`: sin `name: tavo` se compartirían contenedores y
  datos. Dentro de Docker se habla por nombre de servicio (`db:5432`,
  `backend:8002`, `n8n:5678`).
- `automatizaciones/dev/verificar-puertos.ps1` revisa los puertos (reserva
  de Windows, ocupación, qué proceso o contenedor) antes de arrancar; lo
  llaman `start-backend.ps1` y `start-frontend.ps1`.
- Los scripts SOLO cierran procesos de este producto (por puerto o por la
  ruta de esta carpeta), nunca "todo uvicorn" o "todo vite".
- `uvicorn app.main:app` a secas no arranca (`app/core/arranque.py`).
- Lo protegen `backend/tests/test_mapa_de_puertos.py`,
  `tests/test_arranque.py`, `tests/test_config.py` y
  `frontend/src/vite-config.test.js`.

## Reglas de trabajo en este repositorio
- Una rama por fase, commits claros, y tests + build al cerrar cada fase.
  Nada a `main` sin aprobación explícita del usuario.
- Cada decisión nueva va a `docs/DECISIONES.md` con fecha, en el mismo
  trabajo en que se toma.

## LEER PRIMERO
- **`docs/DECISIONES.md`** — registro fechado de TODAS las decisiones
  (paleta vigente y descartadas, tipografías, reglas de movimiento y
  rendimiento, configuración crítica que no se borra). Cada decisión nueva
  se agrega ahí con fecha, en el mismo trabajo en que se toma.
- **`PRODUCT.md`** — contexto de producto para Impeccable (usuarios,
  posicionamiento, WCAG AA).
- **Skills instaladas** en `.claude/skills/` (2026-09-28): colección de Emil
  Kowalski (`animate`, `improve-animations`, `review-animations`…),
  taste-skill (diales 3 / 5 / 8: estructura clara, movimiento sobrio, mucha
  densidad) e Impeccable (`npx impeccable detect src/` desde `frontend/`).
  Se usan SOLO para movimiento, rendimiento y pulido: paleta, tipografías
  (Playfair Display / Inter / JetBrains Mono) y layout aprobados mandan
  sobre cualquier consejo de una skill.

## Arquitectura clave (no romper esto)
- **Multi-tenant real, no un deploy por cliente.** Un solo backend y una
  sola base de datos sirven a todas las empresas. Cada tabla de negocio
  hereda `TenantMixin` (`backend/app/db/mixins.py`), que agrega `tenant_id`.
  Cualquier query o endpoint nuevo sobre datos de negocio DEBE filtrar por
  `tenant_id` (lo cubre `tests/test_permisos.py`: desde otra empresa, 404 y
  cero datos ajenos en cada ruta con id).
- **Permisos por rol (2026-09-30): la seguridad está en el BACKEND.** Todo
  endpoint de negocio declara su permiso con
  `Depends(tenant_con_permiso("modulo", "accion"))` o
  `usuario_con_permiso(...)` (`app/core/permisos.py`), nunca
  `get_current_tenant_id` a secas. El catálogo de módulos y acciones está en
  `app/core/catalogo_permisos.py` (y en ningún otro lado). Un endpoint nuevo
  sin permiso rompe `tests/test_permisos.py`: agrégalo a `ESPERADO` con el
  permiso que exige. El frontend solo oculta (`useAuth().puede(m, a)`,
  `components/ConPermiso.jsx`). El rol con `es_administrador` tiene todo,
  no se borra y solo otro administrador lo asigna. Detalle en
  `docs/DECISIONES.md` §7.
- **Un módulo = una carpeta**, igual en backend (`app/modules/<modulo>`) y
  frontend (`src/modules/<modulo>`): `dashboard`, `compras`, `ventas`,
  `seguridad`, `ia`. Así se activan/desactivan por cliente según el plan
  contratado sin tocar los demás módulos.
- **Personalización por cliente** (colores, logo, tipografía) vive en
  `Tenant.theme_config` (backend, JSON) y se aplica en frontend vía
  `src/theme/tokens.js` con CSS variables — nunca hardcodear colores de marca
  en componentes, siempre usar `var(--color-primario)`, etc.
- **Planes → módulos visibles**: `frontend/src/config/modules.js` controla
  qué módulos aparecen en el sidebar según `tenant.plan`
  (`basico` < `estandar` < `pro_ia`) más `tenant.modulos_activos`. Cada
  módulo puede tener `hijos` (submódulos con ruta propia) y el sidebar los
  muestra como grupo desplegable. Si se agrega un módulo o submódulo nuevo,
  hay que registrarlo ahí Y agregar su `<Route>` en `App.jsx`. **El plan
  también se exige en el BACKEND (2026-10-01)**: `exigir_permiso` comprueba
  el plan (o el add-on en `modulos_activos`) antes que el rol, con el mapa
  grupo → plan mínimo de `catalogo_permisos.py`, que debe coincidir con
  `modules.js` (`tests/test_planes.py`).

## Estado actual (lo que YA funciona)
- Backend: FastAPI con login/registro JWT (bcrypt + jose) y `tenant_id`
  resuelto desde el token en todos los endpoints de negocio.
- CRUD real y paginado (`?q=&pagina=&por_pagina=`, sobre
  `{items,total,pagina,por_pagina,paginas}` de `app/core/paginacion.py`) de:
  Categorías, Marcas, Proveedores, Productos, Compras (confirmar/cancelar/
  anular con reversión de stock), Ventas (completar/anular), Pedidos
  (prioridad, transiciones de estado validadas y línea de tiempo en
  `pedido_eventos`), Usuarios y Roles (permisos JSON por módulo/acción).
- **Stock = suma de movimientos.** El producto nace con stock 0 y el
  formulario no lo edita (el backend ignora cualquier `stock` en el PUT).
  Cada compra confirmada, venta completada y anulación escribe una fila en
  `movimientos_inventario` (`registrar_movimiento` en `compras/services.py`:
  tipo, cantidad con signo, stock_resultante, documento, usuario) y el stock
  nunca queda negativo (409 "Stock insuficiente para 'X': disponible N,
  solicitado M", validado sobre todas las líneas antes de mover nada).
  Historial en `GET /compras/productos/{id}/movimientos`; lo cubre
  `tests/test_inventario.py` (compra → anular → stock vuelve).
- **Proveedores ↔ Productos (muchos a muchos)** en `proveedor_productos`
  (con `tenant_id`). Las relaciones son `viewonly`; las filas se escriben en
  `sincronizar_productos_proveedor` con `producto_ids` del PUT/POST de
  proveedor. `GET /compras/productos?proveedor_id=` filtra por proveedor.
- PDF de compra, venta y pedido con reportlab (`app/core/pdf.py`,
  endpoints `/{id}/pdf`).
- Dashboard: **dos endpoints independientes, porque en la pantalla son dos
  controles distintos** (mover uno no debe volver a pedir el otro):
  `/dashboard/panel?periodo=hoy|mes|anio` devuelve las cifras (totales con su
  variación, clientes, unidades vendidas, más vendidos con categoría y
  variación, inventario con su rejilla por categoría, y la proyección del mes
  siguiente por regresión lineal sobre 6 meses), y
  `/dashboard/serie?rango=1d|1s|1m|6m|1a` devuelve la serie de la gráfica
  (24 horas / 7 días / 30 días / 6 meses / 12 meses) con el tramo actual, el
  tramo anterior del mismo tamaño y una proyección de un bucket hacia
  adelante. La aritmética de ventanas vive en
  `app/modules/dashboard/periodos.py`: el tramo anterior mide SIEMPRE lo
  mismo que el actual (comparar 25 días de septiembre contra los 31 de agosto
  inventaría una caída). Los días, meses y años son los de COLOMBIA
  (`ZONA_NEGOCIO`, UTC-5), no los de UTC: los límites se calculan en hora
  de Bogotá y se pasan a UTC naive antes de consultar, y la gráfica agrupa
  con `date_trunc(unidad, fecha - 5 h)` (decisión del 2026-09-30; con días
  UTC, "Hoy" iba de 19:00 a 19:00). El backend devuelve instantes en ISO
  (UTC naive); la etiqueta
  legible la arma el frontend con Intl. Lo cubre
  `tests/test_panel_dashboard.py`. `/dashboard/avisos` devuelve
  el panel de avisos: cada regla es una función pequeña en
  `app/modules/dashboard/avisos.py` (stock agotado, stock bajo el mínimo,
  variación de ventas ±20 % frente a la semana anterior, pedidos abiertos
  sin avanzar 3+ días y el más vendido de la semana), calculada con datos
  reales del tenant. El backend no conoce rutas del frontend: devuelve
  `enlace: {recurso, id}` y `modules/dashboard/avisos.js` lo convierte en
  URL. Si ninguna regla dispara, el panel dice que todo está en orden —
  nunca se muestra vacío. Lo cubren `tests/test_avisos.py` y
  `PanelAvisos.test.jsx`.
- Migraciones Alembic: `init`, `compras`, `ventas`,
  `marcas_pedidos_permisos`, `proveedor_tipo_persona`,
  `proveedor_productos_movimientos`, `indices_de_listados`,
  `permisos_por_rol`, `aceptaciones_legales`, `fase1_restaurante`,
  `fase2_carta_insumos_recetas`, `fase3_conteos`, `fase4_ordenes`, `fase6_caja`. Correr
  `alembic upgrade head` tras hacer pull. Cada cambio de modelo lleva su
  migración.
- **Legal (2026-09-30, BORRADORES pendientes de abogado)**: Política de
  tratamiento de datos y Términos en `/legal/privacidad` y `/legal/terminos`
  (textos en `frontend/src/modules/legal/textos/*.md`), pie legal en todas
  las pantallas (`components/PieLegal.jsx`) con los datos de
  `config/empresa.js` (hoy marcadores POR COMPLETAR). El registro exige la
  casilla de aceptación (también el backend: 422) y guarda versión y fecha
  en `aceptaciones_legales`; versiones en `backend/app/core/legal.py` +
  espejo `frontend/src/config/legal.js`. Sin cookies ni servicios de
  terceros en el navegador: agregar uno obliga a revisar la decisión de no
  tener banner. Todo en `docs/legal/README.md`.
- Frontend: React + Vite + Tailwind v4. **Marco monocromático (2026-10-01,
  sustituye al panel flotante de la maqueta)**: sidebar blanco a toda altura
  con secciones, píldora activa gris, badges numéricos (de
  `/dashboard/avisos`, compartido por `context/AvisosContext.jsx`) y bloque
  de usuario; barra superior blanca con píldoras de estado
  (`components/shell.css`, `Sidebar.jsx`, `BarraSuperior.jsx`); grupos
  desplegables
  (decisión del 2026-09-27: TODOS cerrados al cargar o recargar, sin
  recordar nada ni abrirse solos por la ruta, y un solo grupo abierto a la
  vez; lista densa de ~30 px por ítem), y en pantallas angostas cajón lateral
  que entra con `transform` más barra inferior. **Una pantalla con ruta propia
  por acción** en todos los módulos: listado `/x`, crear `/x/nuevo`, detalle
  `/x/:id`, editar `/x/:id/editar` (compras y ventas no tienen editar). Cada
  archivo `modules/<m>/XPage.jsx` exporta `XLista`, `XNuevo`, `XDetalle`,
  `XEditar` y se registran en `App.jsx`. Tablas con buscador + paginación
  (`useListadoPaginado` + `TablaRecurso`), y el dashboard
  (`modules/dashboard/DashboardPage.jsx` + `dashboard.css` +
  `components/charts/GraficaRendimiento.jsx`).
- Plan inicial de un tenant nuevo: `settings.PLAN_POR_DEFECTO` (hoy
  `pro_ia`). Con `basico` el sidebar oculta Compras y Ventas — así se
  "perdieron" los módulos una vez.
- Docker Compose en `infra/` levanta Postgres + backend + frontend juntos.
- Script `automatizaciones/deploy/alta_tenant.py` crea un tenant nuevo con
  su admin desde línea de comandos.
- Script `automatizaciones/deploy/seed_demo.py` (idempotente) carga datos de
  demostración en una empresa: 5 categorías, 5 marcas, 5 proveedores
  (jurídicos con NIT/DV válido y naturales con CC/CE), 5 productos, 8 compras
  confirmadas, 9 ventas (una por mes en los últimos 5 meses, esta semana,
  ayer y hoy) y 2 pedidos. **Las fechas son relativas a HOY en cada corrida**
  (re-ancla los documentos de la demo): correrlo el día de una demostración
  deja ventas hoy, esta semana, este mes y en 6M/1A (`tests/test_seed_demo.py`). Pasa por los esquemas Pydantic y los
  servicios reales (el stock sale de movimientos, nunca se escribe a mano).
  Desde `backend/`: `venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py --email <correo de acceso>`.

## Estado para clientes (2026-10-02, tras integrar a main)
- **Completo y verificado**: login/registro con aceptación legal, dashboard
  (cifras, gráfica, avisos, proyección), Compras, Productos, Categorías,
  Marcas, Proveedores, Ventas, Pedidos, Usuarios, Roles (permisos por rol Y
  por plan en el backend), Sugerencias IA, exportación CSV y PDF. WCAG 2.1
  AA: 0 violaciones en 96 pantallas.
- **Riesgos antes de una demo o venta**: (1) los textos legales son
  BORRADORES y el pie muestra "[RAZÓN SOCIAL / NIT / CORREO / CIUDAD POR
  COMPLETAR]"; (2) no hay respaldos de base de datos, ni registro de
  auditoría de accesos, ni límite de intentos de login; (3) "Hoy" sale en
  cero si no se corre `seed_demo.py` el día de la demo; (4) los PDF usan la
  paleta anterior; (5) no hay hosting de producción definido (el contrato
  de transmisión lo exige como subencargado).
- **Decisiones del usuario (no técnicas)**: datos legales de la empresa,
  revisión por abogado, precios y módulos exactos por plan, plazos de
  portabilidad/soporte en los términos, proveedor de hosting, política de
  respaldos y retención, y si se quiere auditoría de accesos.
- **Entorno**: Docker Desktop debe estar encendido (Postgres). Para dejar
  el producto corriendo desde una sesión de Claude: `.claude/launch.json`
  (`tavo-backend` en 8002, `tavo-frontend-dev` en 5175), no procesos de
  terminal.

## Próximas tareas técnicas (en orden sugerido)
1. ~~Aplicar los permisos de rol~~ — HECHO el 2026-09-30 (ver arriba).
2. ~~Módulo IA~~ — HECHO el 2026-10-01: `GET /ia/sugerencias`, reglas
   estadísticas locales y explicables, sin servicios externos
   (`docs/ia/README.md`).
3. ~~Exportar CSV de los listados~~ — HECHO el 2026-10-01: `?formato=csv` en
   los nueve listados (`app/core/exportar.py`), mismos filtros y permisos.
4. Pendientes que decide el usuario: respaldos de la base de datos,
   registro de auditoría de accesos y límite de intentos de login.

## Convenciones de código
- **Sin modales ni paneles laterales para crear/editar/ver.** Cada acción
  es una pantalla con ruta, `PageHeader` con `migas` y acciones arriba a la
  derecha; al guardar se vuelve al listado con una alerta (ver
  **Alertas** abajo). Piezas compartidas:
  `components/FormularioPantalla.jsx` (tarjeta + secciones + pie Cancelar/
  Guardar), `components/PantallaDetalle.jsx` (encabezado + `PantallaCarga`
  hasta que llega el registro; en recargas posteriores conserva el
  contenido), `hooks/useGuardarPantalla.js` (enviar → aviso → navigate) y
  `components/SelectorBusqueda.jsx` (búsqueda en vivo contra un endpoint
  paginado; `multiple` muestra fichas removibles; combobox ARIA 1.2 con
  flechas/Enter/Escape — sus opciones son `<li role="option">`, nunca
  botones). Lo ÚNICO que sigue
  siendo diálogo es `ModalConfirmar` (eliminar y cambiar estado); `Modal`
  aparece de una vez, sin animación, y usa `hooks/useCapaSuperpuesta.js`
  (ese hook depende SOLO de `abierto`: con `onCerrar` en las dependencias
  el foco salta en cada tecla). Registrar compra elige PROVEEDOR primero
  (`SelectorBusqueda`) y ofrece solo sus productos (`?proveedor_id=`) salvo
  que se marque "Mostrar todos".
- **Alertas (sistema único, decisión del 2026-09-21)**: toda operación de
  escritura avisa con una alerta apilable arriba a la derecha — éxito
  (`role="status"`, 4 s, borde en la tinta plena) y error (`role="alert"`,
  7 s, para dar tiempo a leer la causa), cerrable a mano. Desde la paleta
  del 2026-09-28 no hay rojo: éxito y error se distinguen por icono, rol,
  duración y texto, no por color. Viven en
  `context/AvisoContext.jsx` (pila + temporizadores) y `ui/Aviso.jsx`
  (`.alertas`/`.alerta` en `pantallas.css`), montadas una sola vez en
  `AppLayout`. Los módulos NO llaman al sistema a mano: las alertas se
  emiten en los dos embudos, `ModalConfirmar` (eliminar, cambiar estado,
  anular, confirmar) y `hooks/useGuardarPantalla.js` (crear y editar), con
  las props `mensajeExito` y `accion`. **El mensaje de error dice SIEMPRE la
  causa concreta**: `lib/errores.js` toma el `detail` del backend y lo
  muestra tal cual, nunca un genérico; los 422 se arman campo por campo y
  además se pintan bajo el campo. Del lado del backend eso lo garantiza
  `app/core/mensajes.py` y lo protege `tests/test_mensajes_error.py`.
  Pruebas del frontend: `components/ui/Aviso.test.jsx`.
- **Movimiento (decisión del 2026-09-25, sustituye a la regla de 2026-09-18
  "solo cuatro animaciones")**: la referencia es la maqueta aprobada
  `docs/dashboard-referencia.html` — de ahí salen tanto el aspecto como la
  FORMA de animar. La regla vieja prohibía el movimiento porque lo que
  había estaba mal hecho; ahora el criterio es CÓMO, no cuánto:

  a) **Nada de `backdrop-filter` sobre paneles grandes.** Era la causa del
     flashazo al cargar: obliga al navegador a rasterizar todo lo que hay
     debajo antes del primer pintado. Se reemplaza por un fondo con
     degradado semiopaco (`--marco-fondo`, `--tarjeta-fondo` en
     `index.css`): visualmente idéntico y sin coste.
  b) **Solo se animan `transform` y `opacity`** (más color, que es
     repintado barato). Prohibido `width`, `height`, `top`, `left`,
     `box-shadow`, `grid-template-rows` y `transition: all`. Las barras de
     proporción usan `scaleX` con `transform-origin: left`; el indicador de
     las píldoras usa `translateX`; el cajón lateral entra con `transform`.
  c) **No animar atributos SVG por CSS** (`d`, `cx`, `cy`, `x1`, `r`): solo
     funciona en Chrome y en Firefox salta de golpe al final. La transición
     de la gráfica entre rangos INTERPOLA los puntos en JavaScript con
     `requestAnimationFrame` y escribe el `d` ya calculado.
  d) **El punto, el halo, la línea guía y el tooltip de la gráfica NO van
     dentro del SVG**: son divs en una capa HTML encima, movidos con
     `translate3d`, para que los mueva el compositor sin repintar el SVG.
  e) **Actualizar un número no re-renderiza la pantalla**: los contadores
     animados escriben `textContent` en su nodo
     (`hooks/useContadoresAnimados.js`). Nunca estado de React por cuadro.
  f) **`pointermove` se limita a un cálculo por cuadro** con
     `requestAnimationFrame` (gráfica y `components/dashboard/TarjetaLuz`).
  g) **Cada animación corre UNA vez y se queda quieta.** Bucles permitidos,
     lista cerrada: el halo del punto de la gráfica, la flotación de los
     objetos 3D del inventario y el giro del spinner. (El ambiente de la
     pantalla de acceso —deriva y vetas— se retiró con la foto el
     2026-09-30.)
  h) **`prefers-reduced-motion` se respeta en todo**, y el bloque anula
     también los RETARDOS, no solo las duraciones: con retardos vivos un
     bloque con `--d: .28s` se queda invisible y el dashboard aparece a
     trozos.
  i) **(2026-09-28) Curvas con física, solo por token** (`index.css`, espejo
     en `lib/movimiento.js`): `--ease-suave` = `cubic-bezier(0.32, 0.72, 0, 1)`
     para entradas/salidas/color y `--resorte` (resorte rigidez 300 /
     amortiguación 30 muestreado con `linear()`) para lo que se desliza.
     Prohibidos `linear`, `ease` por defecto y rebotes; excepciones: spinner
     (`linear`) y los dos bucles (`--vaiven`). Duraciones `--dur-*`.
  j) **(2026-09-28) Salidas siempre animadas, sin librería.** La pantalla que
     se va sale con un clon de DOM inerte (`despedirVista` en `AppLayout`);
     el indicador del sidebar es UN nodo que se desliza (FLIP a mano en
     `Sidebar.jsx`); los hermanos que cambian de sitio se deslizan con
     `hooks/useDeslizarHermanos.js`. Sin Framer Motion (decisión del
     usuario: 0 KB). Detalle de cada pieza en `docs/DECISIONES.md` §5.

  Protección automatizada: `frontend/src/reglas-de-movimiento.test.js` lee
  el CSS del producto (declaraciones completas, aunque ocupen varias líneas)
  y falla si vuelve un `backdrop-filter`, una transición de layout, un
  `transition: all`, un bucle no listado, una curva que no sea token, un
  rebote, un atajo `animation` inválido (dos fill-mode: así se rompieron las
  barras de más vendidos) o si el bloque de movimiento reducido pierde los
  retardos. Si hace falta una excepción, se
  documenta ahí con su porqué; no se borra el test.

  Causas de parpadeo que NO deben volver: atenuar la vista (`opacity-60`)
  en cada fetch (StrictMode dispara los efectos dos veces en dev y se veía
  doble), contenido que entra desde opacidad 0 al reemplazar un skeleton,
  mostrar el estado vacío antes de la primera respuesta, y volver al
  skeleton en una recarga. En el dashboard el esqueleto y el contenido son
  el MISMO nodo de tarjeta (la entrada `.reveal` corre una vez) y los
  esqueletos miden exactamente lo mismo que el contenido. Reglas vigentes: `useApiResource` y
  `useListadoPaginado` descartan respuestas viejas (`version` ref) —por eso
  el doble fetch de StrictMode pinta el DOM una sola vez—, los listados
  conservan las filas mientras recargan (`cargaInicial`), y las pantallas
  de detalle/edición muestran `PantallaCarga` hasta el primer dato y luego
  nunca vuelven a él. En el dashboard, cambiar de periodo o de rango NO
  vuelve al esqueleto: los datos actuales se quedan hasta que llegan los
  nuevos, y la gráfica no se desmonta (si se remontara, volverían a correr
  sus animaciones de entrada en cada clic — eso es el parpadeo). Pruebas
  automatizadas: `CategoriasPage.test.jsx` ("nunca el estado vacío antes de
  la primera respuesta", "conserva las filas mientras recarga"),
  `DashboardPage.test.jsx` ("al recargar conserva el contenido") y
  `GraficaRendimiento.test.jsx` ("cambiar de rango NO remonta los nodos").
- **Densidad y alineación (decisión del 2026-09-19)**: pantallas compactas,
  nada de aire muerto. Todo vive en los componentes compartidos, no módulo
  por módulo. Tablas: `ui/Table.jsx` es la ÚNICA tabla del producto (la
  matriz de permisos de Roles también la usa; no crear `<table>` sueltas).
  TODO CENTRADO: cada `<th>` y cada `<td>` llevan `text-align: center` sin
  excepción por tipo de dato y `vertical-align: middle`; badges y botones
  dentro de celdas se centran con flex `justify-content: center`; la misma
  clase va en el `<th>` y en los `<td>` de la columna, así comparten ancho
  exacto. `cifra: true` solo cambia la fuente (JetBrains Mono con
  tabular-nums); `ajustar: true`, `cifra` y "acciones" no parten línea.
  **Anchos proporcionales al contenido (2026-09-30)**: ninguna columna lleva
  ancho fijo; el sobrante se reparte según lo que ocupa cada una (con el
  viejo `width: 1%` todo caía en el nombre y el dato flotaba lejos del
  resto). **La tabla pasa a tarjetas cuando NO CABE en su contenedor** (o
  bajo 768 px): `hooks/useTablaApilada.js` mide su ancho mínimo antes del
  pintado y pone `.tabla-contenedor--apilada`; las tarjetas van en rejilla
  (`auto-fill`, 18 rem). Un media query de ventana no sirve: el ancho
  mínimo va de 266 a 851 px y el disponible depende del sidebar (con él, a
  768–900 y 1180 px la página se desplazaba de lado). Lo protege
  `components/ui/Table.test.jsx`. La primera columna enlaza al detalle con `.enlace` (sin subrayado;
  solo cambia de color al pasar el mouse). Formularios: `.pantalla-estrecha` mide 720 px centrado
  en todas las pantallas (`width: 100%` obligatorio: dentro del flex de
  `.main__contenido`, `margin: auto` lo encogía a su contenido y los
  formularios iban de 298 a 720 px) (encabezado incluido); `PageHeader volver=` pinta la flecha de retroceder
  al listado (obligatoria en crear/editar/detalle); campos cortos
  (documento, teléfono, NIT, precio, cantidad, fecha) a media columna con
  `.fila-campos` (o `.fila-campos--tres`), largos a ancho completo;
  etiqueta a 5 px del control, 16 px entre campos, ~28 px entre secciones,
  controles de 36 px, textarea de 3 filas, Cancelar/Guardar juntos a la
  derecha. Los formularios NO tienen control de estado (activo/inactivo):
  un registro nace activo y el estado se cambia solo desde la tabla o el
  detalle con su diálogo. Detalle: `ui/Detalle.jsx` es una fila por dato
  (etiqueta 11 rem | valor), nunca un formulario deshabilitado.
- **Bloqueo de entrada al teclear**: `Input` con `permitir=` ("nombre",
  "entero", "decimal", "digitos", "alfanumerico", "sku", "nit",
  "telefono", "documento_nit", "correo"), implementado en
  `lib/entrada.js` sobre el `beforeinput` NATIVO y `paste` (no el
  sintético de React, que no trae inputType). La tecla inválida no produce
  nada; las máscaras (teléfono "300 123 4567", NIT "900123456-7") se
  formatean sin mover el cursor; nunca se reescribe el value en onChange.
  Con `permitir` el input es siempre type="text" (number/email no permiten
  controlar el cursor). Pydantic sigue validando en el backend.
- **Paleta MONOCROMÁTICA (decisión del 2026-10-01, sustituye a la
  Espresso/Marfil, que queda como histórica en DECISIONES.md §2)**: cero
  color, solo blanco, negro y grises. Claro (principal y por defecto):
  `#EDEDF0` fondo, `#FFFFFF` tarjetas, `#F7F7F9` relleno interior, `#F1F1F4`
  sutil/píldora activa, `#E4E4E9` bordes, `#F0F0F3` divisorias, `#D4D4DA`
  eje/hover, `#6B6B76` secundario, `#52525B` terciario, `#3F3F46` nav,
  `#18181B` principal/botón. Oscuro: `#0A0A0B`, `#141416`, `#1C1C1F`,
  `#232327`, `#2A2A2F`, `#8A8A94`, `#F4F4F5`. Los valores viven SOLO en
  `index.css` (paleta → roles por modo → capa de tenant); los componentes
  usan roles (`--texto`, `--relleno`, `--borde`…), nunca un token de paleta.
  Jerarquía solo con valor y peso; positivo/negativo por intensidad y
  SIEMPRE con ▲/▼. Tarjetas de 16 px, borde de 1 px, SIN sombras. Lo
  protege `src/paleta.test.js` (incluido "cero tinte"). Los SVG 3D salen de
  `scripts/generar-renders-3d.py` con la misma paleta. Los PDF
  (`app/core/pdf.py`) siguen con el esquema claro anterior.
- **Validación en dos capas con los mismos mensajes en español**:
  `backend/app/core/validaciones.py` (manda) y su espejo
  `frontend/src/lib/validaciones.js` (Zod). Formularios con
  `hooks/useFormulario.js`: valida al salir del campo, errores en rojo
  bajo el campo, Guardar deshabilitado con errores visibles, foco al
  primer inválido en orden visual, y los 422 del backend se pintan por
  campo. Reglas: nombres de persona solo letras/tildes/apóstrofes (2–80);
  nombres de ítem (producto, categoría, marca, rol, razón social, cliente)
  con el mismo alfabeto que los de persona —letras, tildes, ñ, espacios y
  apóstrofe, sin dígitos ni símbolos (decisión del 2026-09-27)— y sin
  espacios al borde; correo real en
  minúsculas; teléfono colombiano (3XXXXXXXXX o 60XXXXXXXX); NIT con
  dígito de verificación DIAN calculado; documentos por tipo (CC, CE, PA,
  TI); precios positivos con 2 decimales hasta 999.999.999,99; stock 0 a
  1.000.000; cantidades 1 a 100.000; fechas de compra/venta no futuras y
  entrega de pedidos no anterior a hoy. Proveedores tienen tipo de persona
  (natural/jurídica) con formulario condicional; el backend limpia los
  campos del otro tipo (`_limpiar_por_tipo`).
- **Imágenes 3D**: `components/Imagen3d.jsx` con SVG locales en
  `src/assets/3d/` (CC0, generados por `frontend/scripts/generar-renders-3d.py`),
  estáticas y solo en el detalle de producto. Nunca enlaces externos.
- Nombrar entidades de negocio en español (Usuario, Rol, Compra, Venta) para
  que el dominio del código hable el mismo idioma que el catálogo comercial.
- Todo endpoint nuevo que toque datos de negocio: recibir `tenant_id` desde
  el token de auth, nunca desde un parámetro de query que el cliente pueda
  manipular.
- Variables sensibles siempre en `.env` (ver `.env.example` en backend y
  frontend), nunca hardcodeadas.
- **Configuración y arranque en máquinas nuevas (2026-09-27)**: `DATABASE_URL`
  y `SECRET_KEY` son OBLIGATORIAS (sin valor por defecto); `ENV` solo admite
  `development`/`production`; en producción se rechaza la `SECRET_KEY` de
  ejemplo. El `.env` se lee SIEMPRE de `backend/.env` (ruta absoluta, no la
  carpeta de arranque). Si falta algo, `cargar_settings` en
  `app/core/config.py` sale con código 1 y un mensaje en español que dice
  qué copiar — nunca el ValidationError de pydantic. Igual en el frontend:
  el plugin `exigirVariablesDeEntorno` de `vite.config.js` detiene `dev` y
  `build` si falta `VITE_API_URL`. Cada variable nueva de `Settings` va
  documentada en `backend/.env.example` (lo exige `tests/test_config.py`).
  Arranque desde cero: `automatizaciones/setup.ps1` / `setup.sh`
  (idempotentes; cuenta de prueba `demo@jscompany.co` / `Demo2026!`).
  Diagnóstico: `python -m app.diagnostico [--origen URL]` desde `backend/`,
  y `GET /diagnostico` solo con `ENV=development`.

## Rendimiento (medido, no estimado)
Se mide SIEMPRE sobre `npm run build` + `npm run preview` (puerto 4175),
nunca sobre `npm run dev`: el servidor de desarrollo es lento por diseño.
Mediana de 3 corridas. Estado al 2026-09-25, después de llevar el dashboard
a la maqueta:

- **Pantalla de entrada** (Lighthouse 12, preset desktop): puntaje 100,
  FCP 449 ms, LCP 491 ms, Speed Index 449 ms, TBT 0 ms, CLS 0,000,
  386 KB transferidos. (Antes del rediseño: 447 / 487 ms y 383 KB — los
  3 KB de más son el CSS del marco nuevo.)
- **Dashboard ya autenticado** (Lighthouse no puede iniciar sesión, así que
  se miden las mismas métricas con `PerformanceObserver` y caché fría, con
  el token sembrado en `localStorage`): FCP 116 ms, LCP 648 ms,
  **CLS 0,000**, **0 tareas largas**, 303 KB en 22 recursos. El elemento LCP
  es `h1.saludo`. CLS en cero y cero tareas largas son la prueba de que ni
  la entrada escalonada ni la gráfica desplazan o bloquean nada.

Lo que sostiene esos números (no deshacer sin volver a medir):
- **Precarga de la ruta inicial (2026-10-01, `lib/perezoso.js`)**: con
  sesión guardada, el marco y la pantalla de la ruta inicial se piden en
  paralelo con `/seguridad/me` y se pintan directo si ya llegaron (sin la
  espera de ~300 ms que React 19 aplica al revelar un `lazy()`). Medido el
  2026-10-02: LCP del dashboard 904 → 684 ms; módulos ~850 → ~580 ms.
- **CSS por ruta (2026-10-02)**: `index.css` solo trae lo de las pantallas
  públicas; el resto lo importa su ruta (`AppLayout`, `DashboardPage`,
  `GraficaRendimiento`). CSS del login 54 KB. Un CSS de ruta solo define
  selectores que empiezan por una clase propia (`css-por-ruta.test.js`).
- **Carga diferida por ruta** en `App.jsx`: login y registro se importan de
  una vez (son la entrada); el layout y cada módulo van en `lazy()`. El
  `Suspense` usa el mismo indicador que `ProtectedRoute`, para que la
  espera no estrene una forma nueva.
- **Recharts se eliminó del proyecto (2026-09-25).** La gráfica del
  dashboard es SVG propio (`components/charts/GraficaRendimiento.jsx`):
  hacía falta de todos modos para poder interpolar los puntos en JavaScript
  (Firefox no anima atributos SVG por CSS) y para sacar el punto, el halo,
  la guía y el tooltip a una capa HTML. El paquete pasó de ~109 KB gzip a
  **3,1 KB gzip**.
  Sigue vigente la regla que lo acompañaba: **nada más lleva nombre de
  paquete fijo en `manualChunks`.** En cuanto se le da uno, Vite lo mete en
  el `<link rel="modulepreload">` del HTML y se descarga hasta en la
  pantalla de inicio de sesión. La librería pesada que venga va dentro de su
  `import()` dinámico. `vendor-react` sí se agrupa: hace falta desde el
  primer pintado. `manualChunks` debe ser una FUNCIÓN (Rolldown/Vite 8 falla
  con un objeto).
- **Fuentes: solo el subconjunto `latin`.** Cubre todo el español. NO sumar
  `latin-ext`: los archivos por subconjunto de @fontsource no traen
  `unicode-range`, así que el navegador no puede distinguirlos y se baja
  ambos — se midió y pasó de 3 a 6 descargas de fuente.
- **Login sin foto (2026-09-30; revertido a este diseño el 2026-10-01 sobre la paleta monocromática, fondo `#0A0A0B`)**: fondo negro sólido y panel
  transparente; el LCP pasó a ser `h1.auth__titulo`. Medido (mediana de 3,
  Lighthouse desktop): puntaje 100, FCP = LCP 492 ms, TBT 0, CLS 0,
  **204 KB** transferidos (antes 386 KB con la foto). `public/fondo-auth.jpg`
  (duotono de la paleta, 187 KB, licencia Unsplash) se conserva en disco
  pero ya no se descarga; cómo volver a usarla en `docs/DECISIONES.md` §4.
- **Backend**: `tests/test_rendimiento_consultas.py` exige que cada listado
  cueste el MISMO número de consultas con 1 fila que con 10; así se detectó
  el N+1 del listado de proveedores (`selectinload(Proveedor.productos)`).
  Los índices de los listados y del dashboard están en la migración
  `indices_de_listados`: claves foráneas (Postgres no las indexa solo) más
  compuestos que empiezan por `tenant_id`, porque toda consulta de negocio
  filtra primero por empresa.
- **El panel del dashboard son puros agregados**: `/dashboard/panel` y
  `/dashboard/serie` cuestan el mismo número de consultas con una venta que
  con diez mil (los dos tramos, actual y anterior, se separan con sumas
  condicionales en la MISMA consulta, no con dos viajes a la base).

## REGLA PERMANENTE: configuración activa que NO es código muerto
En limpiezas de código (eliminar "no usado", simplificar, consolidar)
**nunca** eliminar ni reordenar lo siguiente, aunque ninguna otra parte del
código lo referencie. Son configuración activa del proyecto:

- **CORS del backend**: `configure_cors(app, settings)` y
  `app.add_middleware(CatchAllExceptionsMiddleware)` en `backend/app/main.py`
  (bloque marcado "CONFIGURACIÓN CRÍTICA"), junto con `app/core/cors.py`,
  `app/core/error_handlers.py` y `CORS_ORIGINS` en `app/core/config.py` /
  `.env`. Sin esto el frontend no puede registrarse ni iniciar sesión
  (bloqueo CORS). El orden importa: el catch-all va ANTES que
  `configure_cors()` para que las respuestas de error (401/409/422/500)
  también traigan `Access-Control-Allow-Origin`. No mover el catch-all de
  500 a `app.add_exception_handler(Exception, ...)`: pierde el header.
- **Mapa de puertos del Producto Tavo** (ver la sección del principio):
  5175 / 4175 / 8002 / 5433 / 5679, en `frontend/vite.config.js`,
  `frontend/.env.example`, `backend/.env.example` y `Settings.PORT`,
  `infra/docker-compose.yml`, `automatizaciones/dev/comun.ps1`,
  `.vscode/` y `.claude/launch.json`. Lo protege
  `backend/tests/test_mapa_de_puertos.py`.
- **`strictPort: true`** en `vite.config.js` (dev y preview): si el 5175
  está ocupado, Vite debe fallar en vez de saltar al siguiente en silencio
  (ese salto rompe CORS sin avisar).
- **Guarda de arranque** (`app/core/arranque.py`, llamada en `app/main.py`):
  `uvicorn` lanzado con otro puerto que `Settings.PORT` se detiene con un
  mensaje. Lo protege `tests/test_arranque.py`.
- **Orígenes locales de desarrollo** en `DEV_ORIGIN_REGEX`
  (`HOSTS_LOCALES` + `REDES_PRIVADAS` en `backend/app/core/cors.py`, solo
  `ENV=development`): localhost, 127.0.0.1, [::1] y la red privada, en
  cualquier puerto o sin puerto. Vite tiene `server.host: true` e imprime
  una URL "Network"; sin la red privada, abrirla daba 400 en el OPTIONS del
  login (caso real de un compañero, 2026-09-27). Lo protegen
  `tests/test_cors_config.py` y `tests/test_cors.py` (errores con header).
- **Demo por túnel** (`automatizaciones/demo/start-demo-tunel.ps1`):
  `HOSTS_TUNEL`/`allowedHosts` en `server` y `preview` de
  `frontend/vite.config.js`, `preview.port = 4175` (adicional, no
  reemplaza al 5175), el tramo de dominios de túnel (`DOMINIOS_TUNEL`) en
  `DEV_ORIGIN_REGEX` de `backend/app/core/cors.py` (solo
  `ENV=development`), el header `bypass-tunnel-reminder` en
  `frontend/src/lib/api.js` y `frontend/.env.tunnel.example`. Se comparte
  siempre la versión COMPILADA (`vite build --mode tunnel` + `vite
  preview`), nunca `npm run dev`: por el túnel los .jsx sueltos llegan
  como text/plain y el navegador los bloquea. Lo protegen
  `backend/tests/test_cors_config.py` (dominios de túnel) y
  `frontend/src/vite-config.test.js`.

Protección automatizada: `backend/tests/test_cors.py` y
`backend/tests/test_cors_config.py` fallan si se elimina o reordena la
configuración de CORS. Correr `pytest tests/test_cors.py` tras cualquier
limpieza del backend.

Reload de uvicorn en Windows: `--reload` a veces detecta el cambio
("Reloading...") pero el worker viejo (proceso hijo `multiprocessing.spawn`,
cuya línea de comando NO dice "uvicorn") nunca muere y sigue sirviendo
código viejo. Si un endpoint nuevo da 404 o un cambio no se refleja,
reiniciar con `automatizaciones/dev/start-backend.ps1`, que cierra el
reloader, los workers huérfanos y a quien tenga el 8002 — y SOLO eso: nunca
"todo python con uvicorn", que tumbaría el backend del Producto JS.

Síntoma engañoso: si el backend no está corriendo (o Postgres/Docker está
apagado), Firefox reporta la conexión rechazada como "CORS request did not
succeed". Antes de tocar la configuración de CORS, comprobar que algo
escucha en el 8002 (`automatizaciones/dev/verificar-puertos.ps1`).
