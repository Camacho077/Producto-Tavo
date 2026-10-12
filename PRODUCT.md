# Product

<!-- impeccable:product-schema 1 -->

## Platform

web (escritorio, tablet y celular según el rol)

## Users

Equipo de restaurantes en Colombia; primer cliente "Donde Tavo", un
restaurante dentro de una universidad con 12 años de operación y sin ningún
sistema. Cuatro roles con dispositivo propio: administrador (escritorio),
cajero (escritorio), mesero (celular) y cocinero (tablet, leída a un metro).
El comensal nunca ve este sistema.

## Product Purpose

Sistema de gestión multi-tenant para restaurantes, derivado del ERP "Producto
JS": un solo backend y una sola base sirven a todos los restaurantes, cada uno
aislado por `tenant_id`. Éxito = tomar un pedido más rápido que en papel, que
la cocina vea cada orden al instante, cobrar y cuadrar caja sin errores, y que
el dueño sepa por fin cuánto le cuesta cada plato y cuánto gana.

## Positioning

- **Costo y margen por plato** a partir de recetas e insumos reales: la
  necesidad de fondo del primer cliente.
- **Hecho para el ritmo del servicio**: pantallas táctiles rápidas para el
  mesero, tablero de cocina legible a distancia, caja con cuadre diario.
- **Rápido y sobrio**, heredado del Producto JS: primera carga por debajo de
  0,5 s medida sobre la versión compilada y movimiento cuidado.

## Operating Context

Servicio de almuerzo universitario con picos fuertes entre semana y caídas en
fines de semana y vacaciones. Flujos: tomar orden (local con mesa, para
llevar, domicilio), comanda a cocina, cocina toma y finaliza, caja cobra y
cierra el día, compras de insumos, inventario con mermas y conteos.

## Capabilities and Constraints

- Una pantalla con ruta propia por acción; sin modales salvo la confirmación
  de acciones.
- Existencias = suma de movimientos; nunca se escriben a mano.
- Mensajes de error siempre con la causa concreta, en español.
- Decisiones visuales heredadas y NO negociables en trabajo de pulido: paleta
  monocromática estricta (blanco, negro y grises; `docs/DECISIONES.md` §2),
  tipografías Playfair Display (títulos), Inter (interfaz) y JetBrains Mono
  (cifras), y las reglas de movimiento de `docs/DECISIONES.md` §5.
- La factura es un comprobante INTERNO, no facturación electrónica DIAN.

## Brand Commitments

Nombre provisional: "JS Restaurante" (vive en un archivo de branding, con
logo provisional). Voz en español de Colombia, directa y concreta. Las
entidades de negocio se nombran en español (Orden, Plato, Insumo, Receta,
Caja).

## Evidence on Hand

Datos de demostración de restaurante cargables con el seed (fase 11). No hay
testimonios, casos de clientes ni cifras comerciales: no inventarlos.

## Product Principles

1. Más rápido que el papel: si un flujo es más lento que hoy, está mal.
2. La verdad antes que el adorno: toda cifra sale de datos reales del tenant.
3. Rendimiento medido, no estimado: nada entra si empeora las métricas.
4. El movimiento orienta, nunca distrae: corre una vez y se queda quieto.

## Accessibility & Inclusion

WCAG 2.2 AA obligatorio: contraste AA medido en la app viva en ambos
esquemas, `prefers-reduced-motion` respetado en todo, foco visible, y
objetivos táctiles amplios en las vistas de mesero y cocina.
