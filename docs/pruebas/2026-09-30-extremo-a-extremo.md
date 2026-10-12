# Prueba de extremo a extremo — 2026-09-30

**Resultado: 58 de 58 comprobaciones correctas, 0 fallas.**

## Cómo se hizo

- La aplicación usada **como una persona**: clics y teclado reales en la
  interfaz (Playwright + Chromium), con el frontend en `http://localhost:5173`
  y el backend en el `8001`.
- Una **empresa de prueba propia**, registrada por la pantalla real de
  registro (así también queda probado el registro), para no llenar la empresa
  de demostración con datos de prueba ni mover su stock.
- Cada resultado se confirma **directamente en Postgres** (consulta SQL a la
  base de desarrollo, no la respuesta de la API) y, donde aplica, **después de
  recargar la página**.
- Los PDF se descargan con el botón de la interfaz y se **lee su texto**
  (código, cliente/proveedor, productos, totales) con un extractor sin
  librerías externas.
- Script reproducible: `automatizaciones/pruebas/extremo-a-extremo/e2e.cjs`
  (ver el encabezado del archivo para las variables `PLAYWRIGHT_MODULE`,
  `PYTHON_BACKEND` y `SALIDA_E2E`). Cada corrida crea su propia empresa.

## Resultados

| # | Prueba | Resultado | Evidencia (base de datos / pantalla / PDF) |
|---|---|---|---|
| 1 | Registro por la pantalla real crea la empresa y su administrador | ✅ | `{"url":"http://localhost:5173/"}` |
| 2 | categorias: crear | ✅ | `{"alerta":"Categoría creada","bd":{"nombre":"Bebidas Prueba","activo":true,"descripcion":"Creada en la prueba de extremo a extremo"}}` |
| 3 | categorias: sigue tras recargar | ✅ | `visible en el listado` |
| 4 | categorias: ver detalle | ✅ | `título del detalle` |
| 5 | categorias: editar | ✅ | `{"bd":{"nombre":"Bebidas Frías"}}` |
| 6 | categorias: edición sigue tras recargar | ✅ | `visible` |
| 7 | categorias: cambiar estado (desactivar y activar) | ✅ | `{"tras_desactivar":{"activo":false},"tras_activar":{"activo":true}}` |
| 8 | categorias: eliminar | ✅ | `{"filas_en_bd":0}` |
| 9 | marcas: crear | ✅ | `{"alerta":"Marca creada","bd":{"nombre":"Marca Propia","activo":true,"descripcion":"Creada en la prueba de extremo a extremo"}}` |
| 10 | marcas: sigue tras recargar | ✅ | `visible en el listado` |
| 11 | marcas: ver detalle | ✅ | `título del detalle` |
| 12 | marcas: editar | ✅ | `{"bd":{"nombre":"Marca Propia Premium"}}` |
| 13 | marcas: edición sigue tras recargar | ✅ | `visible` |
| 14 | marcas: cambiar estado (desactivar y activar) | ✅ | `{"tras_desactivar":{"activo":false},"tras_activar":{"activo":true}}` |
| 15 | marcas: eliminar | ✅ | `{"filas_en_bd":0}` |
| 16 | proveedores: crear (jurídica, NIT con DV) | ✅ | `{"alerta":"Proveedor creado","bd":{"razon_social":"Distribuidora Prueba","nit":"890903938-8","telefono":"3001234567","activo":true}}` |
| 17 | proveedores: sigue tras recargar | ✅ | `visible` |
| 18 | proveedores: ver detalle | ✅ | `título` |
| 19 | proveedores: editar | ✅ | `razón social nueva en BD` |
| 20 | proveedores: edición sigue tras recargar | ✅ | `visible` |
| 21 | proveedores: cambiar estado | ✅ | `false -> true` |
| 22 | proveedores: eliminar | ✅ | `0 filas` |
| 23 | productos: crear (con categoría y marca; stock nace en 0) | ✅ | `{"bd":{"nombre":"Gaseosa Prueba","sku":"GAS-E2E","precio":3000,"precio_compra":1800,"stock":0,"stock_minimo":5,}}` |
| 24 | productos: sigue tras recargar | ✅ | `visible` |
| 25 | productos: ver detalle | ✅ | `título` |
| 26 | productos: editar precio | ✅ | `3000 -> 3200` |
| 27 | productos: edición sigue tras recargar | ✅ | `precio nuevo visible` |
| 28 | productos: cambiar estado | ✅ | `false -> true` |
| 29 | productos: eliminar (sin movimientos; la interfaz no tiene botón) | ✅ | `{"http":204}` |
| 30 | compras: registrar pendiente (no mueve stock) | ✅ | `{"compra":{"numero":1,"estado":"pendiente","total":36000},"stock":0}` |
| 31 | compras: confirmar sube el stock EXACTAMENTE lo comprado | ✅ | `{"antes":0,"despues":20,"estado":"confirmada"}` |
| 32 | compras: PDF abre y trae los datos correctos | ✅ | `ORDEN DE COMPRA` |
| 33 | compras: anular devuelve el stock a su valor previo | ✅ | `{"antes":0,"tras_anular":0,"estado":"anulada"}` |
| 34 | compras: cada movimiento queda registrado (entrada y reversa) | ✅ | `[{"tipo":"compra","cantidad":20,"stock_resultante":20},{"tipo":"anulacion_compra","cantidad":-20,"stock_resultante":0}]` |
| 35 | compras: registrar confirmada de inmediato | ✅ | `{"compra2":{"numero":2,"estado":"confirmada","total":36000},"stock":20}` |
| 36 | ventas: completar baja el stock | ✅ | `{"venta":{"estado":"completada","total":9600},"antes":20,"despues":17}` |
| 37 | ventas: vender más de lo que hay se bloquea en pantalla con mensaje claro (y no guarda nada) | ✅ | `{"mensaje":"Stock insuficiente para \"Gaseosa Prueba\": disponible 17, solicitado 1000.","ventas_en_bd":1,"stock":17}` |
| 38 | ventas: el backend rechaza la sobreventa por sí solo (409 con la causa) | ✅ | `{"status":409,"detail":"No se pudo registrar la venta: el producto Gaseosa Prueba solo tiene 17 unidades y se pidieron 1000."}` |
| 39 | ventas: PDF abre y trae los datos correctos | ✅ | `VEN-000001` |
| 40 | pedidos: crear agregando y quitando líneas | ✅ | `{"lineasAntes":2,"lineasDespues":1,"items_en_bd":[{"cantidad":4}]}` |
| 41 | pedidos: editar agrega una línea y cambia prioridad | ✅ | `{"items_en_bd":[{"cantidad":4},{"cantidad":1}]}` |
| 42 | pedidos: cambiar estado a en_proceso | ✅ | `{"estado":"en_proceso"}` |
| 43 | pedidos: cambiar estado a listo | ✅ | `{"estado":"listo"}` |
| 44 | pedidos: cambiar estado a entregado | ✅ | `{"estado":"entregado"}` |
| 45 | pedidos: seguimiento (línea de tiempo) en BD y en pantalla | ✅ | `{"eventos":["pendiente: Pedido registrado","pendiente: Pedido editado","en_proceso: paso a en_proceso","listo: paso a listo","entregado: paso a entregado"],"en_pantalla":5}` |
| 46 | pedidos: PDF abre y trae los datos correctos | ✅ | `PED-000001` |
| 47 | usuarios: crear con rol Cajero | ✅ | `{"bd":{"nombre_completo":"Pedro Pruebas","activo":true}}` |
| 48 | usuarios: sigue tras recargar | ✅ | `visible` |
| 49 | usuarios: ver detalle | ✅ | `título` |
| 50 | usuarios: editar | ✅ | `nombre nuevo en BD` |
| 51 | usuarios: cambiar estado | ✅ | `desactivado` |
| 52 | usuarios: eliminar | ✅ | `0 filas` |
| 53 | roles: crear con permisos desde la matriz | ✅ | `{"bd":{"permisos":"{\"ventas\": [\"ver\"], \"compras\": [\"ver\"]}"}}` |
| 54 | roles: sigue tras recargar | ✅ | `visible` |
| 55 | roles: ver detalle | ✅ | `título` |
| 56 | roles: editar permisos | ✅ | `pedidos:ver agregado` |
| 57 | roles: eliminar | ✅ | `0 filas` |
| 58 | dashboard: refleja la venta y la compra nuevas | ✅ | `{"en_pantalla":"$ 9.600","mas_vendido":"Gaseosa Prueba","api":{"ventas":9600,"compras":36000}}` |

