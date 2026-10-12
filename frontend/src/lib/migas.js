/**
 * Migas de pan de un módulo: siempre "Módulo › Submódulo › …".
 *
 * Cada pantalla llama `migasDe(BASE, { etiqueta: "Nuevo" })`, donde BASE son
 * las migas fijas del módulo. Antes cada archivo tenía su propia versión de
 * esta línea, con diferencias (Usuarios repetía la misma ruta dos veces).
 */
export function migasDe(base, ...resto) {
  return [...base, ...resto];
}

/** Migas fijas de cada módulo, en un solo sitio. */
export const MIGAS = {
  carta: [{ etiqueta: "Carta", a: "/carta" }],
  platos: [{ etiqueta: "Carta", a: "/carta" }, { etiqueta: "Platos", a: "/carta" }],
  combos: [{ etiqueta: "Carta", a: "/carta" }, { etiqueta: "Combos", a: "/carta/combos" }],
  inventario: [{ etiqueta: "Inventario", a: "/inventario/insumos" }],
  insumos: [{ etiqueta: "Inventario", a: "/inventario/insumos" }, { etiqueta: "Insumos", a: "/inventario/insumos" }],
  compras: [{ etiqueta: "Inventario", a: "/inventario/insumos" }, { etiqueta: "Compras", a: "/inventario/compras" }],
  proveedores: [{ etiqueta: "Inventario", a: "/inventario/insumos" }, { etiqueta: "Proveedores", a: "/inventario/proveedores" }],
  movimientos: [{ etiqueta: "Inventario", a: "/inventario/insumos" }, { etiqueta: "Movimientos", a: "/inventario/movimientos" }],
  conteos: [{ etiqueta: "Inventario", a: "/inventario/insumos" }, { etiqueta: "Conteos", a: "/inventario/conteos" }],
  cargaInicial: [{ etiqueta: "Inventario", a: "/inventario/insumos" }, { etiqueta: "Carga inicial", a: "/inventario/carga-inicial" }],
  ventas: [{ etiqueta: "Ventas", a: "/ventas" }],
  pedidos: [{ etiqueta: "Ventas", a: "/ventas" }, { etiqueta: "Pedidos", a: "/ventas/pedidos" }],
  usuarios: [{ etiqueta: "Seguridad", a: "/seguridad/usuarios" }, { etiqueta: "Usuarios", a: "/seguridad/usuarios" }],
  roles: [{ etiqueta: "Seguridad", a: "/seguridad/usuarios" }, { etiqueta: "Roles", a: "/seguridad/roles" }],
  ajustes: [{ etiqueta: "Ajustes", a: "/ajustes" }, { etiqueta: "Restaurante", a: "/ajustes" }],
  mesas: [{ etiqueta: "Ajustes", a: "/ajustes" }, { etiqueta: "Mesas", a: "/ajustes/mesas" }],
  zonas: [{ etiqueta: "Ajustes", a: "/ajustes" }, { etiqueta: "Mesas", a: "/ajustes/mesas" }, { etiqueta: "Zonas", a: "/ajustes/zonas" }],
};
