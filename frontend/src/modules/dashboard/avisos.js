/**
 * Traducción de los avisos que calcula el backend
 * (backend/app/modules/dashboard/avisos.py) a lo que necesita la pantalla: la
 * ruta a la que lleva el enlace.
 *
 * El backend NO conoce las rutas del frontend: devuelve
 * `enlace: {recurso, id}` y el mapa de abajo lo convierte en una URL. Así
 * cambiar una ruta se hace en un solo lado.
 *
 * El nivel del aviso no necesita un icono: en la maqueta lo distingue un punto
 * de color, que es una clase CSS y no un paquete de iconos más en el bundle.
 */
const RUTAS = {
  producto: (id) => `/compras/productos/${id}`,
  productos: () => "/compras/productos",
  pedido: (id) => `/ventas/pedidos/${id}`,
  pedidos: () => "/ventas/pedidos",
  venta: (id) => `/ventas/${id}`,
  ventas: () => "/ventas",
  proveedor: (id) => `/compras/proveedores/${id}`,
};

const TEXTOS_ENLACE = {
  producto: "Ver producto",
  productos: "Ver productos",
  pedido: "Ver pedido",
  pedidos: "Ver pedidos",
  venta: "Ver venta",
  ventas: "Ver ventas",
  proveedor: "Ver proveedor",
};

/** Devuelve `{a, texto}` o null si el recurso no tiene ruta conocida. */
export function enlaceDeAviso(enlace) {
  if (!enlace?.recurso) return null;
  const construir = RUTAS[enlace.recurso];
  if (!construir) return null;
  return { a: construir(enlace.id), texto: TEXTOS_ENLACE[enlace.recurso] ?? "Ver" };
}
