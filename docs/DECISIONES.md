# Registro de decisiones — Producto Tavo (sistema para restaurantes)

Registro fechado de las decisiones tomadas en el proyecto: qué se decidió,
qué se descartó y **por qué**. Es la memoria del proyecto: cualquier sesión
nueva (persona o agente) debe leerlo antes de tocar diseño, movimiento,
rendimiento o configuración.

**Regla de mantenimiento:** cada decisión nueva se agrega aquí, con fecha, en
el mismo trabajo en que se toma. Si una decisión sustituye a otra, la vieja
NO se borra: se marca como sustituida y se enlaza la nueva.

Las pruebas que protegen cada decisión se citan al lado; si una prueba falla,
la decisión se está rompiendo.

Este producto es una **derivación del Producto JS** (§0). Las entradas
anteriores al 2026-10-12 son la historia heredada y siguen vigentes salvo
que una entrada nueva diga lo contrario.

---

## Índice

0. [Derivación del Producto JS](#0-derivación-del-producto-js)
1. [Configuración crítica que NO se borra](#1-configuración-crítica-que-no-se-borra)
2. [Paleta](#2-paleta)
3. [Tipografías](#3-tipografías)
4. [Layout y estructura](#4-layout-y-estructura)
5. [Movimiento](#5-movimiento)
6. [Rendimiento](#6-rendimiento)
7. [Interfaz y convenciones](#7-interfaz-y-convenciones)
8. [Herramientas (skills) instaladas](#8-herramientas-skills-instaladas)
9. [Historial](#9-historial)

---

## 0. Derivación del Producto JS

### 2026-10-12 — Producto Tavo nace como copia del Producto JS

- **Qué:** sistema para restaurantes, multi-tenant. Primer cliente: "Donde
  Tavo" (restaurante en una universidad, 12 años sin sistema), que será su
  primer TENANT; el código queda genérico para venderlo a otros restaurantes.
  Nombre provisional del producto: "JS Restaurante".
- **De dónde sale:** `git archive` del commit `8146ea0` del Producto JS
  (`C:\Users\camac\Desktop\Producto JS`, repo `Camacho077/Producto-JS`), más
  `.claude/settings.local.json` (hook de Impeccable) y el binario de
  Impeccable. Fuera: venv, node_modules, dist, .vite, `.env`, logs,
  `.claude/worktrees` y bases locales. Repositorio git nuevo, sin historial
  ni remoto compartido; su primer commit es la copia sin cambios.
- **Regla:** el Producto JS no se toca bajo ninguna circunstancia desde este
  trabajo.
- **Se hereda sin tocar:** login y registro, alertas, validaciones (incluido
  el bloqueo al escribir), permisos por rol y por plan en el backend,
  documentos legales y política de datos, auditoría de cookies, sistema de
  diseño monocromo, tipografías, animaciones y reglas de rendimiento,
  gráficas, componentes compartidos, CORS y aislamiento entre empresas. Todo
  lo registrado en §1–§9 sigue vigente: es la historia heredada (las fechas
  anteriores al 2026-10-12 son del Producto JS).
- **Cambia:** branding (archivo de branding con logo provisional y el nombre
  "JS Restaurante"), datos de prueba y módulos: Marcas se QUITA (borrado de
  verdad: rutas, tablas con migración, tests, menú); Compras → compra de
  INSUMOS; Ventas → Caja; Pedidos → Órdenes de pedido con comanda;
  Proveedores, Usuarios, Roles, Dashboard e IA se adaptan.
- **Plan por fases** (numeración del "super prompt" del usuario del
  2026-10-12; una rama por fase, tests + build al cerrar cada una; las ramas
  se apilan: cada una sale de la anterior y nada va a `main` sin aprobación):
  0 verificar la base · 1 adaptar la base al restaurante (branding, sin
  Marcas, Ajustes) · 2 catálogo, insumos y recetas (costo y margen) ·
  3 inventario, compras de insumos y carga inicial · 4 órdenes y comanda
  (impresión 80 mm detrás de una interfaz; se pregunta impresora y equipo
  antes de cerrar) · 5 pantalla de cocina · 6 caja, ventas y gastos ·
  7 vistas por rol y PWA · 8 dashboard y reportes · 9 IA · 10 dictado por
  voz · 11 n8n · 12 datos de prueba · 13 pruebas y cierre.

### 2026-10-12 — Fase 0 verificada (sesión del super prompt)

Repositorio propio (`Camacho077/Producto-Tavo`, sin remoto compartido),
puertos 5175/4175/8002/5433/5679, contenedores y volúmenes `tavo-*` con
`infra-db-1` del Producto JS intacto, `strictPort`, `Settings.PORT = 8002`,
`verificar-puertos.ps1` (detecta reserva de Windows, proceso y contenedor),
CORS con `Access-Control-Allow-Origin` también en los 401, y login 200.
Línea base: backend 499 pruebas, frontend 227. Para desarrollar se usan
backend y Vite LOCALES (`.claude/launch.json`); los contenedores
`tavo-backend`/`tavo-frontend` llevan el código del momento en que se
construyó la imagen y se detienen mientras tanto (Postgres y n8n siguen en
Docker).

### 2026-10-12 — Fase 1: la base adaptada al restaurante

**Hecho**
- **Branding en un archivo**: `frontend/src/config/branding.jsx` (nombre
  "JS Restaurante", lema y logo provisional: una campana de servicio en un
  sello, monocromo, `currentColor`). Espejo del nombre en
  `backend/app/core/branding.py` (PDF, título de la API) y
  `tests/test_ajustes.py` exige que coincidan. Login, registro, sidebar,
  barra y `<title>` ya dicen "JS Restaurante"; "JS Company" queda solo como
  la empresa que presta el servicio (soporte, documentos legales).
- **Marcas eliminada de verdad**: modelo, rutas, esquemas, pantalla, menú,
  permiso, seed y pruebas; migración `c1f0a1b2c3d4` borra
  `productos.marca_id`, la tabla `marcas` y el permiso guardado en los roles.
- **Ajustes del restaurante** (módulo `ajustes`, backend y frontend):
  datos del negocio (nombre, NIT con DV, dirección, ciudad, teléfono,
  correo, logo), configuración operativa (tipos de orden, orígenes, medios
  de pago, impuesto al consumo, propina sugerida, alerta y sonido de cocina,
  jornada, impresoras) y mesas por zona. Pantallas: `/ajustes` (detalle),
  `/ajustes/negocio/editar`, `/ajustes/operacion/editar`, `/ajustes/mesas`
  (+ nuevo/detalle/editar) y `/ajustes/zonas` (+ nuevo/detalle/editar).
- Menú: "Ventas" se presenta como **Caja** y "Pedidos" como **Órdenes**
  (las rutas y permisos viejos siguen hasta que sus fases los reemplacen),
  grupo nuevo **Ajustes**. Roles de ejemplo de una empresa nueva: Cajero,
  Mesero y Cocinero (las empresas existentes conservan sus roles).

**Decidido**
- **Imágenes procesadas en el servidor y guardadas en la base**
  (`imagenes`, `app/modules/imagenes`): JPG/PNG/WebP de hasta 5 MB y 40
  megapíxeles, formato real comprobado con Pillow (no el Content-Type),
  orientación EXIF, platos recortados al cuadrado a 640 px y logos dentro de
  600 × 300, todo a WebP calidad 80 (medido: PNG 1200×500 de 32 KB → 3,3 KB).
  Se suben como cuerpo CRUDO con su Content-Type (sin `python-multipart`).
  Se sirven por `GET /imagenes/{id}` **sin sesión** (un `<img>` no manda el
  token): son fotos de la carta y logos, el id es un UUID aleatorio y la
  respuesta es inmutable (reemplazar crea otra imagen y borra la vieja).
  `pillow==12.3.0` queda fijado (ya venía con reportlab).
- **Configuración en `Tenant.configuracion` (JSON) leída SIEMPRE por su
  esquema** (`ConfiguracionRestaurante`): cada campo tiene valor por
  defecto, y si algo guardado deja de validar se descarta ESE campo, no
  todo. `/seguridad/me` la entrega junto a los datos del negocio: la toma
  de pedidos y la comanda la usan aunque el rol no pueda ver Ajustes.
- **Jornada**: empieza a la hora de inicio EN COLOMBIA; antes de esa hora
  sigue siendo la jornada del día anterior (un servicio que pasa de
  medianoche no reinicia el consecutivo). `fecha_jornada` /
  `limites_jornada` en `app/modules/ajustes/services.py`.
- **Nombres de la carta** (platos, insumos, combos, zonas, impresoras,
  negocio): letras, dígitos y `. , - + & / ( ) %` ("Gaseosa 400 ml",
  "Pollo 1/4"); filtro de teclado `permitir="carta"`. Mesas: letras,
  dígitos, espacio y guion, en mayúsculas (`permitir="mesa"`). Los nombres
  de persona y de categoría siguen con la regla de solo letras.
- **Impresoras**: conexión `navegador` (diálogo de impresión, CSS de 58/80
  mm) o `ip` (ESC/POS directo, para el conector futuro). El valor es "ip" y
  no "red": la guarda de paleta trata "red" como un color con nombre.
- El mesero no edita ajustes pero ve mesas (`mesas.ver`).

**Sigue (fase 2)**: catálogo de platos (sin stock: el inventario pasa a los
INSUMOS), modificadores, combos, imágenes de plato, insumos con unidades y
recetas con costo, margen y porcentaje de costo.

### 2026-10-12 — Fase 2: carta, insumos y recetas (el inventario pasa a los insumos)

**Alcance real (cambio respecto al plan):** en cuanto los platos tienen
receta, el "stock de un plato" deja de tener sentido: lo que se gasta son los
insumos. Por eso esta fase también tuvo que llevar a insumos las COMPRAS
(antes compraban productos) y hacer que la venta manual heredada descuente
POR RECETA. La fase 3 queda para lo que falta del inventario (mermas,
conteos, historial general, alertas, carga inicial).

**Hecho**
- Backend en tres módulos: `catalogo` (categorías, platos y combos con
  receta y modificadores; `/catalogo/...`), `inventario` (insumos y sus
  movimientos; `/inventario/...`) y `compras` (proveedores ↔ insumos y
  compras de insumos). Migración `d2a0b1c2d3e4`: los productos pierden
  stock, mínimo y costo de compra; se borran `movimientos_inventario` y
  `proveedor_productos`; las compras viejas (de productos de reventa) se
  eliminan porque no tienen equivalente en insumos (no había datos de ningún
  restaurante).
- Frontend: grupo **Carta** (Platos `/carta`, Combos `/carta/combos`,
  Categorías `/carta/categorias`) y grupo **Inventario** (Insumos,
  Compras y Proveedores bajo `/inventario/...`). Editor de líneas genérico
  (`components/EditorLineas.jsx`) para receta, modificadores, platos de un
  combo e insumos de una compra; `components/FotoPlato.jsx`.
- Dashboard, avisos e IA adaptados: inventario a costo por grupo de insumo,
  avisos de insumos agotados (solo los que están en alguna receta) y bajo
  el mínimo, y en la IA: lista de compras por consumo, insumos quietos,
  platos con % de costo alto (con el insumo que más pesa) y proveedor más
  barato por UNIDAD del insumo (compara g contra kg).
- Seed de demostración de restaurante (12 insumos, 9 platos con receta y
  modificadores, combo de estudiante, 3 proveedores, compras y ventas que
  descuentan por receta). La fase 12 lo amplía.
- PDF monocromo (antes Espresso/Marfil) y genérico (columnas de
  descripción y detalle): cierra uno de los riesgos heredados.

**Decidido**
- **Unidades**: el insumo vive en UNA unidad (kg, g, L, ml, unidad); compras
  y recetas pueden escribirse en otra de la misma familia y el backend
  convierte (`inventario/unidades.py`, espejo `lib/unidades.js`). Entre
  familias, error con la causa.
- **Costo del insumo por promedio ponderado** de las compras; las salidas se
  valoran al costo vigente y ese `valor` del movimiento es el costo de lo
  vendido. Anular una compra saca su peso del promedio si tiene sentido; si
  no, conserva el costo vigente. El costo se puede fijar a mano (antes de
  la primera compra) solo con `costos.ver`.
- **Costo del plato EN VIVO** (no se guarda): sube un insumo y todos los
  platos que lo usan se recalculan solos. La venta guarda el costo unitario
  de cada línea en ese momento (`venta_items.costo_unitario`). Un plato sin
  receta muestra "sin dato", nunca costo cero.
- **Margen sobre el precio SIN impuesto al consumo** cuando la carta lo
  incluye (8 %: no es ingreso del restaurante).
- **Merma** por línea de receta: se descuenta cantidad × (1 + merma %).
- **Modificadores**: "sin" gratis que deja de descontar un insumo de la
  receta; "extra" con precio que suma UN insumo con su cantidad (la "receta
  del extra"). Un extra con varios insumos queda fuera por ahora.
- **Combos** = productos de tipo combo con sus platos, precio especial,
  vigencia (desde/hasta) y días de la semana; al venderse, cada plato
  descuenta su receta. Un combo no lleva otros combos.
- **Agotado hoy** = `agotado_fecha` de la jornada actual: vuelve solo al
  empezar la siguiente.
- **Imagen por defecto**: el render 3D monocromo del producto (los SVG CC0
  ya aprobados), estable por plato; con foto, la foto (WebP 640 px).
- **No se vende lo que no hay**: si un insumo no alcanza, 409 con la causa
  exacta ("quedan 200 g de Queso y la venta necesita 300 g") y, en `datos`,
  los faltantes (para ofrecer "agotado" en la fase 4). Opción por empresa
  `vender_sin_existencias` (por defecto apagada) para mientras se carga la
  bodega real. Los insumos se leen con `SELECT … FOR UPDATE`.
- **Los movimientos llevan la fecha del documento** (una compra registrada
  con fecha de ayer entró ayer): sin esto el consumo y la IA quedaban en el
  día equivocado.
- **Permisos nuevos**: `insumos` (CRUD) y `costos.ver` (costo, margen, % de
  costo y costo de insumos; un cajero o mesero no lo tienen). `productos` se
  conserva como clave pero significa "la carta".
- **Planes provisionales**: Carta y Caja desde Básico (sin ellas no se
  opera); Inventario desde Estándar. Precios y módulos exactos: decisión
  del usuario.
- Nombres de la carta e insumos admiten dígitos y signos; las categorías
  también pasaron a esa regla y llevan `orden` (pestañas al tomar pedidos).

**Sigue (fase 3)**: mermas y daños con motivo, ajuste por conteo físico,
historial general de movimientos, alertas de stock bajo y carga inicial
desde plantilla Excel/CSV con validación fila por fila.

### 2026-10-12 — Fase 3: mermas, conteos físicos, historial y carga inicial

- **Merma** (`POST /inventario/insumos/{id}/merma`, pantalla
  `/inventario/insumos/:id/merma`): salida con motivo cerrado (vencido,
  dañado, derramado, error de preparación, otro + detalle obligatorio), en
  cualquier unidad de la familia del insumo. NO puede dejar la existencia
  negativa: si en la bodega hay menos de lo que dice el sistema, lo que
  corresponde es un conteo, y el 409 lo dice.
- **Conteo físico** (`/inventario/conteos`, consecutivo `CON-000001` por
  empresa): por cada insumo contado se guarda sistema / contado /
  diferencia / valor a costo, y la diferencia queda como movimiento
  `ajuste` que apunta al conteo. Los insumos que se dejan vacíos no se
  tocan; sin diferencia no hay movimiento. Tablas `conteos` y
  `conteo_items` (migración `e3b1c2d3e4f5`).
- **Historial general** (`GET /inventario/movimientos`, pantalla
  Inventario → Movimientos): todos los movimientos con filtros por tipo,
  insumo y días de Colombia (`desde`/`hasta`), búsqueda por insumo,
  documento, motivo o persona, y CSV. El valor a costo solo con `costos.ver`.
- **Permiso nuevo `movimientos`** (ver: historial y conteos; crear: mermas
  y conteos), grupo Inventario. Un cocinero puede registrar mermas sin ver
  costos.
- **Carga inicial** (`/inventario/carga-inicial`): el sistema genera la
  plantilla (Excel con hojas Insumos, Platos y Recetas, ejemplos, listas de
  unidades y Sí/No; o un CSV por hoja, `;` y coma decimal). Subir el archivo
  primero lo REVISA fila por fila (hoja, fila, columna, qué corregir, en
  español: los errores de Pydantic pasan por `traducir_error`) sin guardar
  nada; `aplicar` vuelve a revisar y guarda TODO en una transacción o nada
  (422 con el informe). Por nombre (sin mayúsculas): lo existente se
  actualiza, lo nuevo se crea; la existencia entra como movimiento
  ("inicial" o "ajuste" por la diferencia, motivo "Carga inicial"), nunca
  escrita directo; las recetas de los platos del archivo se REEMPLAZAN.
  Platos o recetas exigen además `productos.crear` (403 con la causa).
  El archivo va como cuerpo crudo (no multipart): sin dependencia nueva
  más allá de `openpyxl`.
- **Alertas de stock bajo**: ya existían (aviso del dashboard e insignia del
  sidebar sobre insumos bajo el mínimo); el badge cuenta ahora insumos.
- `literal_error` de Pydantic se traduce a "Debe ser una de estas
  opciones: …" en toda la API.
- Encabezado de página: las acciones envuelven en pantallas angostas
  (`max-width: 100%`); con cuatro botones el detalle de insumo se salía
  144 px a 375 px.

**Sigue (fase 4)**: órdenes de pedido con comanda.

### 2026-10-12 — Fase 4: órdenes de pedido con comanda

- **Módulo `ordenes`** (backend y frontend) reemplaza a los Pedidos del ERP,
  que se BORRAN (tablas, rutas, pantalla, pruebas). Migración
  `f4c2d3e4f5a6`; los roles guardados pasan su permiso `pedidos` a
  `ordenes`. Permiso `ordenes`: ver, crear (tomar pedidos), editar
  (agregar/quitar platos y datos), cambiar_estado (entregar), anular.
  Grupo "Órdenes" desde el plan Básico.
- **Modelo**: `Orden` (consecutivo POR JORNADA, único por empresa y
  jornada, con candado de transacción `pg_advisory_xact_lock`; la jornada
  empieza a la hora de inicio de Ajustes en hora de Colombia), `Comanda`
  (cada envío a cocina: la 1 es el pedido, las siguientes solo lo
  agregado; sin nada para cocina nace "lista"), `OrdenItem` (precio con
  extras, costo por receta del momento y `consumo`: lo que sacó de cada
  insumo) y `OrdenEvento` (línea de tiempo con quién y cuándo).
- **Enviar = una transacción**: numera, descuenta los insumos (movimiento
  "venta" con documento `ORD-aammdd-nnn`) y deja la comanda. Si un insumo
  no alcanza: 409 "No se pudo enviar la orden: quedan 200 g de Queso y la
  orden necesita 300 g." y en `datos` los faltantes y los platos que los
  usan; la pantalla ofrece "Marcar «X» agotado hoy" (`POST
  /ordenes/agotados`, con el permiso de tomar pedidos). Nada se guarda y
  el consecutivo no se gasta.
- **Quitar un plato o anular la orden** (antes de cobrar) exige motivo y
  devuelve EXACTAMENTE lo que salió (movimiento `anulacion_orden`, desde el
  `consumo` guardado, aunque la receta haya cambiado). Lo último que queda
  no se quita: se anula la orden. Las comandas anuladas salen de cocina.
- **Estado de cocina de la orden** = el de su comanda más atrasada.
  Tablero: Activas (algo sin entregar), Entregadas, Anuladas; jornada
  visible ("Jornada del lunes 12/10 · 5 en curso") y refresco cada 20 s.
  Mesas: libre / ocupada (algo sin entregar) / por cobrar (todo
  entregado), calculado de las órdenes abiertas (no se guarda).
- **Tomar pedido** (`/ordenes/nueva`): tipo (Local con mesa, Para llevar,
  Domicilio con dirección y teléfono) y origen según Ajustes, cuadrícula de
  mesas por zona con su estado, carta por categorías con buscador, tocar
  un plato lo agrega, modificadores como fichas de un toque, nota por
  plato, botones de cantidad de 44 px. El borrador se guarda en
  localStorage hasta enviarlo. Agregar a una orden enviada reutiliza la
  pantalla (`/ordenes/:id/agregar`).
- **Impresión detrás de una interfaz** (`lib/impresion.js`): `imprimir(
  documento, impresora)` con un conector por tipo de conexión. Hoy solo
  existe el del NAVEGADOR (iframe invisible + CSS de impresión de 58/80
  mm); el de IP (ESC/POS) responde con un mensaje claro. La comanda sale
  sola al enviar si hay una impresora activa para comandas, y se
  reimprime desde el detalle. Solo lleva lo que va a cocina, en grande,
  con modificadores en mayúsculas y la nota.
- **Respuesta del usuario (2026-10-12)** a la PREGUNTA de impresora y
  equipos: "Aún no se sabe". Queda la impresión desde el navegador; el
  conector directo se agrega cuando el restaurante elija la impresora.
- Aviso del dashboard "pedidos sin avanzar" → **"comandas demoradas en
  cocina"** (entrantes o en preparación más allá de `alerta_cocina_minutos`);
  la cifra `pedidos_abiertos` pasa a `ordenes_abiertas`.
- `ModalConfirmar` acepta `deshabilitado` (confirmar apagado mientras
  falta el motivo).
- La Caja todavía es la venta heredada: cobrar una orden llega en la fase 6.

**Sigue (fase 5)**: pantalla de cocina.

### 2026-10-12 — Fase 5: pantalla de cocina

- **Módulo `cocina`** (backend `app/modules/cocina`, frontend
  `modules/cocina`, ruta `/cocina`), permiso `cocina` (ver; cambiar_estado =
  Tomar y Finalizar), grupo propio desde el plan Básico. El rol de ejemplo
  Cocinero tiene SOLO `cocina`: no toma pedidos ni ve órdenes, inventario
  ni caja.
- La cocina trabaja COMANDAS: Entrantes → En preparación (Tomar) → Listos
  (Finalizar); de Listos sale cuando el mesero ENTREGA. Cada paso guarda
  quién y a qué hora, y queda en la línea de tiempo de la orden. Un cambio
  que otra persona ya hizo responde 409 ("quizá otra persona la movió").
- Solo llegan los platos que van a cocina; la venta directa no. Lo anulado
  se ve tachado con el motivo y, durante 15 min, como aviso arriba; una
  orden anulada sale de la pantalla.
- **En vivo por consulta corta cada 5 s**, sin WebSocket (funciona igual
  detrás del túnel de demos y de cualquier proxy) y solo con la pestaña
  visible; los temporizadores avanzan cada 15 s (estado de React cada 15 s,
  nunca por cuadro). Pasado `alerta_cocina_minutos` la tarjeta se marca con
  borde grueso, cabecera invertida y ▲ (sin color, como todo el producto).
- **Sonido opcional**: dos tonos con Web Audio (sin archivos), se activa con
  un botón (los navegadores no suenan sin un toque previo) y se recuerda en
  el dispositivo; Ajustes puede apagarlo para toda la empresa.
- Tipografía para leer a un metro: número de orden 30 px, platos 20 px,
  modificadores 17 px en mayúsculas. Tablet: 3 columnas; celular: apiladas.

**Sigue (fase 6)**: caja, ventas y gastos.

### 2026-10-12 — Fase 6: caja, cobros, cierres y gastos

- **Módulo `caja`** (reemplaza a `ventas`, que se borra): cobrar una orden
  la convierte en VENTA con **comprobante interno** consecutivo
  (`CI-000001`). Se puede cobrar toda la orden o parte (**dividir la
  cuenta** por platos o dentro de una línea: 1 de 2 sándwiches; la línea se
  parte y el resto queda por cobrar). Varios medios de pago por cuenta; en
  efectivo se guarda lo recibido y las devueltas. Los pagos deben sumar
  EXACTO el total más la propina (409 "faltan $ 800").
- **Propina**: voluntaria, nunca automática (botón con el % sugerido de
  Ajustes); no es ingreso del restaurante y va aparte en el cuadre.
- **Impuesto al consumo** según Ajustes: incluido en el precio (se
  desglosa: base + impuesto = precio de carta), sumado, o no aplica.
  `total` de la venta = lo consumido con impuesto; la propina aparte.
- **Caja del día** (`cajas`): se abre con una base; el cuadre se calcula
  SIEMPRE desde los pagos y gastos guardados: efectivo esperado = base +
  cobros en efectivo − gastos pagados desde la caja. Al cerrar se cuenta
  por medio de pago; si algo no cuadra el MOTIVO es obligatorio (422 con
  el detalle por medio) y queda en el reporte del cierre. Una sola caja
  abierta por empresa. Cobrar exige caja abierta.
- **Anular un cobro** (con motivo) solo mientras su caja siga abierta: los
  platos vuelven a quedar por cobrar; los insumos NO vuelven (la comida se
  sirvió — para eso se anula la orden, que ya no se puede si tiene cobros).
- **Gastos** (módulo `gastos`): arriendo, servicios, nómina, gas, aseo,
  mantenimiento, impuestos, otros; fecha (día de Colombia, no futura),
  valor y medio. Un gasto en efectivo puede salir de la caja abierta y
  cuenta en su cuadre; si esa caja ya se cerró, el gasto no se edita ni se
  borra.
- **Permisos**: `ventas` (ver, crear = cobrar, anular), `caja` (ver,
  cambiar_estado = abrir y cerrar), `gastos` (CRUD). Migración
  `a6d4e5f6a7b8`: `ventas.cambiar_estado` de los roles guardados pasa a
  `caja`. El Cajero de ejemplo cobra y cierra, no anula ni ve gastos.
- **Una orden para llevar puede cobrarse antes de entregarse**: sigue en
  cocina y en "Activas" hasta que se entrega (las vistas de cocina y del
  tablero ya no exigen orden "abierta", sino "no anulada").
- Comprobante imprimible en 80 mm (`htmlComprobante` en
  `lib/impresion.js`, impresora de facturas o la del navegador) y en PDF.
- Las ventas de demostración anteriores se perdieron con la migración (el
  producto aún no tiene datos reales); sus movimientos de inventario se
  conservan para que la existencia no cambie. El seed vende ahora por la
  vía real (orden + cobro).
- Se borraron `VentasPage.jsx`, `ItemsEditor.jsx`, `esquemaItems` y la
  validación de "fecha de entrega" (solo la usaban ventas y pedidos del
  ERP). El CSV de un listado sin esquema exporta las filas ya
  serializadas (`app/core/exportar.py`).

**PREGUNTA AL USUARIO (tema legal), resuelta según el plan**: en Colombia
muchos restaurantes están obligados a emitir **factura electrónica** ante la
DIAN según su régimen tributario. Por eso el sistema entrega un
**"Comprobante interno, no válido como factura electrónica."** (texto en el
PDF, en el comprobante de 80 mm y en el detalle). **Hay que confirmar con el
contador de cada restaurante si está obligado**; si lo está, la facturación
electrónica se integra después con un proveedor tecnológico autorizado por la
DIAN. La venta ya guarda lo que esa integración necesita (tipo y número de
documento y correo del cliente, base, impuesto y tasa, y los campos
`fe_estado` / `fe_cufe` vacíos), pero NO se construyó la integración.

**Sigue (fase 7)**: vistas por rol y PWA.

### 2026-10-12 — Fase 7: vistas por rol y PWA

- **Cada rol entra a SU pantalla**, derivada de sus permisos
  (`inicioDeRol` en `config/modules.js`; un rol personalizado también
  aterriza bien): dashboard.ver → Dashboard; caja.ver + ventas.crear →
  Caja; ordenes.crear → Tomar pedido; cocina.ver → Cocina; si no, su
  primera pantalla permitida. La seguridad sigue en el backend (403 por
  permiso y por plan); el frontend solo oculta y redirige.
- **Su propio menú**: el sidebar y la barra inferior se arman con lo que el
  rol puede ver. La barra inferior del celular empieza por la pantalla de
  inicio del rol (mesero: Tomar pedido, Tablero, Mesas). El tablero del
  mesero arranca en "Solo las mías".
- **Modo enfocado**: un rol con UNA sola pantalla (el cocinero) se ve sin
  sidebar ni barra inferior; arriba quedan su nombre, el tema claro/oscuro
  y cerrar sesión. Toda la tablet para la cocina.
- **Roles de ejemplo** según la tabla de la fase 7: el Mesero queda solo con
  `ordenes` (toma pedidos con `/ordenes/carta` y `/ordenes/mesas`, que
  exigen el permiso de órdenes); el Cajero con ventas, caja y órdenes; el
  Cocinero solo con cocina. Siguen siendo editables en Seguridad → Roles.
- **PWA**: `manifest.webmanifest`, íconos monocromos 192/512 y enmascarable
  (generados con Pillow, sin color), `theme-color`, y un service worker
  propio (`public/sw.js`, sin dependencias) registrado SOLO en la versión
  compilada: navegación con red primero y la última app como respaldo;
  `/assets/` con caché primero (nombres con hash). La API (otro origen)
  NUNCA se guarda en caché.
- **Sin conexión**: franja fija "Sin conexión" mientras el navegador no
  tenga red; el pedido que se está escribiendo ya vivía en el equipo
  (borrador en localStorage desde la fase 4) y se envía al volver la red.
- El cajón lateral se cierra al navegar derivándolo de la ruta (sin un
  efecto que haga setState).

**Sigue (fase 8)**: dashboard y reportes.

### 2026-10-12 — Fase 8: dashboard y reportes

- **Definiciones únicas** (`app/modules/reportes/consultas.py`, las usan el
  dashboard y Reportes): *Vendido* = lo que pagaron por lo consumido, con
  el impuesto al consumo y sin propinas; *Ingresos* = vendido SIN el
  impuesto (es de la DIAN); *Costo de lo vendido* = costo por receta de
  cada plato el día que se pidió; *Utilidad bruta* = ingresos − costo;
  *Utilidad real* = bruta − gastos. Las propinas no son ingreso.
- **Dashboard**: periodo **Semana** (desde el lunes de Colombia, contra el
  mismo tramo de la semana anterior) además de Hoy, Mes y Año. KPI:
  Vendido, **Utilidad real** (con su bruta y los gastos; sin costos.ver se
  muestra el ticket promedio y el backend no manda la cifra), **Órdenes**
  (con ticket promedio; reemplaza a "Clientes", que dependía de un nombre
  opcional) y Platos vendidos. La tarjeta oscura responde "¿Cuánto gané?".
- **Donas de participación** (por categoría, medio de pago y tipo de
  orden) en el dashboard y en Reportes: componente propio
  `components/charts/Dona.jsx`, monocromo con seis tonos por ROL, leyenda
  con porcentaje y valor, **nunca más de 6 partes** (el resto en "Otros",
  `charts/partes.js` y espejo `partes()` en el backend). Entra una vez con
  transform + opacidad; los arcos se calculan en JS y no se animan.
- **Reportes** (`/reportes`, permiso nuevo `reportes`, grupo propio desde
  Básico): Hoy, Semana, Mes, Año o fechas (hasta 400 días); resumen
  financiero, platos más y menos vendidos con margen y % de costo, horas de
  más venta, días de la semana, tipos de orden, meseros (órdenes, vendido,
  ticket), medios de pago, categorías, consumo de insumos y mermas con su
  costo, y gastos por categoría. **CSV por sección** (`/reportes/csv`) y
  **PDF** completo (`/reportes/pdf`, `generar_reporte_pdf` en
  `app/core/pdf.py`). Las cifras de costo solo con `costos.ver`.
- Se conservan la gráfica de área, la comparación con el tramo anterior y
  la proyección del producto JS.

**Sigue**: datos de demostración completos (pedido del usuario del
2026-10-12) y verificación por rol.

### 2026-10-12 — Datos de demostración (rama `datos-demo`)

- **`automatizaciones/deploy/seed_demo.py` reescrito.** Solo desarrollo:
  con `ENV=production` se niega (`ConflictError`) y las cuentas demo nunca
  existen en producción. Fechas relativas a HOY en Colombia; idempotente
  por día (si Donde Tavo ya tiene órdenes de hoy, no toca nada); `--reset`
  borra y recrea SOLO las dos empresas demo (borrado genérico por
  `tenant_id` sobre todas las tablas). Se corre desde `backend/`:
  `venv\Scripts\python ..\automatizaciones\deploy\seed_demo.py [--reset]`
  (unos 4–5 min). **Correrlo el día de la demo**: los estados de "hoy"
  (cocina, mesas, caja abierta) son de la jornada en que se cargó.
- **Pasa por la lógica real**: llama a los servicios y a las funciones de
  ruta de FastAPI como funciones (sin HTTP), con un `ahora` histórico que
  la API nunca envía (`registrar_merma`, `registrar_conteo`,
  `anular_compra`, `cocina.services.mover`, `gastos.services`,
  `seguridad.alta.crear_empresa` se separaron de sus routers para eso). Las
  recetas descuentan insumos, el costo sale del promedio ponderado y la caja
  cuadra con los cobros. Los eventos (compras, órdenes, tomar/finalizar/
  entregar/cobrar, anulaciones, mermas, conteo, cierres, gastos) se aplican
  en orden cronológico; la cantidad de cada compra se calcula con lo que
  va a gastarse hasta la siguiente, así nunca falta un insumo.
- **Donde Tavo** (90 días): logo provisional, 12 mesas en Salón y Terraza,
  3 tipos de orden, medios de pago, impuesto al consumo, jornada y alerta
  de cocina; 20 platos en 5 categorías con foto, descripción y
  modificadores (uno agotado hoy: Jugo de mora; uno inactivo: Sopa de
  costilla), 2 combos de estudiante vigentes y uno vencido (Combo
  parciales, solo en su semana); 25 insumos; 4 proveedores (2 jurídicos con
  NIT y DV válidos, 2 naturales); ~35 compras con una anulada (duplicada);
  ~2200 órdenes de los tres tipos y orígenes; hoy órdenes en todos los
  estados, una anulada, mesas libres/ocupadas/por cobrar y la caja
  abierta; un cierre por día anterior (tres de Carla con faltantes);
  mermas con motivo y un conteo físico; gastos de arriendo, servicios,
  nómina, gas y aseo. **Café Central** (7 días, 3 platos) para el
  aislamiento.
- **Cuentas** (contraseñas válidas para las reglas de registro, sin
  ajustes): admin@dondetavo.demo / Tavo2026*Admin (Gustavo Rincón),
  caja@dondetavo.demo / Tavo2026*Caja (Carla Ruiz), mesero@ / mesero2@ /
  mesero3@dondetavo.demo / Tavo2026*Mesero, cocina@ / cocina2@dondetavo.demo
  / Tavo2026*Cocina, admin@cafecentral.demo / Central2026*Admin.
- **Historias para la IA** (y la regla que la detecta, todas nuevas o
  ajustadas en `app/modules/ia/analisis.py`): demanda alta de lunes a
  jueves y casi nula el domingo (`patron_dia`); picos a las 7 y a las 12
  medidos por la LLEGADA de la orden, no por el cobro (`patron_hora`);
  semana de parciales con más Rápidas (`semana_fuerte`, semanas de
  calendario completas contra la mediana, con la categoría que la empujó)
  y la semana pasada floja (`semana_floja`); Almuerzo ejecutivo y
  Hamburguesa clásica venden mucho y dejan poco margen (el "mucho" es por
  dinero movido, no por unidades); Arroz con leche casi no se vende (sección
  nueva `carta`); la carne de res subió 30 % y bajó el margen de 3 platos
  (sección nueva `alzas`, solo con `costos.ver`); mermas anormales de
  lechuga en las dos últimas semanas (`merma`); diferencias de caja
  repetidas en el turno de Carla (`diferencias_caja`, enlaza a Cierres);
  leche y queso se acaban en días (`quiebre`). Además: las caídas ya no
  cuentan promociones vencidas, un "ganador" debe pesar al menos 1 % de lo
  vendido, y las semanas fuera de lo común no dependen del mínimo de los
  patrones de día y hora.
- **Cifras creíbles** (ajuste del mismo día, al ver el dashboard): con
  ~25 órdenes diarias y gastos de $16 M el restaurante perdía $11 M al mes.
  Ahora ~36 órdenes de lunes a miércoles (unas 2.200 en 90 días, ~$12–13 M
  vendidos al mes) y gastos de un local universitario pequeño (arriendo
  $1,8 M, nómina $1,6 M por quincena, energía, acueducto, internet, gas y
  aseo, ~$6,3 M): utilidad real de $0,9–1,4 M al mes (8–11 %). El mes en
  curso puede ir en negativo los primeros días porque el arriendo se paga
  el 1.
- **"Hoy" nunca en cero**: si la carga corre temprano y hay pocas órdenes
  de hoy, al menos `MIN_COBRADAS_HOY` (5) quedan cobradas y los estados
  vivos (entrante, en preparación, lista, entregada) se reparten por
  prioridad con las que sobran (a las 9:30 a. m. las 10 órdenes del día
  quedaban vivas y "Hoy" mostraba $0).
- Lo protegen `tests/test_seed_demo.py` (cuentas, estados de hoy, caja,
  inventario = suma de movimientos, utilidad real = ingresos − costo por
  receta − gastos, aislamiento, idempotencia, se niega en producción) y las
  pruebas nuevas de `tests/test_ia.py`.

### 2026-10-13 — Pulido final antes de compartir el repositorio (rama `pulido-final`)

Recorrido automático de las 67 pantallas con los cuatro roles en 375, 768 y
1440 px (267 vistas: captura, desborde, consola, medidas de formularios,
tablas y objetivos táctiles) más `/impeccable layout` y `/impeccable audit`.
Paleta, tipografías y animaciones no se tocaron.

- **Horas corridas 5 h (error real)**: el backend manda instantes UTC sin
  zona y `formatearFecha`/`formatearFechaHora` los leían como hora local; un
  cierre de las 9:15 p. m. salía a las 2:15 a. m. Ahora todo pasa por
  `aInstante` y se muestra en `America/Bogota` (`lib/formato.test.js`). Lo
  mismo en los PDF: `formatear_fecha` y el pie "Documento generado"
  (`tests/test_pdf_fechas.py`).
- **Cifras partidas**: en la tarjeta "Costo y margen" (columna lateral) el
  `overflow-wrap: anywhere` del detalle partía "$ 1." / "091". Las cifras del
  `Detalle` ya no se parten y la tarjeta envuelve (el % arriba, el desglose
  debajo) cuando no cabe al lado.
- **Detalles de una sola tarjeta a 720 px** (categoría, mesa, zona, gasto,
  usuario, rol), igual que su formulario de edición: antes una tarjeta de
  1.160 px con cinco filas.
- **Reportes**: siete cifras en rejilla automática dejaban "Propinas" sola;
  ahora 4 columnas con la utilidad real a doble ancho (dos filas completas).
- **Cocina en tablet vertical**: columnas de ~240 px partían "Mesa S1" en
  tres renglones; con una consulta de contenedor el tiempo baja a su línea.
- **Pantallas táctiles** (`@media (pointer: coarse)`): botones de 40–44 px,
  campos de 44 px con letra de 16 px (con menos, iOS hace zoom), fichas y
  píldoras de 44 px, íconos de la barra a 44 px. La densidad de escritorio
  (30 px) se queda para el mouse. El buscador de "Tomar pedido" es un
  `label`: toda la caja enfoca el campo.
- **Barra de los listados en celular**: buscador a lo ancho y filtros en dos
  columnas iguales (antes uno por fila con anchos distintos).
- Selector de archivo de la carga inicial con el botón del sistema.
- **Cero avisos**: Starlette 1.7.0 (la 1.6 usaba un alias obsoleto de
  anyio), `httpx2` para el TestClient (Starlette lo pide desde 1.6), el
  `ResourceWarning` de `test_startup` (tubería sin cerrar), Vitest 4.1.11
  (la 3.x tenía vulnerabilidades en `@vitest/mocker` y `tinypool`; se
  declaró `@testing-library/dom`, que antes llegaba como peer) y
  `source-map-js` 1.2.2. `npm audit`: 0. Dependencias de producción sin
  cambios. Se quitó `esbuild.jsx` de `vite.config.js` (Vite 8 usa oxc y lo
  ignoraba con un aviso). `/health` y el diagnóstico decían "JS Company -
  ERP": ahora "JS Restaurante".
- **Lint**: se corrigieron las advertencias triviales; quedan 29 heredadas
  del Producto JS (`only-export-components` en archivos de contexto y
  `set-state-in-effect` en los hooks que evitan el parpadeo). No son
  errores; cambiarlas obliga a partir archivos y tocar hooks medidos, y se
  deja para un trabajo aparte.
- **Seguridad antes de compartir**: revisados los 11 commits del historial
  y los archivos: sin `.env`, tokens, claves ni secretos (solo valores de
  ejemplo y la clave de la base local de Docker). `.gitignore` cubre
  cualquier `.env` (salvo los `.example`), `venv`, `node_modules`, `dist`,
  bases y respaldos locales, Impeccable y `.claude/worktrees`.
- **Verificado**: 731 pruebas del backend sin un solo aviso (también con
  `python -X dev`), 290 del frontend, build, `impeccable detect` limpio,
  consola sin errores ni advertencias en las 267 vistas, punta a punta por
  rol (mesero en celular toma → cocina en tablet toma y finaliza → mesero
  entrega → caja cobra → admin lo ve en "Hoy"), y Docker desde cero en un
  proyecto aislado (`tavo-verif`, otros puertos y volúmenes): migraciones
  sobre base vacía, backend, frontend y n8n en 200; el Producto JS siguió
  en sus puertos (5432 y 8001) sin tocarse.

---

## 1. Configuración crítica que NO se borra

### 2026-10-12 — Mapa de puertos: los dos productos corren a la vez

El usuario corre el Producto JS y este en la misma máquina al mismo tiempo, y
ya se perdió mucho tiempo con puertos (el 8000 reservado por Windows, Vite
saltando de puerto en silencio). Ningún puerto se repite:

| Servicio | Producto JS (no tocar) | **Producto Tavo** |
|---|---|---|
| Frontend (Vite dev) | 5173 | **5175** |
| Vista previa compilada | 4173 | **4175** |
| Backend (FastAPI) | 8001 | **8002** |
| Postgres (puerto en el equipo) | 5432 | **5433** |
| n8n | — | **5679** |

- **Verificados antes de fijarlos** (2026-10-12): ninguno cae en los rangos
  reservados de Windows (`netsh ... excludedportrange`: 49898–49997,
  50000–50059, 50060–50159, 50190–50289, 56023–56122, 57491–57590,
  59461–59560) ni estaba ocupado (`Get-NetTCPConnection`); el 8001 y el
  5432 los tenía el Producto JS.
- **Docker aislado:** `name: tavo` en `infra/docker-compose.yml`. Hallazgo:
  el compose del Producto JS no tiene nombre y Docker lo llama `infra` (el
  de la carpeta), con volumen `infra_db_data`; una copia sin `name` habría
  usado sus mismos contenedores y sus datos (y `down -v` los habría
  borrado). Contenedores `tavo-db`, `tavo-backend`, `tavo-n8n` (y
  `tavo-frontend` con el perfil `frontend`), volúmenes con nombre explícito
  `tavo_db_data` y `tavo_n8n_data`, base `tavo_erp` con usuario
  `tavo_admin`. Dentro de Docker: `db:5432`, `backend:8002`, `n8n:5678`;
  hacia afuera solo los puertos de la tabla. n8n fijado en `2.42.7` (la
  versión `stable` del 2026-10-12).
- **Sin `.dockerignore` la imagen copiaba el `venv` de Windows y el `.env`
  con secretos**: ahora hay uno en `backend/` y otro en `frontend/`.
- **El frontend en Docker nunca había arrancado** (defecto heredado; en el
  Producto JS ese servicio no se usaba): el `predev` de npm corría
  `liberar-puerto.mjs`, cuyo `lsof` en Alpine (busybox) ignora los filtros y
  el script se mataba a sí mismo con `kill -9` (SIGKILL en bucle). El
  `Dockerfile` arranca ahora `npx vite --host` directo. El frontend en
  Docker es opcional (perfil `frontend`); para desarrollar se usa Vite local.
- **Verificado el 2026-10-12, los dos productos a la vez:** JS (5173 → 8001,
  `infra-db-1` en el 5432) y Tavo (5175 → 8002, `tavo-db` en el 5433,
  `tavo-n8n` en el 5679, todo en Docker), con sesión iniciada en ambos al
  mismo tiempo en dos pestañas. `/seguridad/me` responde 200 en cada uno con
  su token, y el token de uno da 401 en el otro (`SECRET_KEY` distintas). El
  repositorio del Producto JS quedó sin cambios.
- **Scripts que ya no tumban al otro producto.** Los heredados cerraban
  "todo python con `uvicorn app.main` o `multiprocessing.spawn`" y "todo
  node con vite" de la máquina: arrancar uno mataba al otro. Ahora
  (`automatizaciones/dev/comun.ps1`) solo se cierra lo que escucha en un
  puerto de ESTE producto —con su reloader y sus workers, reconocidos por
  `parent_pid=`— o lo que lleva la ruta de esta carpeta, y nunca un proceso
  que no sea Python en el puerto del backend (p. ej. Docker con
  `tavo-backend`). **Ojo:** los scripts del Producto JS siguen cerrando por
  nombre; si se usan mientras Tavo corre, lo tumban (no se tocan desde aquí).
- **`automatizaciones/dev/verificar-puertos.ps1`:** revisa los cinco puertos
  (o los que se pidan con `-Servicios`): reserva de Windows con el arreglo,
  ocupación con el proceso (PID, nombre, línea de comando) o el contenedor
  que lo publica. Lo llaman `start-backend.ps1` y `start-frontend.ps1`.
- **`uvicorn app.main:app` a secas ya no arranca en un puerto equivocado:**
  `app/core/arranque.py` reconoce el CLI de uvicorn (`uvicorn`,
  `uvicorn.exe` o `python -m uvicorn`), calcula el puerto efectivo
  (`--port`, `--port=`, `UVICORN_PORT` o el 8000 por defecto) y, si no es
  `Settings.PORT`, sale con código 1 y el comando correcto. No afecta a
  `python -m app.main`, `start-backend.ps1`, Docker ni a pytest.
- Protección: `tests/test_mapa_de_puertos.py` (cruza Settings, los dos
  `.env.example`, Vite, `package.json`, `api.js`, compose, `comun.ps1`,
  `.claude/launch.json` y `.vscode`; y que ningún script vuelva a cerrar
  procesos por nombre), `tests/test_arranque.py`, `tests/test_config.py`,
  `frontend/src/vite-config.test.js`.

### Heredada del Producto JS (vigente)


Es configuración activa aunque nada la referencie. En limpiezas de código
("no usado", simplificar, consolidar) **nunca** se elimina ni se reordena.

| Qué | Dónde | Por qué | Protección |
|---|---|---|---|
| CORS del backend | `backend/app/main.py` (bloque "CONFIGURACIÓN CRÍTICA"), `app/core/cors.py`, `app/core/error_handlers.py`, `CORS_ORIGINS` | Sin esto el frontend no puede registrarse ni iniciar sesión. El bloqueo reapareció varias veces porque se borraba como "código muerto". | `tests/test_cors.py`, `tests/test_cors_config.py` |
| Orden catch-all → CORS | `main.py`: `CatchAllExceptionsMiddleware` ANTES de `configure_cors()` | Para que los 401/409/422/500 también lleven `Access-Control-Allow-Origin`. Mover el catch-all a `add_exception_handler(Exception)` lo saca de CORS (comprobado). | `tests/test_cors.py` |
| Puerto frontend **5175** (era 5173 en el Producto JS) | `frontend/vite.config.js` (`server.port`), `.env` | Fijo: CORS y la URL del backend dependen de él. | `src/vite-config.test.js`, `tests/test_mapa_de_puertos.py` |
| **`strictPort: true`** | `frontend/vite.config.js` | Si el 5175 está ocupado Vite debe FALLAR, no saltar al siguiente en silencio (ese salto rompe CORS sin avisar). | `src/vite-config.test.js` |
| Puerto backend **8002** (era 8001 en el Producto JS) | `Settings.PORT`, `VITE_API_URL`, `automatizaciones/dev/start-backend.ps1`, `infra/docker-compose.yml` | Fijo, igual que el del frontend. | `tests/test_mapa_de_puertos.py`, `tests/test_arranque.py` |
| Orígenes de red privada en desarrollo | `DEV_ORIGIN_REGEX` en `app/core/cors.py` (solo `ENV=development`) | Vite imprime una URL "Network"; sin la red privada, abrirla daba 400 en el OPTIONS del login (caso real, 2026-09-27). | `tests/test_cors_config.py` |
| Demo por túnel | `HOSTS_TUNEL`/`allowedHosts`, `preview.port = 4175`, `DOMINIOS_TUNEL`, header `bypass-tunnel-reminder` | Se comparte SIEMPRE la versión compilada (`vite build --mode tunnel` + `vite preview`). | `tests/test_cors_config.py`, `src/vite-config.test.js` |
| Variables obligatorias | `DATABASE_URL`, `SECRET_KEY` sin valor por defecto; `.env` siempre desde `backend/.env` | Arranque en máquinas nuevas con mensaje en español, nunca el ValidationError de pydantic (2026-09-27). | `tests/test_config.py` |

Síntoma engañoso: si el backend no corre, Firefox reporta "CORS request did
not succeed". Antes de tocar CORS, comprobar que algo escucha en el 8002
(`automatizaciones/dev/verificar-puertos.ps1`).

---

## 2. Paleta

### Vigente — 2026-10-01: monocromática estricta (claro principal)

Cero color: solo blanco, negro y grises. Si aparece un azul, un verde o
cualquier tinte, está mal (un test lo verifica canal por canal: R, G y B a
menos de 12 puntos entre sí).

| Claro (principal) | | Oscuro | |
|---|---|---|---|
| fondo de la app | `#EDEDF0` | fondo | `#0A0A0B` |
| tarjetas, sidebar, barra | `#FFFFFF` | tarjetas | `#141416` |
| relleno interior (KPI, encabezado de tabla) | `#F7F7F9` | relleno interior | `#1C1C1F` |
| rellenos sutiles, píldora activa, badges | `#F1F1F4` | sutil y píldora activa | `#232327` |
| bordes | `#E4E4E9` | bordes | `#2A2A2F` |
| divisorias finas | `#F0F0F3` | secundario | `#8A8A94` |
| eje de gráficas, borde en hover | `#D4D4DA` | principal, serie, botón | `#F4F4F5` |
| texto secundario | `#6B6B76` | | |
| texto terciario | `#52525B` | | |
| navegación | `#3F3F46` | | |
| principal, serie actual, botón | `#18181B` | | |

- **Claro por defecto** (`ThemeContext`); `:root` sin atributo pinta en
  claro y un script en `index.html` aplica el modo guardado antes del primer
  pintado (sin cuadro del modo equivocado).
- Mismos ROLES de siempre (`--texto`, `--borde`, `--relleno`…): los
  componentes no cambiaron de variable. El oscuro tiene siete tokens; sus
  divisorias, eje, terciario y nav salen de mezclar sus propios tokens.
- Jerarquía SOLO con valor y peso tipográfico; positivo/negativo por
  intensidad y ▲/▼. Sin sombras en tarjetas ni degradados de fondo.
- La comparativa de la gráfica usa el secundario, no `#D4D4DA`: una línea que
  se lee necesita 3:1 (WCAG 1.4.11) y ese gris queda en 1,5:1 sobre blanco.
- Renders 3D y favicon regenerados en grises (`generar-renders-3d.py`).
- **El acceso (login y registro) NO adopta la tarjeta blanca**: el usuario
  pidió revertirlo (§4, 2026-10-01). `.esquema-oscuro` aplica ahí los roles
  del oscuro monocromático; dentro del acceso el terciario y el suave son el
  texto al 62 % y al 82 % para conservar la jerarquía aprobada.
- Protección: `frontend/src/paleta.test.js`.
- Pendiente fuera de esta decisión: los PDF (`app/core/pdf.py`) siguen con
  el esquema claro anterior.

### Histórica — 2026-09-28 a 2026-10-01: Espresso/Marfil (oscuro) y Blanco/Crema (claro)

**Sustituida** por la monocromática del 2026-10-01. Se conserva su registro:

DOS esquemas de seis tokens y ningún otro color.

| Oscuro (principal) | | Claro | |
|---|---|---|---|
| espresso | `#0B0908` | blanco | `#FFFFFF` |
| carbón | `#151110` | crema | `#FBF6EC` |
| sombra | `#241D1A` | crema-hondo | `#F2E7D3` |
| ceniza | `#4A3F39` | arena | `#D9C5A0` |
| lino | `#B9A88F` | tierra | `#8A6B44` |
| marfil | `#EDE4D8` | marrón | `#3B2A18` |

- Los valores viven SOLO en `frontend/src/index.css` (paleta → roles por
  modo → capa de tenant). Los componentes usan roles (`--texto`, `--tinta`,
  `--positivo-fondo`…), nunca un token de paleta.
- La jerarquía se hace con opacidades de `--tinta` (marfil / marrón).
- Sin rojo, verde, azul ni dorado: positivo y negativo se distinguen por
  intensidad y SIEMPRE con ▲/▼; éxito y error de las alertas por icono, rol,
  duración y texto.
- El botón primario invierte el esquema (marfil + espresso / marrón + crema).
- Contraste AA medido en la app viva. En claro el marrón al 55–65 % NO llega
  (3,3–4,4:1): el secundario es tierra sólida y las insignias llevan texto
  marrón.
- Los PDF usan el esquema claro; los SVG 3D salen de
  `frontend/scripts/generar-renders-3d.py` con la misma paleta.
- La capa de tenant (`--color-primario` desde `Tenant.theme_config`) sigue
  pudiendo repintar el acento de cada cliente.
- Protección: `frontend/src/paleta.test.js`.

### Descartadas

| Fecha | Paleta | Por qué se descartó |
|---|---|---|
| 2026-09-28 a 2026-10-01 | **Espresso/Marfil + Blanco/Crema** (arriba) | Sustituida por la monocromática estricta del 2026-10-01 (decisión del usuario: cero color). |
| hasta 2026-09-28 | **Verde bosque** (ónix `#0B0A09`, carbón `#1A1917`, humo, piedra, arena `#D4CFC4`, marfil `#F4F1EB`, verdes `#0A1711`/`#16352A`/`#1F4A38` de la maqueta) | Sustituida por la paleta Espresso/Marfil del 2026-09-28. |
| hasta 2026-09-25 | **Pizarra** (azules `#0C1016` → `#9FB2C6`) conviviendo con la anterior | Retirada al llevar el dashboard a la maqueta aprobada. |

---

## 3. Tipografías

**Vigente (aprobada, no se cambia):**

| Uso | Familia | Notas |
|---|---|---|
| Títulos | **Playfair Display** | `--fuente-titulo` |
| Interfaz | **Inter** | `--fuente-base` |
| Cifras | **JetBrains Mono** | `--fuente-mono` con `tabular-nums` (clase `.cifra`) |

- Solo el subconjunto `latin` de @fontsource (cubre el español). NO sumar
  `latin-ext`: sin `unicode-range` el navegador baja ambos (medido: de 3 a 6
  descargas de fuente).
- **2026-09-28:** Impeccable desaconseja Inter por "sobreusada". Se ignora
  ese consejo: la tipografía está decidida y aprobada.

---

## 4. Layout y estructura

- **Maqueta aprobada (2026-09-25):** `docs/dashboard-referencia.html` sigue
  siendo la referencia de la FORMA DE ANIMAR. Su aspecto (panel flotante,
  degradados, paleta) y el layout del dashboard los **sustituyó el rediseño
  monocromático del 2026-10-01**, pedido por el usuario (abajo).
- **Marco (2026-10-01, sustituye al panel flotante con degradados):** sidebar
  blanco a toda altura con borde derecho de 1 px, secciones con título en
  mayúsculas de 11 px, píldora activa gris con texto en 600 (el mismo
  indicador deslizante), badges numéricos y bloque de usuario abajo (avatar,
  nombre, rol y plan); barra superior blanca con borde inferior, sección
  actual y píldoras de estado con punto ("1 producto bajo el mínimo"). El
  contenido va sobre el gris de la app con 16 px entre bloques
  (`components/shell.css`, `Sidebar.jsx`, `BarraSuperior.jsx`). En pantallas
  angostas, cajón lateral con `transform` y barra inferior, como antes.
- **Avisos compartidos (2026-10-01):** barra, sidebar y panel del dashboard
  leen UN `/dashboard/avisos` (`context/AvisosContext.jsx`, reutiliza la
  petición en vuelo). Sin búsqueda global en la barra: el usuario la
  descartó (un buscador que no busca no se pone).
- **Dashboard (2026-10-01):** fila de KPI con CAPA DOBLE (tarjeta blanca de
  6 px de relleno; bloque gris de radio 12 y 16 px con icono y cifra de
  30 px/600/−0,02em; tendencia ▲▼ fuera del bloque), tarjetas de 16 px sin
  sombra y sin elevación en hover (solo el borde), barras de 6 px, rejilla
  de 12 columnas con cortes por CONTENEDOR (el ancho real depende del
  sidebar). Mismos datos y mismas dos peticiones.
- **Tablas (2026-10-01):** encabezado gris de 12 px en mayúsculas, filas con
  línea de 1 px y tinte leve en hover, la tabla llega a los bordes de su
  tarjeta; Productos con miniatura de 44 px (la imagen 3D del detalle).
- **2026-09-27:** grupos del sidebar TODOS cerrados al cargar o recargar, sin
  recordar nada ni abrirse solos por la ruta, y un solo grupo abierto a la
  vez; lista densa (~30 px por ítem).
- **2026-09-19 — Densidad y alineación:** pantallas compactas; `ui/Table.jsx`
  es la ÚNICA tabla; todo centrado; formularios a 720 px.
- Una pantalla con ruta propia por acción (`/x`, `/x/nuevo`, `/x/:id`,
  `/x/:id/editar`). Sin modales para crear/editar/ver: lo único que sigue
  siendo diálogo es `ModalConfirmar`, y aparece sin animación.

### 2026-09-30 — Sin `datetime.utcnow` (Fase 8)

- La suite daba **6.506 avisos** (el plan hablaba de 2.268: la suite creció);
  6.407 venían de un solo sitio, el `default=datetime.utcnow` de
  `TimestampMixin`, uno por cada fila insertada. Ahora todo usa
  `app/core/tiempo.ahora_utc()` (mismo valor: UTC naive, porque las columnas
  son DateTime sin zona) y el token JWT usa `datetime.now(timezone.utc)`.
- Resultado: **412 pruebas, 2 avisos**, ambos de dentro del `TestClient` de
  Starlette (httpx/anyio); arreglarlos es cambiar dependencias fijadas.
- **`pytest.ini` convierte cualquier `utcnow` en ERROR**: comprobado con una
  prueba canario que falla y se borró.
- Verificado en vivo tras reiniciar el backend: el token emitido vence a los
  480 min exactos y `/seguridad/me` responde 200.
- Se eliminó el worktree `.claude/worktrees/dreamy-lederberg-6f94ff` tras
  comprobar que no perdía nada: sus commits están en otras ramas y sus
  cambios sin guardar ya estaban en `cierre-v1` o superados (la prueba de
  fechas aquí usa reloj fijo, mejor que su arreglo). Su rama queda.

### 2026-09-30 — Datos de demostración con fechas relativas a hoy

- `seed_demo.py` **re-ancla en cada corrida** cada documento de la demo
  (compras, ventas, pedidos, sus movimientos de inventario y la línea de
  tiempo del pedido) a sus "días atrás" contados desde hoy. Antes era
  idempotente pero se quedaba congelado: a los dos días "Hoy" salía en ceros.
- **Historial**: 3 compras de hace ~6 meses y una venta por mes (5 meses) más
  una a mitad de semana, con notas NUEVAS para no duplicar en empresas que ya
  tenían la demo. Las compras y ventas se crean en orden cronológico: el
  historial de inventario cuadra paso a paso por fecha.
- Verificado en la empresa del usuario ("JS company", vía API viva): Hoy
  $158.600; 1S con 4 días de ventas; 6M con los 6 meses; tres avisos.
  Segunda corrida: 0 documentos nuevos.
- **Hallazgo (no corregido en esta fase)**: el dashboard calcula "Hoy",
  "Mes" y "Año" en UTC (`periodos.py`), no en el día de Colombia como las
  validaciones. De 19:00 a 24:00 en Bogotá, "Hoy" ya es el día siguiente y
  "Mes" el 1 de octubre solo mostraba hoy. Queda como tarea aparte.
  **Corregido** en la entrada siguiente ("El dashboard usa el día
  calendario de Colombia").
- Lo protege `tests/test_seed_demo.py` (incluido el caso "la demo se cargó
  hace 10 días").

### 2026-09-30 — El dashboard usa el día calendario de Colombia

- Cierra el hallazgo de la entrada anterior. Las ventanas de `periodos.py`
  se calculaban en días UTC: en Bogotá "Hoy" iba de 19:00 a 19:00, y después
  de las 7 p. m. las ventas de la mañana salían de "Hoy" (y el último día del
  mes, "Mes" pasaba a ser el mes siguiente con un solo día).
- **Regla:** todos los límites del dashboard (Hoy/Mes/Año, los buckets de
  hora/día/mes de 1D/1S/1M/6M/1A, el tramo anterior, el bucket de la
  proyección y los meses de la proyección del panel) se calculan en hora de
  Bogotá con `ZONA_NEGOCIO` de `app/core/validaciones.py` y se convierten a
  **UTC naive** antes de llegar a SQL: `Venta.fecha`/`Compra.fecha` siguen
  siendo DateTime sin zona, en UTC, y nunca se compara un valor con tzinfo.
  La gráfica agrupa con `date_trunc(unidad, fecha - 5 h)` y la clave vuelve a
  UTC naive para casarla con `RangoGrafica.inicios()`.
- **El contrato del API no cambia:** los instantes siguen saliendo en ISO UTC
  naive; solo cambia dónde caen (00:00 de Bogotá = `T05:00:00`).
- Se mantiene la regla del tramo anterior del mismo largo: el desfase es
  constante (Colombia no tiene horario de verano), así que convertir a UTC
  no cambia ningún largo. Efecto visible: a las 21:00 del 30 de septiembre,
  "Mes" es septiembre completo contra el 1-30 de agosto de Bogotá.
- Descartado: zona como `ZoneInfo("America/Bogota")` (Windows no trae
  tzdata) y columnas `timestamptz` (migración de todos los datos para un
  desfase fijo).
- Lo protege `tests/test_panel_dashboard.py` con reloj fijo a las 21:00 de
  Bogotá (02:00 UTC del día siguiente): venta de las 10:00 en "Hoy", "Mes"
  y "Año" en la primera hora UTC del mes/año siguiente, buckets de los cinco
  rangos, y de punta a punta panel + serie (1D/1S/6M).
- Verificado en vivo sobre "JS company" a las 23:11 de Bogotá del 30 de
  septiembre: el backend viejo daba Hoy $158.600 y Mes = solo el 1 de
  octubre; el nuevo, Hoy $290.200 (venta de las 05:30 + la de las 22:42) contra
  $63.700 del 29, y Mes = septiembre.

### 2026-09-30 — Legal y datos personales (Colombia)

Detalle completo, inventario y pendientes en **`docs/legal/README.md`**.
Todo es BORRADOR pendiente de abogado; los datos de la empresa son
marcadores en `frontend/src/config/empresa.js`.

- **Política de tratamiento de datos** (Ley 1581/2012, Decreto 1377/2013) y
  **Términos y condiciones** como pantallas públicas `/legal/privacidad` y
  `/legal/terminos` (rutas diferidas: no pesan en el login), con un
  renderizador de Markdown propio de 0 KB. **Cláusula de transmisión de
  datos** para el contrato en `docs/legal/`.
- Roles: JS Company Responsable de las cuentas; **el cliente es Responsable
  de lo que registra y JS Company su Encargado**. Los datos son del cliente.
- **Registro con casilla desmarcada por defecto**, obligatoria también en el
  backend (422 con la causa, aunque el campo no venga). Se guarda en
  `aceptaciones_legales` documento, versión, fecha/hora UTC, usuario y
  correo; si el usuario se borra, la prueba queda (SET NULL + correo).
  Versiones en `backend/app/core/legal.py` (manda) y su espejo
  `frontend/src/config/legal.js`. Verificado en vivo: registro real → 2 filas.
- **Cookies: sin banner.** Auditoría en vivo: cero cookies; `localStorage`
  solo con la sesión y el tema; el navegador solo habla con los servidores
  propios. Se informa en la Política (§5). Revisar ANTES de agregar
  cualquier servicio de terceros en el navegador.
- **Servicios externos**: ninguno en tiempo de ejecución (sin analítica,
  CDN, correo ni IA externa). Las fuentes ya se sirven localmente
  (@fontsource): no se pide nada a Google. Hosting de producción por
  definir (será subencargado).
- **RNBD (SIC)**: la obligación depende de los ACTIVOS del Responsable
  (> 100.000 UVT, Decreto 090 de 2018), no del volumen de registros.
- Licencias: renders 3D CC0 propios, foto de login Unsplash (ya no se
  descarga), Lucide ISC, fuentes OFL. **El favicon no tiene origen
  conocido**: queda marcado "por verificar".
- **Pie legal** (razón social, NIT, correo, ciudad + enlaces) en login,
  registro, documentos y el marco de la app (fuera de `.vista`, no entra ni
  sale con cada pantalla). En login/registro el panel sigue en la mitad
  exacta con filas `1fr auto 1fr`; el pie en posición absoluta se medía
  tapando el panel 8–42 px a 375 px.
- Lo protegen `tests/test_aceptacion_legal.py`, `RegistroPage.test.jsx`,
  `modules/legal/legal.test.jsx` y `auth-diseno.test.js`.
- Suite del frontend con `maxWorkers: "50%"`: sin límite arrancaban 15
  workers de jsdom en 16 núcleos y era más lenta (18,6–19,7 s frente a
  15,5–16,8 s) con timeouts sueltos de 5 s.

### 2026-09-30 — Accesibilidad (WCAG 2.1 AA)

Auditado sobre la versión compilada con axe-core (etiquetas wcag2a, wcag2aa,
wcag21a, wcag21aa) en 98 pantallas — login, registro, dashboard, IA y las
4 pantallas de cada uno de los 9 módulos, **en modo oscuro y claro**, y los
formularios también con los errores visibles — más un recorrido con Tab
que compara cada elemento con foco y sin foco.

- **Resultado final: 0 violaciones** (incluido contraste de color en ambos
  modos) y **foco visible en todas las paradas de Tab** (11 pantallas, las
  de más controles, en ambos modos).
- **Selector con búsqueda** (`SelectorBusqueda`): era la única pantalla con
  violaciones (opciones `<button role="option">` dentro de `<li>`, lista sin
  nombre, `aria-expanded` sin `role="combobox"`, "Sin resultados" dentro
  del listbox) y no se manejaba con flechas. Ahora es el patrón combobox de
  ARIA 1.2: ↑/↓ con `aria-activedescendant`, Enter elige, Escape cierra, el
  estado va en `role="status"`.
- **Campos**: `Select` y `Textarea` no asociaban su error al control, y
  ninguno asociaba la AYUDA ("Máximo 2 decimales"…). Ahora
  `aria-describedby` apunta al error o, sin error, a la ayuda. El contador
  del `Textarea` ya no es región viva (anunciaba cada tecla); se describe
  al entrar y solo se anuncia el tope.
- El error general del formulario (p. ej. stock insuficiente, validado sin
  ir al backend) lleva `role="alert"`.
- `BotonPdf` con texto visible ya no lo tapa con `aria-label` (WCAG 2.5.3:
  "Ver PDF" por voz debía encontrarlo).
- Imágenes: la única es el render 3D del detalle de producto, decorativo
  (`alt=""`, el nombre está al lado). Iconos: decorativos con
  `aria-hidden`; los botones de solo icono tienen `aria-label` (axe
  `button-name` en 0).
- Lo protegen `components/SelectorBusqueda.test.jsx` y
  `components/ui/campos-accesibles.test.jsx`.

### 2026-09-30 — Espacios y pulido (medido en las 34 pantallas de módulo)

Medido con Playwright sobre la versión compilada (`vite preview`) en
375 / 768 / 1440 px, más 820 / 900 / 1024 / 1100 / 1180 / 1280 para el
desborde de tablas, sobre la empresa real del usuario:

- **Ya cumplían:** 16 px entre campos, 29 px entre secciones (objetivo ~28),
  etiqueta a 5 px, controles de 36 px, encabezados de tabla centrados con su
  contenido (desvío ≤ 2 px).
- **Formularios a 720 px en TODAS las pantallas.** Medían entre 298 y
  720 px: `.pantalla-estrecha` tenía `max-width` sin `width` y, dentro del
  flex en columna de `.main__contenido`, `margin: auto` lo encogía a su
  contenido. Ahora `width: 100%; max-width: 720px`.
- **Anchos de columna proporcionales al contenido** (sustituye al
  `width: 1%` del 2026-09-19): el sobrante se reparte entre todas las
  columnas. Antes, en el detalle de proveedor, "Producto" medía 872 px para
  137 px de texto.
- **La página ya no se desplaza de lado.** Entre 768 y 900 px (y a 1180 px,
  cuando vuelve el sidebar) siete tablas se salían de su tarjeta — defecto
  ANTERIOR a esta fase (comprobado volviendo a la regla vieja: mismo
  resultado). Ningún umbral de ventana sirve (ancho mínimo de 266 a 851 px),
  así que `Table` mide si cabe (`hooks/useTablaApilada.js`, antes del
  pintado, CLS 0) y si no, pasa a tarjetas en rejilla `auto-fill` de 18 rem
  (dos por fila a 900 px, una en el teléfono). Verificado en 8 anchos × 11
  pantallas y redimensionando en vivo.
- La flecha de volver ya no sobresale 8 px a la izquierda de la tarjeta
  (tenía un margen negativo de cuando no llevaba borde).
- Lo protegen `components/ui/Table.test.jsx` (tabla/tarjetas, sin `width:
  1%`, formulario a 100 %/720 px).

### 2026-10-01 — Login y registro: se revierte la tarjeta blanca

El rediseño monocromático los había llevado a una tarjeta blanca sobre el
gris. El usuario pidió volver al diseño aprobado del 2026-09-30 (entrada
siguiente): `LoginPage.jsx`, `RegistroPage.jsx`, `Input.jsx` y `auth.css`
se recuperaron tal cual del commit `1c5f032` (main antes del rediseño), y
en `ui.css` se repuso solo `.input--linea`. Los colores salen de la paleta
monocromática vigente vía `.esquema-oscuro` (§2), sin reintroducir tokens
viejos. Verificado en la app real: credenciales inválidas, validaciones
nativas y de aceptación, registro con 2 aceptaciones en Postgres, inicio de
sesión a 375 px y responsive a 375/768/1440 sin desborde.

### 2026-09-30 — Login y registro: panel centrado sobre negro, sin foto

- **Fondo negro sólido:** el espresso de la paleta (`#0B0908`) es el negro
  del producto; no se agrega `#000` ni ningún color nuevo.
- **Esquema oscuro forzado** en ambas pantallas, también con el modo claro
  activo: sobre negro, el texto marrón del claro no se leería. Lo hace la
  clase `.esquema-oscuro` (en `index.css` comparte selector con el bloque de
  roles oscuros y con la capa de tenant, así que no duplica ningún valor).
- **Panel centrado en la mitad de la pantalla** (`display:grid;
  place-items:center`), una sola columna de 24 rem máx., **totalmente
  transparente**: sin marco, borde, fondo de tarjeta ni sombra. La marca
  "JS Company", que antes vivía sobre la foto, va arriba del título.
- **Sin foto por ahora.** Se borraron `components/auth/FondoAuth.jsx` y
  `config/branding.js` y, con ellos, los dos bucles de ambiente
  (`auth-deriva`, `auth-veta`). La entrada es una sola: fade + 12 px con
  `--dur-bloque` / `--ease-suave`.
- **Contraste medido en la app viva** (375 / 768 / 1440 px, modo oscuro y
  claro, login y registro): todo el texto AA. El trazo inferior de
  `.input--linea` estaba a la tinta al 22 % → 1,74:1, por debajo del 3:1 de
  WCAG 1.4.11; pasó al 45 % (3,8:1) y el hover al 62 %.
- Lo protege `src/modules/auth/auth-diseno.test.js`.

**Para volver a poner la foto:** el archivo `public/fondo-auth.jpg` se
conserva (duotono de la paleta, 1920 px, 187 KB). Origen y licencia:
"Green leaves and foliage" de Łukasz Rawa en Unsplash, **licencia
Unsplash** (uso comercial libre, sin atribución obligatoria), servida
localmente, nunca desde un enlace externo. Recuperar `FondoAuth.jsx` y
`branding.js` del commit `538e365`, volver a la rejilla de dos columnas y
quitar `.esquema-oscuro` si la foto vuelve a ir detrás de una tarjeta.

---

## 5. Movimiento

### 2026-09-28 — Reglas de animación vigentes

Sustituye y amplía la decisión del 2026-09-25 (que a su vez sustituyó a la de
2026-09-18, "solo cuatro animaciones"). El criterio es CÓMO se anima.

**Reglas no negociables** (aprendidas en este proyecto):

1. Solo se animan `transform` y `opacity` (más color, repintado barato).
   Prohibido `width`, `height`, `top`, `left`, `margin`, `padding`,
   `box-shadow`, `grid-template-rows`. Barras con `scaleX`, indicadores con
   `translateX`/`translate3d`.
2. Nunca `transition: all`: se declara la propiedad exacta.
3. Nada de `backdrop-filter` en paneles grandes (causaba el flashazo al
   cargar y mataba el scroll): fondo con degradado semiopaco.
4. No se animan atributos SVG por CSS (`d`, `cx`, `cy`, `x1`, `r`): en Firefox
   saltan. Los puntos se interpolan en JavaScript con requestAnimationFrame.
5. Punto, halo, guía y tooltip de la gráfica van en una capa HTML sobre el
   SVG, movidos con `translate3d`.
6. Actualizar un número NO re-renderiza la pantalla: se escribe el texto del
   nodo (`useContadoresAnimados`, `CifraAnimada`).
7. `pointermove` se limita a un cálculo por cuadro con requestAnimationFrame.
8. **Curvas con física**: resorte (rigidez 260–320, amortiguación 28–34) o
   `cubic-bezier(0.32, 0.72, 0, 1)`. Prohibidos `linear`, el `ease` por
   defecto, rebotes y elásticos.
9. Cada animación corre UNA vez y se queda quieta. Bucles permitidos, lista
   cerrada: el halo del punto de la gráfica y la flotación de los objetos 3D
   (más el giro del spinner). El ambiente de la pantalla de acceso se retiró
   con la foto el 2026-09-30 (§4).
10. `prefers-reduced-motion` se respeta en todo; el bloque anula también los
    RETARDOS (con retardos vivos, un bloque con `--d: .28s` se queda
    invisible y el dashboard aparece a trozos).
11. Nada parpadea ni va y vuelve. Si pasa, se diagnostica si es doble montaje
    de StrictMode o una animación que se reinicia en cada render.

**Tokens (`frontend/src/index.css`, espejo JS en `src/lib/movimiento.js`):**

| Token | Valor | Uso |
|---|---|---|
| `--ease-suave` | `cubic-bezier(0.32, 0.72, 0, 1)` | Entradas, salidas, fades, color |
| `--resorte` + `--resorte-duracion` | resorte rigidez 300 / amortiguación 30 / masa 1 muestreado con `linear()`; 506 ms, sobrepasa 0,43 % | Lo que se DESLIZA: indicadores, tooltip, hermanos que se reacomodan |
| `--vaiven` | `cubic-bezier(0.37, 0, 0.63, 1)` (senoidal) | SOLO los dos bucles (flotación y halo): con una curva de salida el bucle da un tirón en cada vuelta |
| `--dur-color` / `--dur-salida` / `--dur-entrada` / `--dur-bloque` / `--dur-dato` | 150 / 180 / 280 / 300 (antes 480, cambiado el 2026-09-29) / 700 ms | Color · salidas · entradas · bloques del dashboard · movimiento de datos |

CSS no tiene resortes: se muestrea la solución exacta de la ecuación del
resorte y se expresa con la función `linear()` (Chrome 113+, Firefox 112+),
que el navegador ejecuta como cualquier otra curva.

**Excepciones documentadas:**

- **Spinner con `linear`** (2026-09-28, aprobado por el usuario): una rotación
  continua necesita velocidad constante; con cualquier curva el giro late.
- **Bucles con `--vaiven`**: ver arriba.
- **Pantalla de acceso** (`components/auth/auth.css`): desde el 2026-09-30
  ya NO está fuera de alcance; usa los tokens como el resto del producto
  (`FUERA_DE_ALCANCE` quedó vacío en `reglas-de-movimiento.test.js`).

**Qué se anima y cómo (2026-09-28):**

| Pieza | Movimiento | Implementación |
|---|---|---|
| Recarga | Marca, ítems y pie del sidebar entran en cascada (50 ms), la vista con fade y los bloques del dashboard escalonados. El MARCO (`.app`) queda quieto: ver abajo | `.sidebar__cascada`, `.vista`, `.reveal` |
| Cambio de pantalla | Entra: fade + 8 px desde abajo (280 ms, sin retardo). Sale SIEMPRE: fade + 6 px hacia arriba (180 ms), por encima de la que entra | `.vista`; salida: clon de DOM inerte en la limpieza del ref (`AppLayout.jsx`, `despedirVista`) |
| Dashboard | Bloques escalonados 55 ms en orden de lectura; el esqueleto y el contenido son el MISMO nodo, así la entrada nunca se repite | `.reveal` con `--d` |
| Indicador del sidebar | UN nodo que se desliza al ítem activo con el resorte (FLIP a mano, sin librería); cara fuerte (píldora) en ítems de primer nivel, sutil en submódulo/cabecera | `Sidebar.jsx` `colocarIndicador` |
| Píldoras Hoy/Mes/Año y 1D…1A | Indicador que se desliza con el resorte | `.pildoras__indicador` |
| Grupos del sidebar | Chevron rota; hijos entran en cascada (transición + `@starting-style`, interrumpible) y salen antes de desmontarse; los grupos de abajo se deslizan (no saltan) | `useDeslizarHermanos` |
| Tarjetas | Hover: suben 3 px y el borde se ilumina; la luz interior sigue al cursor (disco ya pintado movido con `translate3d`, sin repintar) | `TarjetaLuz.jsx` |
| Cifras | Cuentan hasta su valor al cargar y al cambiar de periodo, desde el valor que muestran | `useContadoresAnimados`, `CifraAnimada` |
| Cambio de periodo | Cifras cuentan, barras se transforman a la proporción nueva, productos que entran al ranking suben con fade | transición sobre `--proporcion`, `[data-vivo]` + `@starting-style` |
| Objetos 3D | Flotan 3 px en 7,5 s, cada uno con su desfase | `objeto-flota` (bucle permitido) |
| Gráfica — entrada | Trazo de izquierda a derecha; área sube desde la base mientras se dibuja; comparativa después (más tenue); proyección al final | `stroke-dashoffset` con `pathLength=1`, `scaleY` con `transform-box: fill-box` |
| Gráfica — cambio de rango | La curva MORFEA interpolando puntos en JS; la capa del punto va sin transición durante el morfeo (si no, se quedaba atrás de la curva) | `GraficaRendimiento.jsx`, `.grafica__capa--morfeo` |
| Gráfica — hover | Guía vertical que sigue al cursor, el punto crece, el tooltip se desliza con el resorte | capa HTML con `translate3d` |
| Barras de más vendidos | Crecen desde la base con 60 ms de desfase | `scaleX(var(--proporcion))` + `@starting-style` |
| Esqueletos | Misma forma y MISMO alto que el contenido (medido: 0 px de diferencia en los seis bloques del dashboard y en las filas de tabla) | `Skeleton.jsx`, esqueletos del dashboard |
| Alertas | Fade simple de entrada y salida (transición, no keyframes); las de abajo se deslizan al cerrarse una | `pantallas.css`, `Aviso.jsx` |

**Bugs de movimiento encontrados y corregidos el 2026-09-28** (auditoría con
`improve-animations`):

- Barras de más vendidos: `animation: … backwards forwards` (dos fill-mode)
  invalidaba la declaración entera: no se animaban y se pintaban al 100 % sin
  importar la proporción. Ahora la proporción es estado.
- El contenido del dashboard volvía a entrar desde opacidad 0 al reemplazar
  al esqueleto (causa de parpadeo prohibida).
- El punto y el tooltip de la gráfica se quedaban detrás de la curva durante
  el morfeo (la transición CSS se reiniciaba en cada cuadro).
- La fila del esqueleto de tabla medía 39 px contra 46,7 px de la real.
- La luz de las tarjetas repintaba la tarjeta entera en cada cuadro.

**2026-09-28 — El marco (`.app`) NO se anima (medido).** La primera versión
hacía entrar el marco con fade + 10 px. Medido con PerformanceObserver sobre
la versión compilada: el LCP del dashboard (`h1.saludo`) quedaba ~750-900 ms
después de montarse con el marco animado —con opacidad y también solo con
transform—, contra ~185 ms sin animarlo. Es una capa del tamaño de la
pantalla: animarla obliga a rasterizarla entera antes de que el saludo cuente
como pintado (misma lección que el `backdrop-filter`). También se quitó el
retardo de 60 ms de `.vista`, que sumaba al mismo efecto. Al recargar entra lo
de dentro (sidebar en cascada, vista, bloques). Lo protege
`reglas-de-movimiento.test.js`.

**2026-09-28 — Coste medido de la salida animada de pantallas.** La salida
(clon de DOM que se desvanece) repinta la pantalla que se va. Medido con
navegadores reales (Playwright con ventana y GPU, 10 navegaciones
dashboard → Productos por variante, versión compilada): navegaciones con un
cuadro perdido (> 20 ms) — Firefox 7/10 con salida contra 4/10 sin ella;
Chrome 4/10 contra 2/10. Es decir, la salida añade UN cuadro perdido en ~2-3
de cada 10 navegaciones. Se probó recortar el clon a lo visible, no leer
layout durante el commit, y quitarle SVG, sombras o fondos: ninguna variante
lo elimina de forma consistente.

**2026-09-29 — DECISIÓN CONSCIENTE Y CERRADA: la salida se queda como está.**
El usuario lo confirmó con estas mediciones delante. Motivo: un tirón
ocasional de 33 ms (un cuadro, en ~2-3 de cada 10 navegaciones, igual en
Firefox y Chrome) NO justifica migrar todas las navegaciones a la View
Transitions API, que obligaría a interceptar cada navegación (incluidos los
guardados de formulario que redirigen solos con `navigate` en
`useGuardarPantalla`) y a arriesgar ese flujo. No se vuelve a discutir salvo
que cambie el dato de base (p. ej., que el tirón pase a ser sistemático o
perceptible en uso real).

**2026-09-29 — Arreglos de la revisión `review-animations` (aplicados).**
Veredicto inicial: Block leve (dos problemas anteriores a la sesión). Se
aplicó, en este orden de prioridad del usuario:

1. **Spinner bajo `prefers-reduced-motion`**: sigue girando a 2 s por vuelta.
   Antes se CONGELABA: el `*` con `!important` del bloque de movimiento
   reducido le ganaba a `.spinner { animation-duration: 2s }` de `ui.css`
   (esa regla nunca tuvo efecto; ahora vive en el bloque de `index.css`).
2. **Sin elevación en las tarjetas que se leen** (Rendimiento y Más
   vendidos, clase `tarjeta--quieta`): conservan borde y luz. Al entrar a
   leer el tooltip, la gráfica entera saltaba 3 px. Las tarjetas pequeñas
   (Ventas, inventario) sí se elevan.
3. **Movimiento reducido = menos movimiento, no cero**: `.vista` entra con un
   fade de opacidad (`vista-aparece`, sin los 8 px) y `.alerta` conserva su
   fade de 180 ms. Duraciones y retardos del resto siguen en 0; ninguna
   excepción lleva retardo ni desplazamiento.
4. **Entradas más cortas**: `--dur-bloque` de 480 a 300 ms (stagger de 55 ms
   intacto) y la secuencia de la gráfica termina en 1,2 s (medido: 1187 ms
   en Chrome, 1199 ms en Firefox; antes ~1,9 s).
5. **Feedback de pulsación en `.btn`**: `scale(0.97)` en `:active`, igual que
   `.boton-claro`.

Medido en la versión compilada: dashboard FCP 124 ms, LCP 624 ms (antes
656), CLS 0, 0 tareas largas, 307 KB; login Lighthouse 100, FCP 490 ms,
LCP 655 ms, TBT 0. El CLS del login es 0,0002–0,0003 (el texto de la marca
al llegar la fuente Playfair); es IDÉNTICO en el commit anterior medido en
las mismas condiciones, así que no viene de estos arreglos, y está muy por
debajo del umbral de 0,1. (Los informes anteriores decían "CLS 0" porque
redondeaban a tres decimales.) Lo protegen `reglas-de-movimiento.test.js`
(movimiento reducido, secuencia de la gráfica ≤ 1,2 s, `--dur-bloque` 300,
tarjetas quietas, pulsación de `.btn`) y `DashboardPage.test.jsx`.

**2026-09-29 — Se decidió NO tocar:**

- **La luz que sigue al cursor va 1:1 con el puntero** (sin transición que
  la suavice). La revisión lo marcó como prioridad baja; el usuario decidió
  dejarlo: el 1:1 no le molesta y no afecta la lectura de datos.
- **El `scaleY` del FLIP del indicador del sidebar.** Revisado en cámara
  lenta (animación congelada en 0/8/16/30/50/100 % y capturas a 3x): altos
  reales 35 px (ítem), 32 px (cabecera) y 30 px (submódulo). En el peor
  salto (35 → 30) el radio vertical arranca en 14 px contra 12 horizontales,
  baja a 13,1 px al 16 % del recorrido (~80 ms) y a 12,4 px al 30 %
  (~150 ms). En las capturas la píldora se ve normal: la deformación es de
  menos de 2 px, dura menos de una décima de segundo y ocurre en
  movimiento. No se nota; se deja así.

**2026-09-28 — Sin Framer Motion.** El usuario eligió implementar a mano
(0 KB) el indicador deslizante y la salida de pantallas en vez de instalar
Framer Motion (~30 KB gzip tras el login). Mismo criterio que cuando se quitó
Recharts (109 KB → 3,1 KB).

**Protección automatizada:** `frontend/src/reglas-de-movimiento.test.js`
(backdrop-filter, propiedades de layout, `transition: all`, bucles, curvas
solo por token, rebotes, atajos `animation` inválidos, barras como estado,
resorte CSS = JS, movimiento reducido con retardos), `src/lib/movimiento.test.js`,
`Sidebar.test.jsx`, `GraficaRendimiento.test.jsx`, `DashboardPage.test.jsx`,
`Skeleton.test.jsx`, `Aviso.test.jsx`. Si hace falta una excepción, se
documenta en el test con su porqué; no se borra el test.

### 2026-10-01 — Movimiento del rediseño monocromático

Se mantienen todas las animaciones y reglas anteriores. Nuevas, con las
mismas reglas (solo transform/opacity/color, curvas por token, una vez):
cascada de las KPI (40–175 ms) con cifras que cuentan, barras y cifras que
se reescalan al cambiar de periodo, borde que se aclara en hover (sin
elevación), tinte de fila en tablas y DESTELLO del badge numérico del
sidebar cuando su número cambia (WAAPI, escala + opacidad, 420 ms; nunca al
montar). `review-animations` no puede invocarla un agente: queda para que la
corra el usuario.

### Sustituidas

- **2026-09-25** — "Manda la maqueta: el criterio es CÓMO, no cuánto".
  Ampliada por la del 2026-09-28 (curvas con física, salidas siempre
  animadas, indicador deslizante).
- **2026-09-18** — "Solo cuatro animaciones". Sustituida el 2026-09-25: el
  movimiento que había estaba mal hecho, no sobraba.

---

## 6. Rendimiento

Se mide SIEMPRE sobre `npm run build` + `npm run preview` (puerto 4175 en
este producto; 4173 en el Producto JS), nunca sobre `npm run dev`. Mediana
de 3 corridas.

- **Carga diferida por ruta** en `App.jsx`: login y registro de una vez; el
  layout y cada módulo en `lazy()`.
- **2026-09-25 — Recharts eliminado:** gráfica SVG propia (~109 KB gzip →
  3,1 KB).
- **Nada con nombre de paquete fijo en `manualChunks`** (se metería en el
  `modulepreload` del login). `manualChunks` es una función (Vite 8).
- Fuentes: solo `latin`.
- 2026-09-30: login sin foto → LCP `h1.auth__titulo`; Lighthouse 100,
  FCP = LCP 492 ms, TBT 0, CLS 0, 204 KB (antes 386 KB).
- Backend: cada listado cuesta el mismo número de consultas con 1 fila que
  con 10 (`tests/test_rendimiento_consultas.py`); índices compuestos que
  empiezan por `tenant_id`; el panel del dashboard son puros agregados.

- **2026-10-01 — Precarga de la ruta inicial** (`lib/perezoso.js`): `lazy()`
  siempre suspende la primera vez y React 19 retiene la revelación ~300 ms
  (medido: el trozo del dashboard llegaba a los 258 ms y se pintaba a los
  ~550). Con sesión guardada, el marco y la pantalla de la ruta inicial se
  piden en paralelo con `/seguridad/me` y se pintan directo si ya llegaron.
  Ninguna otra ruta se descarga antes de visitarse.
- **2026-10-02 — CSS por ruta:** `index.css` solo trae lo que usan las
  pantallas públicas; tablas/formularios van con `AppLayout`, dashboard y
  gráfica con su pantalla. CSS del login 80,4 → 54,4 KB (14,9 → 10,4 KB
  gzip). Comparado píxel a píxel contra la versión anterior. Un CSS de ruta
  solo define selectores que empiezan por una clase propia
  (`css-por-ruta.test.js`): así se encontró `.miniatura`, definida en
  `ui.css` y en `dashboard.css`, que se teñían mutuamente.
- Fuera `autoprefixer`, `postcss`, `python-multipart` y `pytest-cov` (sin uso).
- **Medido el 2026-10-02** (build + preview, mediana de 3, caché fría):
  login Lighthouse 100, FCP = LCP 505 → **492 ms**, 206 → 201 KB. Con sesión,
  modo oscuro: dashboard LCP 904 → **684 ms**, Productos 892 → **596**,
  Ventas 856 → **552**, Usuarios 840 → **580**; CLS 0 en todas y ninguna
  petición duplicada (cada módulo pide `/dashboard/avisos` una vez: los
  badges y las píldoras de estado lo necesitan).

Mediciones: ver el historial (§9).

---

## 7. Interfaz y convenciones

- **2026-09-21 — Alertas:** sistema único, apilable arriba a la derecha;
  éxito 4 s (`role="status"`), error 7 s (`role="alert"`); el error dice
  SIEMPRE la causa concreta del backend.
- **Validación en dos capas** con los mismos mensajes en español
  (`app/core/validaciones.py` manda; espejo en `src/lib/validaciones.js`).
- **2026-09-27 — Nombres de ítem** con el mismo alfabeto que los de persona
  (letras, tildes, ñ, espacios y apóstrofe).
- **2026-09-28 — "Hoy" es el día de Colombia**, no el de UTC ni el del
  navegador: la entrega "no anterior a hoy" se compara en `America/Bogota`
  (`ZONA_NEGOCIO` en `validaciones.py`, desfase fijo -05:00 porque Colombia no
  tiene horario de verano y Windows no trae tzdata; espejo `diaNegocio` con
  `Intl` en `validaciones.js`). Con UTC, de 19:00 a 24:00 el backend rechazaba
  una entrega de hoy y de madrugada aceptaba una de ayer. Las pruebas de fechas
  fijan el reloj (`vi.setSystemTime` / `monkeypatch`) a las 08:00 y a las
  20:30 de Bogotá; nunca `Date.now()` real.
- **Bloqueo de entrada al teclear** con `Input permitir=` sobre el
  `beforeinput` nativo.
- Entidades de negocio en español (Usuario, Rol, Compra, Venta).
- Multi-tenant real: toda consulta de negocio filtra por `tenant_id` tomado
  del token, nunca de un parámetro que el cliente pueda manipular.

### 2026-09-30 — Permisos por rol (verificados en el backend)

Antes: los roles se guardaban y se editaban, pero ningún endpoint los exigía
(un cajero podía borrar productos y ver costos). Ahora:

- **Catálogo único** en `backend/app/core/catalogo_permisos.py`: 11 módulos
  (dashboard, compras, productos, categorías, marcas, proveedores, ventas,
  pedidos, usuarios, roles, ia), cada uno SOLO con sus acciones (ver, crear,
  editar, cambiar_estado, anular, eliminar). Compras y ventas no se editan
  (se anulan); los pedidos no se eliminan; el dashboard solo se ve. El
  frontend lo lee de `GET /seguridad/permisos`; los permisos efectivos del
  usuario llegan en `GET /seguridad/me`.
- **La seguridad está en el backend.** Cada endpoint declara su permiso con
  `tenant_con_permiso(modulo, accion)` / `usuario_con_permiso(...)`
  (`app/core/permisos.py`) y responde **403** con la causa ("Tu rol «Cajero»
  no tiene permiso para eliminar productos…"). El frontend solo oculta
  botones y bloquea rutas (`components/ConPermiso.jsx`): comodidad.
- **Rol Administrador** (`roles.es_administrador`): acceso total siempre, no
  se elimina, sus permisos no se editan, y solo otro administrador lo
  asigna o modifica a un usuario administrador.
- **Contra la escalada de privilegios:** nadie cambia su propio rol ni edita
  los permisos de su rol; quien no es administrador no concede permisos que
  no tiene; no se desactiva/elimina/degrada al último administrador activo.
- **Costos y márgenes:** `precio_compra` solo lo ve y lo escribe quien tiene
  `compras.ver` (para el resto sale vacío y se ignora al guardar).
- **Roles de ejemplo** en cada empresa nueva (registro, `alta_tenant.py`) y
  en las existentes (migración `a1b2c3d4e5f6`): **Cajero** (ventas y pedidos;
  catálogo en solo lectura; sin compras, costos ni dashboard) y **Bodega**
  (compras sin anular, catálogo y productos; sin ventas ni dashboard).
- `/dashboard/sugerencias-ia` e `/ia/status` eran PÚBLICAS (sin sesión):
  ahora exigen `ia.ver`.
- Quien no ve el dashboard entra a `/` y va directo a su primera pantalla
  permitida.
- Nota de uso: registrar una compra implica elegir proveedor y productos, así
  que un rol con `compras.crear` necesita también `proveedores.ver` y
  `productos.ver` (el rol Bodega ya los trae). Igual crear usuarios necesita
  `roles.ver` para ofrecer los roles.
- Protección: `backend/tests/test_permisos.py` (toda ruta exige el permiso
  esperado; 403 sin el permiso exacto en cada ruta; 404 y cero datos
  ajenos desde otra empresa en cada ruta con id; escalada; costos) y
  `frontend/src/permisos.test.jsx`.

### 2026-10-01 — El plan contratado también se exige en el backend

Hueco encontrado al verificar los permisos: el plan solo escondía módulos
del sidebar y una empresa en Básico podía usar /compras, /ventas o la IA por
la API. Ahora `exigir_permiso` comprueba el plan (o el add-on en
`Tenant.modulos_activos`) ANTES que el rol: 403 «El plan Básico de tu
empresa no incluye Compras…». Grupo y plan mínimo por módulo en
`catalogo_permisos.py`, espejo de `config/modules.js` (`test_planes.py`
exige que coincidan). `ConPermiso` bloquea por plan una URL escrita a mano.

### 2026-10-01 — Sugerencias IA reales (add-on)

Detalle en `docs/ia/README.md`. `GET /ia/sugerencias` calcula con
estadística local: quiebres previsibles, caídas, reposición, ganadores,
patrones de día/franja (hora de Colombia), baja rotación, precios por
margen y proveedor más barato. Cada sugerencia trae su porqué y sus cifras;
sin base suficiente, la sección lo dice con el umbral que falta. **Ningún
dato sale del sistema** ni se leen datos personales de clientes. Costos y
proveedores solo con `compras.ver`. `test_ia.py`, `IaPage.test.jsx`.

### 2026-10-01 — Exportar a CSV en los nueve listados

Sin rutas nuevas: `?formato=csv` en cada listado (misma consulta, filtros,
búsqueda, permiso y campos ocultos que la tabla; todas las filas, tope de
50.000 con la causa). Formato para Excel es-CO (`;`, coma decimal, UTF-8 con
BOM, hora de Bogotá) y celdas tipo fórmula neutralizadas (inyección CSV).
Botón «Exportar CSV» en `TablaRecurso`. `test_exportar.py`.

### 2026-10-02 — Revisión de cierre

- Legal 1.1 (borradores): IA sin terceros, portabilidad por CSV, módulos
  adicionales; auditoría de cookies repetida en vivo: ninguna, sin banner
  (`docs/legal/README.md`).
- Accesibilidad tras el rediseño: **0 violaciones de axe (WCAG 2.1 AA) en
  96 pantallas** (48 por modo, con detalle, edición y formularios con
  errores) y **288 paradas de Tab con foco visible**.
- Setup desde cero probado en una copia limpia sin `.env`: `setup.ps1`
  instala, migra, siembra y deja todo listo en 124 s sin intervención; sus
  servidores arrancan y el login de la demo entra al dashboard.
- Pruebas nuevas para 22 comportamientos que solo cubría `test_permisos.py`
  (`test_endpoints_restantes.py`); escáner de consultas sin `tenant_id`
  (ninguna; probado con un caso canario); 21 acciones destructivas, todas
  con `ModalConfirmar`.
- Eliminados `/dashboard/resumen` y `/dashboard/serie-ventas` (sin
  consumidores; `/resumen` calculaba "hoy" en UTC).
- **Pendiente (decisión del usuario):** respaldos de la base de datos,
  registro de auditoría de accesos y límite de intentos de inicio de sesión
  no existen todavía.

### 2026-10-02 — Integración a main (rediseño + funcionalidad completa)

Aprobada por el usuario. Se fusionó `funcionalidad-completa` (que contiene
`rediseno-monocromo`) en `main` con `--no-ff`, después de traer
`origin/main` a la rama (sin cambios nuevos, sin conflictos). Antes y después
de fusionar: backend 469/469, CORS 25/25, frontend 227/227 y build.
**Ninguna rama de trabajo se borró.**

Para actualizarse después del pull: **no hay migraciones nuevas** ni
variables de entorno nuevas; solo se QUITARON dependencias
(`autoprefixer`, `postcss`, `python-multipart`, `pytest-cov`), así que
basta `npm install` en `frontend/` para limpiar `node_modules`. El seed de
demostración es opcional y re-ancla las fechas a hoy.

Lecciones de entorno de esta integración (no son fallos del código):
- **Docker Desktop apagado = Postgres apagado**: la suite del backend dio
  362 errores "Connection refused 5432" hasta arrancarlo
  (`docker compose -f infra/docker-compose.yml up -d db`).
- **Con la máquina cargada** (navegador, juegos) la suite del frontend con
  el 50 % de los núcleos tuvo fallos por tiempo en pruebas que teclean
  formularios completos; `--maxWorkers=3` pasa 227/227. Con la máquina
  libre pasa con la configuración por defecto.
- Los procesos lanzados desde la terminal de una sesión de Claude mueren al
  terminar el comando: para dejar el producto corriendo se usan las
  entradas `backend` y `frontend-dev` de `.claude/launch.json`.

Riesgos antes de mostrarlo a un cliente y decisiones pendientes del
usuario: ver la sección "Estado para clientes" de `CLAUDE.md`.

**Hallazgo al revisar la demo tras la integración:** `alta_tenant.py` (que
usa `setup.ps1` para crear la "Empresa Demo") traía por defecto el color de
marca `#1E3A5F` (azul): la demo se veía azul pese a la paleta monocromática.
Ahora no impone color (`default=None`); lo protege
`test_scripts_de_arranque.py`. Se limpió el `theme_config` de la "Empresa
Demo" de desarrollo; otras 2 empresas de pruebas viejas conservan ese azul.

### 2026-10-02 — El backend arranca en el 8001 sin pasar `--port`

Caso real: `uvicorn app.main:app --reload` a secas arrancó en el 8000 y el
frontend (que llama al 8001) no lo encontró. El CLI de uvicorn no lee la
configuración del proyecto, así que el puerto pasa a vivir en `Settings.PORT`
(8001 por defecto, leído de `backend/.env`, 1–65535) y lo usan todos los
arranques del proyecto: `python -m app.main` (bloque `__main__` de
`app/main.py`, con recarga en desarrollo), `start-backend.ps1` (activa el
venv, lee el puerto de la configuración y prueba abrirlo antes de arrancar
para detectar rangos reservados por Windows) y `.vscode/launch.json` /
`tasks.json`. No hay `pyproject.toml` ni archivo de configuración de uvicorn
donde fijarlo. Lo protegen las pruebas de puerto de `tests/test_config.py`.

### 2026-09-30 — Verificación de extremo a extremo

Cada entrega importante se verifica usando la app como una persona (clics
reales), confirmando cada dato en Postgres y tras recargar, con una empresa
de prueba propia registrada por la pantalla real (no la de demostración).
Script: `automatizaciones/pruebas/extremo-a-extremo/e2e.cjs`; resultado del
2026-09-30 (58/58) en `docs/pruebas/2026-09-30-extremo-a-extremo.md`.
Hallazgo corregido: al rechazar una sobreventa, el mensaje citaba un número
de venta que nunca llegó a existir; ahora dice "No se pudo registrar la
venta: …" y la venta rechazada se deshace explícitamente.

**Bug encontrado al verificar (2026-09-30):** en desarrollo, StrictMode
suelta y re-engancha los refs al montar, y la salida animada de pantallas
creaba un clon de la pantalla que NO se iba (doble exposición en cada carga).
Ahora el clon solo se inserta si, una microtarea después (antes del pintado),
la pantalla ya no está en el documento. Lo protege
`components/AppLayout.test.jsx`.

---

## 8. Herramientas (skills) instaladas

**2026-09-28** — Instaladas en `.claude/skills/` (nivel proyecto):

| Colección | Para qué se usa aquí |
|---|---|
| `emilkowalski/skills` (`animate`, `improve-animations`, `review-animations`, `emil-design-eng`, …) | Construir, auditar y revisar movimiento |
| `Leonxlnx/taste-skill` (`design-taste-frontend`, …) con diales **DESIGN_VARIANCE 3 · MOTION_INTENSITY 5 · VISUAL_DENSITY 8** | ERP denso: estructura clara, movimiento sobrio, mucha información |
| `impeccable` (+ `PRODUCT.md` en la raíz, hook detector en `.claude/settings.local.json`) | Detector de antipatrones (`npx impeccable detect src/`) y pulido |

**Alcance:** las skills se usan SOLO para movimiento, rendimiento y pulido.
Paleta, tipografías y layout aprobados mandan sobre cualquier consejo de una
skill (Impeccable desaconseja Inter; aquí no se cambia).

---

## 9. Historial

| Fecha | Decisión / hito |
|---|---|
| 2026-10-13 | Pulido final: horas en Colombia en pantalla y PDF, cifras sin partir, detalles a 720 px, objetivos táctiles de 40–44 px, cocina en tablet, cero avisos y 0 vulnerabilidades, revisión de secretos; repositorio compartido con el compañero (§0) |
| 2026-10-12 | Datos de demostración: Donde Tavo con 90 días de historia y Café Central para el aislamiento, cuentas por rol solo en desarrollo, y reglas nuevas de la IA (temporadas, picos, carta, alzas, mermas, diferencias de caja) (§0) |
| 2026-10-12 | Fase 8: utilidad real en el dashboard, periodo Semana, donas de participación (máx. 6 partes), pantalla de Reportes con CSV por sección y PDF (§0) |
| 2026-10-12 | Fase 7: cada rol entra a su pantalla con su menú, modo enfocado para cocina, PWA instalable con service worker propio y aviso de sin conexión (§0) |
| 2026-10-12 | Fase 6: caja (cobro con comprobante interno, varios medios, propina voluntaria, impuesto desglosado, dividir la cuenta, apertura y cierre con cuadre y motivo) y gastos; nota legal de factura electrónica (§0) |
| 2026-10-12 | Fase 5: pantalla de cocina (comandas en vivo, Tomar/Finalizar con quién y cuándo, demora marcada, sonido opcional, avisos de anulaciones) (§0) |
| 2026-10-12 | Fase 4: órdenes con comanda (consecutivo por jornada, descuento de insumos en una transacción, comandas por envío, anular con motivo devolviendo lo que salió, tablero, mesas, impresión detrás de una interfaz) reemplazan a los Pedidos (§0) |
| 2026-10-12 | Fase 3: mermas con motivo, conteos físicos con ajuste valorizado, historial general de movimientos, carga inicial desde plantilla Excel/CSV revisada fila por fila (§0) |
| 2026-10-12 | Fase 2: carta con recetas (costo, margen, % de costo en vivo), modificadores, combos con vigencia, agotado hoy, fotos de plato; inventario de INSUMOS con unidades y promedio ponderado; compras de insumos; IA y dashboard sobre insumos (§0) |
| 2026-10-12 | Fase 1: branding en un archivo ("JS Restaurante"), Marcas eliminada, Ajustes del restaurante (negocio, logo, operación, impresoras, jornada, zonas y mesas), imágenes WebP procesadas en el servidor (§0) |
| 2026-10-12 | **Producto Tavo** nace como copia del Producto JS (`8146ea0`) en repo propio; mapa de puertos 5175/4175/8002/5433/5679, Docker aislado (`name: tavo`), scripts que no tocan al otro producto, `verificar-puertos.ps1`, guarda contra `uvicorn` a secas (§0, §1) |
| 2026-09-15 | Fase 0: limpieza de código muerto y origen único de estilos |
| 2026-09-18 | Movimiento: "solo cuatro animaciones" (sustituida) |
| 2026-09-19 | Densidad y alineación: todo centrado, tabla única, formularios 720 px |
| 2026-09-21 | Sistema único de alertas; errores con causa concreta; panel de avisos; primera carga < 0,5 s |
| 2026-09-25 | Dashboard según la maqueta; movimiento "cómo, no cuánto"; Recharts eliminado. Medido: login Lighthouse 100 (FCP 449 ms, LCP 491 ms, TBT 0, CLS 0); dashboard FCP 116 ms, LCP 648 ms, CLS 0, 0 tareas largas |
| 2026-09-27 | Grupos del sidebar cerrados al cargar y uno a la vez; nombres de ítem sin dígitos; arranque en máquinas nuevas; red privada en CORS de desarrollo |
| 2026-09-28 | Paleta Espresso/Marfil + Blanco/Crema (sustituye al verde bosque) |
| 2026-09-28 | Validación de fechas contra el día de Colombia (backend y frontend); pruebas con reloj fijo |
| 2026-09-29 | Arreglos de `review-animations`: spinner vivo y fades con movimiento reducido, tarjetas de lectura sin elevación, bloques 300 ms, gráfica ≤ 1,2 s, pulsación en `.btn`. No se tocan la luz 1:1 ni el `scaleY` del FLIP (§5) |
| 2026-09-29 | Salida animada de pantallas: se acepta su coste medido (1 cuadro en ~2-3 de 10 navegaciones); View Transitions descartado (§5) |
| 2026-09-30 | Permisos por rol verificados en el backend (403 con causa), rol Administrador protegido, roles de ejemplo Cajero y Bodega, costo oculto sin `compras.ver`, rutas IA ya no públicas (§7) |
| 2026-09-30 | Verificación de extremo a extremo 58/58; la sobreventa ya no cita un número de venta fantasma (§7) |
| 2026-09-30 | Sin `datetime.utcnow`: de 6.506 avisos a 2 (ajenos); `utcnow` ahora falla la suite; worktree viejo eliminado (§4) |
| 2026-09-30 | Demo con fechas relativas a hoy en cada corrida e historial de 6 meses; hallazgo: el dashboard usa días UTC (§4) |
| 2026-09-30 | Dashboard por día calendario de Colombia: Hoy/Mes/Año y los buckets de la gráfica en hora de Bogotá, consultados en UTC naive; contrato del API intacto (§4) |
| 2026-09-30 | Legal Colombia (borradores): política de datos, términos, cláusula de transmisión, aceptación con versión y fecha en el registro, pie legal, sin cookies ni servicios externos (§4, `docs/legal/`) |
| 2026-09-30 | Accesibilidad AA: 0 violaciones de axe en 98 pantallas (oscuro y claro), foco visible en todo, selector como combobox ARIA 1.2, ayudas y errores asociados a su campo (§4) |
| 2026-09-30 | Espacios: formularios a 720 px en todas las pantallas, columnas proporcionales, tabla → tarjetas cuando no cabe (la página ya no se desplaza de lado a 768–900 / 1180 px) (§4) |
| 2026-09-30 | Login y registro: panel transparente centrado sobre espresso, esquema oscuro forzado, sin foto ni bucles de ambiente; trazo de campo a 3,8:1 (§4) |
| 2026-10-01 | Paleta monocromática estricta (claro principal; Espresso/Marfil pasa a histórica), marco con sidebar blanco, badges y barra superior, dashboard con KPI de capa doble, tablas y controles planos (§2, §4) |
| 2026-10-01 | Login y registro revertidos al diseño del 2026-09-30 sobre la paleta monocromática (§4) |
| 2026-10-01 | Precarga de la ruta inicial (sin la espera de ~300 ms de Suspense) (§6) |
| 2026-10-01 | Plan exigido en el backend; Sugerencias IA reales sin servicios externos; exportación CSV en los nueve listados (§7) |
| 2026-10-02 | Legal 1.1; a11y 0 violaciones en 96 pantallas y foco en 288 paradas; setup probado en copia limpia; CSS por ruta (login 54 KB); LCP del dashboard 904 → 684 ms (§6, §7) |
| 2026-10-02 | Integración a main de `funcionalidad-completa` (incluye `rediseno-monocromo`): 469 + 25 + 227 pruebas y build en verde, sin conflictos, ramas de trabajo conservadas (§7) |
| 2026-10-02 | Puerto del backend en `Settings.PORT` (8001): `python -m app.main`, `start-backend.ps1` y VS Code ya no dependen de `--port` (§7) |
| 2026-09-28 | Skills de movimiento instaladas; reglas de curvas (`--ease-suave`, `--resorte`); movimiento completo implementado a mano sin Framer Motion; spinner `linear` como excepción; cinco bugs de movimiento corregidos (§5) |
