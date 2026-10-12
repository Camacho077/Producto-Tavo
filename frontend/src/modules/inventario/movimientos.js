/**
 * Tipos de movimiento de inventario y el enlace a su documento: los comparten
 * el historial de cada insumo y el historial general.
 */
export const TIPOS_MOVIMIENTO = {
  inicial: { etiqueta: "Existencia inicial", variante: "neutro" },
  compra: { etiqueta: "Compra", variante: "positivo" },
  anulacion_compra: { etiqueta: "Anulación de compra", variante: "neutro" },
  venta: { etiqueta: "Venta", variante: "neutro" },
  anulacion_venta: { etiqueta: "Anulación de venta", variante: "neutro" },
  merma: { etiqueta: "Merma", variante: "negativo" },
  ajuste: { etiqueta: "Ajuste", variante: "neutro" },
};

export function enlaceDeDocumento(m) {
  if (m.documento_tipo === "compra") return `/inventario/compras/${m.documento_id}`;
  if (m.documento_tipo === "venta") return `/ventas/${m.documento_id}`;
  if (m.documento_tipo === "conteo") return `/inventario/conteos/${m.documento_id}`;
  return null;
}
