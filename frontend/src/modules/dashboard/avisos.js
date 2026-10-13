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
  producto: (id) => `/carta/${id}`,
  productos: () => "/carta",
  insumo: (id) => `/inventario/insumos/${id}`,
  insumos: () => "/inventario/insumos?bajo_minimo=1",
  orden: (id) => `/ordenes/${id}`,
  ordenes: () => "/ordenes",
  venta: (id) => `/caja/ventas/${id}`,
  ventas: () => "/caja/ventas",
  proveedor: (id) => `/inventario/proveedores/${id}`,
  cierres: () => "/caja/cierres",
};

const TEXTOS_ENLACE = {
  producto: "Ver plato",
  productos: "Ver la carta",
  insumo: "Ver insumo",
  insumos: "Ver insumos",
  orden: "Ver orden",
  ordenes: "Ver órdenes",
  venta: "Ver venta",
  ventas: "Ver ventas",
  proveedor: "Ver proveedor",
  cierres: "Ver cierres de caja",
};

/** Devuelve `{a, texto}` o null si el recurso no tiene ruta conocida. */
export function enlaceDeAviso(enlace) {
  if (!enlace?.recurso) return null;
  const construir = RUTAS[enlace.recurso];
  if (!construir) return null;
  return { a: construir(enlace.id), texto: TEXTOS_ENLACE[enlace.recurso] ?? "Ver" };
}