## Hallazgos durante la prueba (y qué se hizo)

1. **Sobreventa: el mensaje citaba una venta que nunca existió.** Al registrar
   y completar una venta sin stock, el backend respondía *"No se pudo completar
   la venta VEN-000002: …"*, pero esa venta se revierte y el número nunca
   existe. Corregido: ahora dice *"No se pudo registrar la venta: el producto X
   solo tiene N unidades y se pidieron M."*; además la venta rechazada se
   deshace explícitamente (`db.rollback()`), sin depender de cómo se cierre la
   sesión. Lo protege `tests/test_ventas.py`.
2. **La interfaz ya bloqueaba la sobreventa antes de enviar** y mostraba la
   causa en el formulario ("Stock insuficiente para … disponible 17,
   solicitado 1000"). Pendiente para la fase de accesibilidad: ese texto no
   se anuncia a lectores de pantalla (no es `role="alert"`).
3. **Botón de PDF**: el texto visible dice "Ver PDF" / "Factura PDF", pero su
   nombre accesible es "Descargar PDF" (WCAG 2.5.3, la etiqueta visible debe
   estar en el nombre). Pendiente para la fase de accesibilidad.
4. **Productos no tiene botón Eliminar en la interfaz** (sí en el backend,
   con permiso `productos.eliminar`). Se probó por la API con la sesión real.
   Es coherente con la regla de conservar el historial (un producto con
   movimientos no se elimina); queda anotado por si se quiere el botón.
5. **Pedidos**: editar un pedido también deja un evento en la línea de
   tiempo ("Pedido editado"), además del registro y cada cambio de estado.
   Comportamiento correcto.
