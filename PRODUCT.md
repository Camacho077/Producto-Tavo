# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Equipo administrativo de PyMEs en Colombia (administradores y auxiliares)
que registran compras, ventas, pedidos e inventario a diario, en escritorio.
El cliente final del negocio nunca ve este sistema.

## Product Purpose

ERP multi-tenant de gestión interna: un solo backend y una sola base de datos
sirven a todas las empresas, cada una aislada por `tenant_id`. Éxito = que el
equipo registre y consulte su operación diaria rápido y sin errores, y que el
dashboard muestre la verdad del negocio con datos reales.

## Positioning

- **Marca propia por empresa**: cada cliente ve su color, logo y tipografía
  (`Tenant.theme_config` aplicado con variables CSS).
- **Planes modulares**: Básico / Estándar / Pro+IA; los módulos se activan
  por plan sin tocar los demás.
- **Rápido y sobrio**: primera carga por debajo de 0,5 s (medido con
  Lighthouse sobre la versión compilada) y movimiento cuidado, que forma
  parte del producto y no es decoración.

## Operating Context

Uso de oficina, sesiones largas, mucha información por pantalla. Flujos:
registrar compra (proveedor primero), registrar venta, pedidos con estados,
catálogo (categorías, marcas, productos, proveedores), usuarios y roles, y un
dashboard con cifras, gráfica, más vendidos, inventario y avisos.

## Capabilities and Constraints

- Una pantalla con ruta propia por acción (listado, nuevo, detalle, editar);
  sin modales salvo la confirmación de acciones.
- Stock = suma de movimientos; nunca se escribe a mano.
- Mensajes de error siempre con la causa concreta, en español.
- Decisiones visuales ya aprobadas y NO negociables en trabajo de pulido:
  paleta Espresso/Marfil (oscuro) y Blanco/Crema (claro), tipografías
  Playfair Display (títulos), Inter (interfaz) y JetBrains Mono (cifras), y
  el layout de la maqueta `docs/dashboard-referencia.html`. Ver
  `docs/DECISIONES.md`.

## Brand Commitments

Nombre: JS Company. Voz en español de Colombia, directa y concreta. Las
entidades de negocio se nombran en español (Usuario, Rol, Compra, Venta).

## Evidence on Hand

Datos de demostración reales cargables con
`automatizaciones/deploy/seed_demo.py`. No hay testimonios, casos de clientes
ni cifras comerciales: no inventarlos.

## Product Principles

1. Densidad sin ruido: mucha información por pantalla, cero aire muerto.
2. La verdad antes que el adorno: toda cifra y todo aviso salen de datos
   reales del tenant.
3. Rendimiento medido, no estimado: nada entra si empeora las métricas.
4. El movimiento orienta, nunca distrae: corre una vez y se queda quieto.

## Accessibility & Inclusion

WCAG 2.2 AA obligatorio: contraste AA medido en la app viva en ambos
esquemas, `prefers-reduced-motion` respetado en todo, y el foco visible.
