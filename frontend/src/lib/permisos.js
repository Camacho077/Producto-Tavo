/**
 * Frases de permisos para la interfaz. Espejo de las de
 * backend/app/core/catalogo_permisos.py (el backend manda: estas solo
 * explican por qué una pantalla o un botón no está disponible).
 */
const OBJETO = {
  dashboard: "el dashboard",
  compras: "compras",
  productos: "productos",
  categorias: "categorías",
  proveedores: "proveedores",
  ventas: "ventas",
  pedidos: "pedidos",
  usuarios: "usuarios",
  roles: "roles",
  ia: "las sugerencias de IA",
  ajustes: "los ajustes del restaurante",
  mesas: "mesas y zonas",
};

const VERBO = {
  ver: "ver",
  crear: "crear",
  editar: "editar",
  cambiar_estado: "cambiar el estado de",
  anular: "anular",
  eliminar: "eliminar",
};

/** "cambiar el estado de productos", "ver el dashboard". */
export function fraseDePermiso(modulo, accion = "ver") {
  return `${VERBO[accion] ?? accion} ${OBJETO[modulo] ?? modulo}`;
}
