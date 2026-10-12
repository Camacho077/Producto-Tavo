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
  compras: [{ etiqueta: "Compras", a: "/compras" }],
  productos: [{ etiqueta: "Compras", a: "/compras" }, { etiqueta: "Productos", a: "/compras/productos" }],
  proveedores: [{ etiqueta: "Compras", a: "/compras" }, { etiqueta: "Proveedores", a: "/compras/proveedores" }],
  ventas: [{ etiqueta: "Ventas", a: "/ventas" }],
  pedidos: [{ etiqueta: "Ventas", a: "/ventas" }, { etiqueta: "Pedidos", a: "/ventas/pedidos" }],
  usuarios: [{ etiqueta: "Seguridad", a: "/seguridad/usuarios" }, { etiqueta: "Usuarios", a: "/seguridad/usuarios" }],
  roles: [{ etiqueta: "Seguridad", a: "/seguridad/usuarios" }, { etiqueta: "Roles", a: "/seguridad/roles" }],
};
