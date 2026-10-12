// PRUEBA DE EXTREMO A EXTREMO (resultado documentado en docs/pruebas/2026-09-30-extremo-a-extremo.md): la app usada como una persona (clics y
// teclado reales en la interfaz), y cada resultado confirmado DIRECTAMENTE en
// Postgres y después de recargar la página. Empresa de prueba propia,
// registrada por la pantalla real de registro.
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
// Playwright no es dependencia del proyecto: se usa el que haya instalado
// (p. ej. el de `npx playwright`) indicando su ruta en PLAYWRIGHT_MODULE.
const pw = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const BASE = process.env.BASE || "http://localhost:5173";
const API = "http://localhost:8001/api/v1";
const DIR = __dirname;
// Resultados y PDFs descargados van FUERA del repositorio.
const SALIDA = process.env.SALIDA_E2E || require("os").tmpdir();
const PY = process.env.PYTHON_BACKEND || path.resolve(__dirname, "../../../backend/venv/Scripts/python.exe");
const SELLO = Date.now().toString(36);
const EMPRESA = `Verificacion Integral ${SELLO}`;
const CORREO = `e2e.${SELLO}@prueba.co`;
const CLAVE = `Prueba-${SELLO}-OK`;

const resultados = [];
let tenantId = null;

function sql(consulta, params = {}) {
  const r = spawnSync(PY, [path.join(DIR, "consultar.py"), consulta, JSON.stringify(params)], { encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  if (r.status !== 0) throw new Error(`SQL falló: ${r.stderr}`);
  return JSON.parse(r.stdout);
}
const uno = (consulta, params) => sql(consulta, { t: tenantId, ...params })[0];
function comprobar(prueba, ok, evidencia) {
  resultados.push({ prueba, ok: Boolean(ok), evidencia });
  console.log(`${ok ? "OK  " : "FALLA"} ${prueba} :: ${typeof evidencia === "string" ? evidencia : JSON.stringify(evidencia)}`);
}
function textoPdf(ruta) {
  const r = spawnSync(PY, [path.join(DIR, "texto_pdf.py"), ruta], { encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  return r.stdout;
}

(async () => {
  const navegador = await pw.chromium.launch();
  const ctx = await navegador.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const p = await ctx.newPage();
  const errores = [];
  p.on("pageerror", (e) => errores.push(String(e)));

  const ir = async (ruta) => {
    await p.goto(BASE + ruta);
    await p.waitForLoadState("networkidle");
  };
  const alerta = async () => (await p.locator(".alerta").last().textContent({ timeout: 8000 })).trim();
  const guardar = async (texto = /^Guardar/) => {
    await p.getByRole("button", { name: texto }).last().click();
  };
  const confirmarDialogo = async (texto) => {
    const d = p.getByRole("dialog");
    await d.getByRole("button", { name: texto, exact: true }).click();
    await d.waitFor({ state: "detached", timeout: 8000 }).catch(() => {});
  };
  const recargarYVer = async (texto) => {
    await p.reload();
    await p.waitForLoadState("networkidle");
    return (await p.getByText(texto, { exact: false }).count()) > 0;
  };
  const idDeUrl = () => p.url().split("/").filter(Boolean).pop();

  // ------------------------------------------------------------------ Registro
  await ir("/registro");
  await p.getByLabel("Nombre de la empresa").fill(EMPRESA);
  await p.getByLabel("Correo electrónico").fill(CORREO);
  await p.getByLabel("Contraseña").fill(CLAVE);
  const casilla = p.getByRole("checkbox");
  if (await casilla.count()) await casilla.first().check(); // (fase 6: aceptación de la política)
  await p.getByRole("button", { name: "Crear cuenta" }).click();
  await p.waitForURL((u) => !u.pathname.startsWith("/registro"), { timeout: 15000 });
  tenantId = sql("select tenant_id from usuarios where email = :e", { e: CORREO })[0]?.tenant_id;
  comprobar("Registro por la pantalla real crea la empresa y su administrador", tenantId, { tenantId, url: p.url() });

  // ------------------------------------------------- Catálogos simples (x2)
  for (const cat of [
    { ruta: "/compras/categorias", tabla: "categorias", nombre: "Bebidas Prueba", editado: "Bebidas Frías", temporal: "Categoría Temporal", singular: "categoría" },
    { ruta: "/compras/marcas", tabla: "marcas", nombre: "Marca Propia", editado: "Marca Propia Premium", temporal: "Marca Temporal", singular: "marca" },
  ]) {
    await ir(`${cat.ruta}/nuevo`);
    await p.getByLabel("Nombre").fill(cat.nombre);
    await p.getByLabel("Descripción").fill("Creada en la prueba de extremo a extremo");
    await guardar();
    const aviso = await alerta();
    const fila = uno(`select id, nombre, activo, descripcion from ${cat.tabla} where tenant_id = :t and nombre = :n`, { n: cat.nombre });
    comprobar(`${cat.tabla}: crear`, fila && aviso, { alerta: aviso, bd: fila });
    comprobar(`${cat.tabla}: sigue tras recargar`, await recargarYVer(cat.nombre), "visible en el listado");

    await ir(`${cat.ruta}/${fila.id}`);
    comprobar(`${cat.tabla}: ver detalle`, (await p.getByRole("heading", { name: cat.nombre }).count()) > 0, "título del detalle");
    await p.getByRole("button", { name: "Editar" }).click();
    await p.getByLabel("Nombre").fill(cat.editado);
    await guardar(/Guardar cambios/);
    await alerta();
    const editada = uno(`select nombre from ${cat.tabla} where id = :id`, { id: fila.id });
    comprobar(`${cat.tabla}: editar`, editada.nombre === cat.editado, { bd: editada });
    comprobar(`${cat.tabla}: edición sigue tras recargar`, await recargarYVer(cat.editado), "visible");

    await p.getByRole("button", { name: "Desactivar" }).click();
    await confirmarDialogo("Desactivar");
    await alerta();
    const inactiva = uno(`select activo from ${cat.tabla} where id = :id`, { id: fila.id });
    await p.reload();
    await p.getByRole("button", { name: "Activar" }).click();
    await confirmarDialogo("Activar");
    await alerta();
    const reactivada = uno(`select activo from ${cat.tabla} where id = :id`, { id: fila.id });
    comprobar(`${cat.tabla}: cambiar estado (desactivar y activar)`, inactiva.activo === false && reactivada.activo === true, { tras_desactivar: inactiva, tras_activar: reactivada });

    // Eliminar: uno temporal
    await ir(`${cat.ruta}/nuevo`);
    await p.getByLabel("Nombre").fill(cat.temporal);
    await guardar();
    await alerta();
    const temp = uno(`select id from ${cat.tabla} where tenant_id = :t and nombre = :n`, { n: cat.temporal });
    await ir(`${cat.ruta}/${temp.id}`);
    await p.getByRole("button", { name: "Eliminar" }).click();
    await confirmarDialogo("Eliminar");
    await p.waitForURL(`**${cat.ruta}`);
    const borrado = uno(`select count(*) as n from ${cat.tabla} where id = :id`, { id: temp.id });
    comprobar(`${cat.tabla}: eliminar`, borrado.n === 0, { filas_en_bd: borrado.n });
    cat.id = fila.id;
  }

  const [categoria, marca] = [
    uno("select id, nombre from categorias where tenant_id = :t"),
    uno("select id, nombre from marcas where tenant_id = :t"),
  ];

  // ---------------------------------------------------------------- Proveedores
  await ir("/compras/proveedores/nuevo");
  await p.getByLabel("NIT").pressSequentially("8909039388");
  await p.getByLabel("Razón social").fill("Distribuidora Prueba");
  await p.getByLabel("Representante legal").fill("Ana Prueba");
  await p.getByLabel("Teléfono").pressSequentially("3001234567");
  await guardar();
  const avisoProv = await alerta();
  const prov = uno("select id, razon_social, nit, telefono, activo from proveedores where tenant_id = :t");
  comprobar("proveedores: crear (jurídica, NIT con DV)", prov && prov.nit.startsWith("890903938"), { alerta: avisoProv, bd: prov });
  comprobar("proveedores: sigue tras recargar", await recargarYVer("Distribuidora Prueba"), "visible");
  await ir(`/compras/proveedores/${prov.id}`);
  comprobar("proveedores: ver detalle", (await p.getByRole("heading", { name: "Distribuidora Prueba" }).count()) > 0, "título");
  await p.getByRole("button", { name: "Editar" }).click();
  await p.getByLabel("Razón social").fill("Distribuidora Prueba Andina");
  await guardar(/Guardar cambios/);
  await alerta();
  comprobar("proveedores: editar", uno("select razon_social from proveedores where id = :id", { id: prov.id }).razon_social === "Distribuidora Prueba Andina", "razón social nueva en BD");
  comprobar("proveedores: edición sigue tras recargar", await recargarYVer("Distribuidora Prueba Andina"), "visible");
  await p.getByRole("button", { name: "Desactivar" }).click();
  await confirmarDialogo("Desactivar");
  await alerta();
  const provInactivo = uno("select activo from proveedores where id = :id", { id: prov.id });
  await p.reload();
  await p.getByRole("button", { name: "Activar" }).click();
  await confirmarDialogo("Activar");
  await alerta();
  comprobar("proveedores: cambiar estado", provInactivo.activo === false && uno("select activo from proveedores where id = :id", { id: prov.id }).activo === true, "false -> true");
  // eliminar uno temporal (persona natural)
  await ir("/compras/proveedores/nuevo");
  await p.getByLabel("Tipo de persona").selectOption("natural");
  await p.getByLabel("Tipo de documento").selectOption({ index: 1 });
  await p.getByLabel("Número de documento").pressSequentially("1020304050");
  await p.getByLabel("Nombres").fill("Pedro");
  await p.getByLabel("Apellidos").fill("Temporal");
  await guardar();
  await alerta();
  const provTemp = uno("select id from proveedores where tenant_id = :t and numero_documento = '1020304050'");
  await ir(`/compras/proveedores/${provTemp.id}`);
  await p.getByRole("button", { name: "Eliminar" }).click();
  await confirmarDialogo("Eliminar");
  await p.waitForURL("**/compras/proveedores");
  comprobar("proveedores: eliminar", uno("select count(*) as n from proveedores where id = :id", { id: provTemp.id }).n === 0, "0 filas");

  // ------------------------------------------------------------------ Productos
  await ir("/compras/productos/nuevo");
  await p.getByLabel("Nombre").fill("Gaseosa Prueba");
  await p.getByLabel("SKU").pressSequentially("GAS-E2E");
  await p.getByLabel("Categoría").selectOption({ label: categoria.nombre });
  await p.getByLabel("Marca").selectOption({ label: marca.nombre });
  await p.getByLabel("Precio de venta").pressSequentially("3000");
  await p.getByLabel("Costo de compra").pressSequentially("1800");
  await p.getByLabel("Stock mínimo").fill("5");
  await guardar();
  await alerta();
  const prod = uno("select id, nombre, sku, precio, precio_compra, stock, stock_minimo, categoria_id, marca_id from productos where tenant_id = :t and sku = 'GAS-E2E'");
  comprobar("productos: crear (con categoría y marca; stock nace en 0)", prod && prod.stock === 0 && prod.precio === 3000 && prod.precio_compra === 1800 && prod.categoria_id === categoria.id, { bd: prod });
  comprobar("productos: sigue tras recargar", await recargarYVer("Gaseosa Prueba"), "visible");
  await ir(`/compras/productos/${prod.id}`);
  comprobar("productos: ver detalle", (await p.getByRole("heading", { name: "Gaseosa Prueba" }).count()) > 0, "título");
  await p.getByRole("button", { name: "Editar" }).click();
  await p.getByLabel("Precio de venta").fill("");
  await p.getByLabel("Precio de venta").pressSequentially("3200");
  await guardar(/Guardar cambios/);
  await alerta();
  comprobar("productos: editar precio", uno("select precio from productos where id = :id", { id: prod.id }).precio === 3200, "3000 -> 3200");
  comprobar("productos: edición sigue tras recargar", await recargarYVer("3.200"), "precio nuevo visible");
  await p.getByRole("button", { name: "Desactivar" }).click();
  await p.getByRole("dialog").getByRole("button", { name: /Desactivar/ }).click();
  await alerta();
  const prodInactivo = uno("select activo from productos where id = :id", { id: prod.id });
  await p.reload();
  await p.getByRole("button", { name: "Activar" }).click();
  await p.getByRole("dialog").getByRole("button", { name: /Activar/ }).click();
  await alerta();
  comprobar("productos: cambiar estado", prodInactivo.activo === false && uno("select activo from productos where id = :id", { id: prod.id }).activo === true, "false -> true");
  // Eliminar: el listado de productos no ofrece eliminar en la interfaz;
  // se prueba con uno temporal sin movimientos por la API con la sesión real.
  await ir("/compras/productos/nuevo");
  await p.getByLabel("Nombre").fill("Producto Temporal");
  await p.getByLabel("SKU").pressSequentially("TMP-E2E");
  await p.getByLabel("Precio de venta").pressSequentially("1000");
  await guardar();
  await alerta();
  const tmp = uno("select id from productos where tenant_id = :t and sku = 'TMP-E2E'");
  const borrar = await p.evaluate(async ({ api, id }) => {
    const r = await fetch(`${api}/compras/productos/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${localStorage.getItem("js_company_token")}` } });
    return r.status;
  }, { api: API, id: tmp.id });
  comprobar("productos: eliminar (sin movimientos; la interfaz no tiene botón)", borrar === 204 && uno("select count(*) as n from productos where id = :id", { id: tmp.id }).n === 0, { http: borrar });

  // ------------------------------------------------------------------- Compras
  const stock = () => uno("select stock from productos where id = :id", { id: prod.id }).stock;
  const registrarCompra = async ({ cantidad, confirmar }) => {
    await ir("/compras/nuevo");
    await p.getByPlaceholder("Buscar proveedor...").fill("Andina");
    await p.getByRole("option", { name: /Distribuidora Prueba Andina/ }).click();
    const todos = p.getByLabel(/Mostrar todos los productos/);
    if (await todos.count()) await todos.check();
    await p.getByLabel("Producto").first().selectOption({ label: /Gaseosa Prueba/.test("") ? "" : undefined, index: 1 }).catch(async () => {
      await p.getByLabel("Producto").first().selectOption({ index: 1 });
    });
    await p.getByLabel("Cantidad").first().fill(String(cantidad));
    await p.getByLabel("Costo unitario").first().fill("");
    await p.getByLabel("Costo unitario").first().pressSequentially("1800");
    const conf = p.getByLabel(/Confirmar de inmediato/);
    if (confirmar) await conf.check();
    else if (await conf.isChecked()) await conf.uncheck();
    await p.getByRole("button", { name: /^Registrar compra/ }).click();
    await alerta();
    return uno("select id, numero, estado, total from compras where tenant_id = :t order by numero desc limit 1");
  };
  const antes = stock();
  const compra = await registrarCompra({ cantidad: 20, confirmar: false });
  comprobar("compras: registrar pendiente (no mueve stock)", compra.estado === "pendiente" && stock() === antes, { compra, stock: stock() });
  await ir(`/compras/${compra.id}`);
  await p.getByRole("button", { name: "Confirmar compra" }).click();
  await confirmarDialogo("Confirmar");
  await alerta();
  const trasConfirmar = stock();
  comprobar("compras: confirmar sube el stock EXACTAMENTE lo comprado", trasConfirmar === antes + 20, { antes, despues: trasConfirmar, estado: uno("select estado from compras where id = :id", { id: compra.id }).estado });
  // PDF de compra desde el botón de la interfaz
  const [respPdfCompra] = await Promise.all([
    p.waitForResponse((r) => r.url().endsWith(`/compras/compras/${compra.id}/pdf`)),
    p.getByRole("button", { name: /PDF/ }).first().click(),
  ]);
  fs.writeFileSync(path.join(SALIDA, "compra.pdf"), await respPdfCompra.body());
  const txtCompra = textoPdf(path.join(SALIDA, "compra.pdf"));
  comprobar("compras: PDF abre y trae los datos correctos", /PAGINAS=1/.test(txtCompra) && /Distribuidora Prueba Andina/.test(txtCompra) && /GAS-E2E/.test(txtCompra) && /\b20\b/.test(txtCompra) && /36\.000/.test(txtCompra), txtCompra.split("\n").filter((l) => /COMP|Andina|GAS|36\.000|Total/.test(l)).join(" | "));
  await p.getByRole("button", { name: "Anular" }).click();
  await confirmarDialogo("Anular compra");
  await alerta();
  comprobar("compras: anular devuelve el stock a su valor previo", stock() === antes, { antes, tras_anular: stock(), estado: uno("select estado from compras where id = :id", { id: compra.id }).estado });
  const movs = sql("select tipo, cantidad, stock_resultante from movimientos_inventario where producto_id = :id order by created_at", { id: prod.id });
  comprobar("compras: cada movimiento queda registrado (entrada y reversa)", movs.length === 2 && movs[0].cantidad === 20 && movs[1].cantidad === -20, movs);
  const compra2 = await registrarCompra({ cantidad: 20, confirmar: true });
  comprobar("compras: registrar confirmada de inmediato", compra2.estado === "confirmada" && stock() === antes + 20, { compra2, stock: stock() });

  // -------------------------------------------------------------------- Ventas
  const registrarVenta = async (cantidad) => {
    await ir("/ventas/nuevo");
    await p.getByLabel("Nombre del cliente").fill("Cliente Prueba");
    await p.getByLabel("Producto").first().selectOption({ index: 1 });
    await p.getByLabel("Cantidad").first().fill(String(cantidad));
    const precio = p.getByLabel(/Precio/).first();
    if ((await precio.inputValue()) === "") await precio.pressSequentially("3200");
    await p.getByLabel(/Completar de inmediato/).check();
    await p.getByRole("button", { name: /^Registrar venta/ }).click();
  };
  const antesVenta = stock();
  await registrarVenta(3);
  await alerta();
  const venta = uno("select id, estado, total from ventas where tenant_id = :t order by numero desc limit 1");
  comprobar("ventas: completar baja el stock", venta.estado === "completada" && stock() === antesVenta - 3, { venta, antes: antesVenta, despues: stock() });
  await registrarVenta(1000);
  await p.waitForTimeout(2500);
  // La interfaz lo bloquea ANTES de enviar y muestra la causa en el formulario.
  const avisoError = ((await p.getByText(/Stock insuficiente/).first().textContent({ timeout: 5000 }).catch(() => "")) || "").trim();
  const ventasTras = uno("select count(*) as n from ventas where tenant_id = :t").n;
  comprobar("ventas: vender más de lo que hay se bloquea en pantalla con mensaje claro (y no guarda nada)", /disponible 17/.test(avisoError) && /solicitado 1000/.test(avisoError) && ventasTras === 1 && stock() === 17, { mensaje: avisoError, ventas_en_bd: ventasTras, stock: stock() });
  // Y el BACKEND también lo bloquea solo (sin el formulario de por medio).
  const directo = await p.evaluate(async ({ api, productoId }) => {
    const r = await fetch(`${api}/ventas/ventas`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("js_company_token")}` },
      body: JSON.stringify({ cliente_nombre: "Cliente Directo", fecha: new Date(Date.now() - 60000).toISOString(), confirmar: true, items: [{ producto_id: productoId, cantidad: 1000, precio_unitario: "3200" }] }),
    });
    return { status: r.status, detail: (await r.json()).detail };
  }, { api: API, productoId: prod.id });
  comprobar("ventas: el backend rechaza la sobreventa por sí solo (409 con la causa)", directo.status === 409 && directo.detail === "No se pudo registrar la venta: el producto Gaseosa Prueba solo tiene 17 unidades y se pidieron 1000." && stock() === 17 && uno("select count(*) as n from ventas where tenant_id = :t").n === 1, directo);
  await ir(`/ventas/${venta.id}`);
  const [respPdfVenta] = await Promise.all([
    p.waitForResponse((r) => r.url().endsWith(`/ventas/ventas/${venta.id}/pdf`)),
    p.getByRole("button", { name: /PDF/ }).first().click(),
  ]);
  fs.writeFileSync(path.join(SALIDA, "venta.pdf"), await respPdfVenta.body());
  const txtVenta = textoPdf(path.join(SALIDA, "venta.pdf"));
  comprobar("ventas: PDF abre y trae los datos correctos", /Cliente Prueba/.test(txtVenta) && /GAS-E2E/.test(txtVenta) && /9\.600/.test(txtVenta), txtVenta.split("\n").filter((l) => /VEN-|Cliente|GAS|9\.600/.test(l)).join(" | "));

  // ------------------------------------------------------------------- Pedidos
  await ir("/ventas/pedidos/nuevo");
  await p.getByLabel("Cliente").fill("Tienda Prueba");
  await p.getByLabel("Teléfono").pressSequentially("3109876543");
  await p.getByLabel("Dirección de entrega").fill("Calle 10 # 20-30");
  await p.getByLabel("Producto").first().selectOption({ index: 1 });
  await p.getByLabel("Cantidad").first().fill("4");
  await p.getByRole("button", { name: "Agregar producto" }).click();
  await p.getByLabel("Producto de la línea 2").selectOption({ index: 1 });
  await p.getByLabel("Cantidad de la línea 2").fill("2");
  const lineasAntes = await p.getByRole("button", { name: "Quitar producto" }).count();
  await p.getByRole("button", { name: "Quitar producto" }).last().click();
  const lineasDespues = await p.getByRole("button", { name: "Quitar producto" }).count();
  await p.getByRole("button", { name: /^Registrar pedido/ }).click();
  await alerta();
  const pedido = uno("select id, codigo, estado from (select id, numero, estado, 'PED-' || lpad(numero::text, 6, '0') as codigo from pedidos where tenant_id = :t) x order by codigo desc limit 1");
  const items1 = sql("select cantidad from pedido_items where pedido_id = :id", { id: pedido.id });
  comprobar("pedidos: crear agregando y quitando líneas", lineasAntes === 2 && lineasDespues === 1 && items1.length === 1 && items1[0].cantidad === 4, { lineasAntes, lineasDespues, items_en_bd: items1 });
  await ir(`/ventas/pedidos/${pedido.id}/editar`);
  await p.getByRole("button", { name: "Agregar producto" }).click();
  await p.getByLabel("Producto de la línea 2").selectOption({ index: 1 });
  await p.getByLabel("Cantidad de la línea 2").fill("1");
  await p.getByLabel("Prioridad").selectOption({ label: "Alta" });
  await guardar(/Guardar cambios/);
  await alerta();
  const items2 = sql("select cantidad from pedido_items where pedido_id = :id order by cantidad desc", { id: pedido.id });
  comprobar("pedidos: editar agrega una línea y cambia prioridad", items2.length === 2 && uno("select prioridad from pedidos where id = :id", { id: pedido.id }).prioridad === "alta", { items_en_bd: items2 });
  for (const [boton, estado] of [["En proceso", "en_proceso"], ["Listo", "listo"], ["Entregado", "entregado"]]) {
    await ir(`/ventas/pedidos/${pedido.id}`);
    await p.getByRole("button", { name: new RegExp(boton) }).first().click();
    const nota = p.getByLabel("Nota del cambio");
    if (await nota.count()) await nota.fill(`paso a ${estado}`);
    await confirmarDialogo(boton);
    await alerta();
    const e = uno("select estado from pedidos where id = :id", { id: pedido.id });
    comprobar(`pedidos: cambiar estado a ${estado}`, e.estado === estado, e);
  }
  const eventos = sql("select estado, nota from pedido_eventos where pedido_id = :id order by created_at", { id: pedido.id });
  await ir(`/ventas/pedidos/${pedido.id}`);
  const lineaTiempo = await p.getByRole("list", { name: "Historial del pedido" }).locator("li").count();
  // Registrado, editado y tres cambios de estado: cada paso deja su evento.
  comprobar("pedidos: seguimiento (línea de tiempo) en BD y en pantalla", eventos.length === 5 && lineaTiempo === eventos.length && eventos.at(-1).estado === "entregado" && eventos[1].nota === "Pedido editado", { eventos: eventos.map((e) => `${e.estado}: ${e.nota}`), en_pantalla: lineaTiempo });
  const [respPdfPedido] = await Promise.all([
    p.waitForResponse((r) => r.url().endsWith(`/ventas/pedidos/${pedido.id}/pdf`)),
    p.getByRole("button", { name: /PDF/ }).first().click(),
  ]);
  fs.writeFileSync(path.join(SALIDA, "pedido.pdf"), await respPdfPedido.body());
  const txtPedido = textoPdf(path.join(SALIDA, "pedido.pdf"));
  comprobar("pedidos: PDF abre y trae los datos correctos", /Tienda Prueba/.test(txtPedido) && /GAS-E2E/.test(txtPedido) && /Entregado/i.test(txtPedido), txtPedido.split("\n").filter((l) => /PED-|Tienda|GAS|Entregado|Total/.test(l)).join(" | "));

  // ------------------------------------------------------------------ Usuarios
  const rolCajero = uno("select id from roles where tenant_id = :t and nombre = 'Cajero'");
  await ir("/seguridad/usuarios/nuevo");
  await p.getByLabel("Nombre completo").fill("Pedro Pruebas");
  await p.getByLabel("Correo electrónico").fill(`pedro.${SELLO}@prueba.co`);
  await p.getByLabel("Contraseña").fill(`Otra-${SELLO}-Clave`);
  await p.getByLabel("Rol").selectOption({ label: "Cajero" });
  await guardar(/Crear usuario|Guardar/);
  await alerta();
  const usr = uno("select id, nombre_completo, rol_id, activo from usuarios where tenant_id = :t and email = :e", { e: `pedro.${SELLO}@prueba.co` });
  comprobar("usuarios: crear con rol Cajero", usr && usr.rol_id === rolCajero.id, { bd: usr });
  comprobar("usuarios: sigue tras recargar", await recargarYVer("Pedro Pruebas"), "visible");
  await ir(`/seguridad/usuarios/${usr.id}`);
  comprobar("usuarios: ver detalle", (await p.getByRole("heading", { name: "Pedro Pruebas" }).count()) > 0, "título");
  await p.getByRole("button", { name: "Editar" }).click();
  await p.getByLabel("Nombre completo").fill("Pedro Pruebas Ruiz");
  await guardar(/Guardar cambios/);
  await alerta();
  comprobar("usuarios: editar", uno("select nombre_completo from usuarios where id = :id", { id: usr.id }).nombre_completo === "Pedro Pruebas Ruiz", "nombre nuevo en BD");
  await p.getByRole("button", { name: "Desactivar" }).click();
  await confirmarDialogo("Desactivar");
  await alerta();
  comprobar("usuarios: cambiar estado", uno("select activo from usuarios where id = :id", { id: usr.id }).activo === false, "desactivado");
  await p.reload();
  await p.getByRole("button", { name: "Eliminar" }).click();
  await confirmarDialogo("Eliminar");
  await p.waitForURL("**/seguridad/usuarios");
  comprobar("usuarios: eliminar", uno("select count(*) as n from usuarios where id = :id", { id: usr.id }).n === 0, "0 filas");

  // --------------------------------------------------------------------- Roles
  await ir("/seguridad/roles/nuevo");
  await p.getByLabel("Nombre del rol").fill("Auditor");
  await p.getByRole("checkbox", { name: "Ventas: Ver" }).check();
  await p.getByRole("checkbox", { name: "Compras: Ver" }).check();
  await guardar();
  await alerta();
  const rol = uno("select id, permisos::text as permisos from roles where tenant_id = :t and nombre = 'Auditor'");
  comprobar("roles: crear con permisos desde la matriz", rol && /"ventas": \["ver"\]/.test(rol.permisos) && /"compras": \["ver"\]/.test(rol.permisos), { bd: rol });
  comprobar("roles: sigue tras recargar", await recargarYVer("Auditor"), "visible");
  await ir(`/seguridad/roles/${rol.id}`);
  comprobar("roles: ver detalle", (await p.getByRole("heading", { name: "Auditor" }).count()) > 0, "título");
  await p.getByRole("button", { name: "Editar" }).click();
  await p.getByRole("checkbox", { name: "Pedidos: Ver" }).check();
  await guardar(/Guardar cambios/);
  await alerta();
  comprobar("roles: editar permisos", /"pedidos": \["ver"\]/.test(uno("select permisos::text as p from roles where id = :id", { id: rol.id }).p), "pedidos:ver agregado");
  await p.getByRole("button", { name: "Eliminar" }).click();
  await confirmarDialogo("Eliminar");
  await p.waitForURL("**/seguridad/roles");
  comprobar("roles: eliminar", uno("select count(*) as n from roles where id = :id", { id: rol.id }).n === 0, "0 filas");

  // ----------------------------------------------------------------- Dashboard
  await ir("/");
  await p.waitForSelector(".producto", { timeout: 15000 });
  await p.waitForTimeout(1500);
  const vendido = (await p.locator(".cifra-grande").textContent()).trim();
  const primero = (await p.locator(".producto__nombre").first().textContent()).trim();
  const panel = await p.evaluate(async (api) => {
    const r = await fetch(`${api}/dashboard/panel?periodo=mes`, { headers: { Authorization: `Bearer ${localStorage.getItem("js_company_token")}` } });
    return r.json();
  }, API);
  comprobar("dashboard: refleja la venta y la compra nuevas", /9\.600/.test(vendido) && primero === "Gaseosa Prueba" && panel.totales.ventas === 9600 && panel.totales.compras === 36000, { en_pantalla: vendido, mas_vendido: primero, api: { ventas: panel.totales.ventas, compras: panel.totales.compras } });

  console.log(JSON.stringify({ fase: "completa", errores }));
  fs.writeFileSync(path.join(SALIDA, "estado.json"), JSON.stringify({ tenantId, CORREO, EMPRESA }, null, 1));
  fs.writeFileSync(path.join(SALIDA, "resultados.json"), JSON.stringify(resultados, null, 1));
  await navegador.close();
  process.exit(resultados.every((r) => r.ok) ? 0 : 1);
})().catch((e) => {
  console.error("ERROR:", e.message.split("\n").slice(0, 6).join("\n"));
  fs.writeFileSync(path.join(SALIDA, "resultados.json"), JSON.stringify(resultados, null, 1));
  process.exit(2);
});
