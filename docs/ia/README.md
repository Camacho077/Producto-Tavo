# Módulo de Sugerencias IA

Add-on de pago: incluido en el plan **Pro + IA** o contratado aparte
(`Tenant.modulos_activos` con `"ia"`). El plan se exige en el **backend**
(`app/core/permisos.py` → 403 «El plan … no incluye las Sugerencias IA»), no
solo en el menú. Dentro de la empresa, cada rol necesita además el permiso
`ia.ver`.

- Backend: `backend/app/modules/ia/analisis.py` (reglas) y `router.py`
  (`GET /api/v1/ia/sugerencias`, `GET /api/v1/ia/status`).
- Frontend: `frontend/src/modules/ia/IaPage.jsx`.
- Pruebas: `backend/tests/test_ia.py`, `backend/tests/test_planes.py`,
  `frontend/src/modules/ia/IaPage.test.jsx`.

## Qué sale del sistema: NADA

| Pregunta | Respuesta |
|---|---|
| ¿Se llama a un modelo o API externa (OpenAI, Anthropic, Google…)? | **No.** Todo se calcula dentro del backend con consultas SQL y aritmética. |
| ¿Se envían datos del negocio a terceros? | **No.** Ninguna petición sale del servidor para este módulo. |
| ¿Se usan datos personales de clientes? | **No.** Solo cantidades, montos, fechas, productos y proveedores (empresas). `cliente_nombre` y `cliente_documento` no se leen. |
| ¿Se guardan los resultados? | **No.** Se calculan en cada consulta; no hay tabla ni caché. |
| ¿Quién ve costos y márgenes? | Solo quien tiene `compras.ver` (la misma regla que el costo del producto). A los demás, las secciones de precios y proveedores les dicen por qué no las ven. |

Por eso la pantalla dice: *«Calculado dentro del sistema con estadística sobre
tus ventas, compras y stock. No se envía ningún dato a servicios externos ni se
usan datos personales de tus clientes.»*

**Si algún día se conecta un modelo externo**, antes de hacerlo:

1. Actualizar esta tabla, la Política de Tratamiento de Datos
   (`frontend/src/modules/legal/textos/politica-datos.md`, transmisión a un
   Encargado y posible transferencia internacional) y el contrato
   (`docs/legal/`).
2. Enviar solo agregados (totales por producto/día), nunca filas con
   clientes, documentos, teléfonos ni direcciones.
3. Mostrarlo en la pantalla y pedir la activación explícita al administrador
   de la empresa.

## Reglas (umbrales en `analisis.py`, con nombre)

Toda sugerencia trae `por_que` (la explicación con las cifras) y `datos` (las
cifras usadas). Si una regla no tiene base, la sección lo dice en `sin_datos`;
nunca se inventa un número.

| Sección | Regla | Base mínima |
|---|---|---|
| Base global | — | 5 ventas completadas en 3 días distintos (últimos 90). Sin base, solo se muestran precios y proveedores (no dependen de la historia de ventas). |
| Alertas: quiebre previsible | stock ÷ ritmo de 30 días < 7 días | 3 unidades vendidas en 2 días distintos (30 d) |
| Alertas: caída de venta | ventas totales −20 % frente a los 30 días anteriores; por producto −40 % | tramo anterior con ventas; producto con ≥ 5 unidades antes |
| Reponer | cobertura < 21 días o stock ≤ mínimo; cantidad = ritmo × 30 + mínimo − stock | mismo ritmo; sin ritmo solo cuenta el mínimo configurado |
| Ganadores | top 5 por monto con crecimiento ≥ 20 % (o nuevos con ventas) | ≥ 5 unidades en 30 d |
| Patrones | día de la semana con ≥ 30 % más que un reparto parejo; franja de 3 h con ≥ 40 % de las ventas (hora de Colombia) | 10 ventas en 4 semanas distintas (de las últimas 8) |
| Baja rotación | vendió menos de ¼ de su stock en 60 días | producto con más de 30 días de creado |
| Precios | margen < 15 % (o negativo); precio sugerido para 25 % | costo conocido: compras de 180 d o costo registrado |
| Proveedores | el último proveedor cuesta ≥ 5 % más que otro del mismo producto | producto comprado a 2+ proveedores en 180 d |

El motor es "IA" en el sentido comercial del catálogo (sugerencias
automáticas); técnicamente son reglas estadísticas explicables, a propósito:
cada cifra se puede comprobar contra los listados.
