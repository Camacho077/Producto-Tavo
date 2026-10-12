/**
 * Estados de una orden para la pantalla. El backend manda dos cosas: el
 * estado de NEGOCIO (abierta, cobrada, anulada) y, si está abierta, el de
 * COCINA (el de su comanda más atrasada). Aquí se juntan en uno solo.
 */
export const ESTADOS = {
  entrante: { etiqueta: "Entrante", variante: "advertencia" },
  en_preparacion: { etiqueta: "En preparación", variante: "acento" },
  lista: { etiqueta: "Lista", variante: "positivo" },
  entregada: { etiqueta: "Entregada", variante: "neutro" },
  anulada: { etiqueta: "Anulada", variante: "negativo" },
  cobrada: { etiqueta: "Cobrada", variante: "neutro" },
};

export function estadoDeOrden(o) {
  if (o.estado === "abierta") return o.estado_cocina ?? "entregada";
  return o.estado;
}

/** "Mesa B2", "Ana (llevar)", "Domicilio · Calle 5". */
export function destinoDeOrden(o) {
  if (o.tipo === "local") return o.mesa_nombre ? `Mesa ${o.mesa_nombre}` : "En el local";
  const cliente = o.cliente_nombre || (o.tipo === "domicilio" ? "Domicilio" : "Para llevar");
  return o.tipo === "domicilio" && o.cliente_direccion ? `${cliente} · ${o.cliente_direccion}` : cliente;
}

/** "Jornada del lunes 12/10" a partir de "2026-10-12". */
export function nombreJornada(fechaIso) {
  if (!fechaIso) return "Jornada";
  const [a, m, d] = fechaIso.split("-").map(Number);
  const dia = new Date(Date.UTC(a, m - 1, d)).toLocaleDateString("es-CO", { weekday: "long", timeZone: "UTC" });
  return `Jornada del ${dia} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}

export const ETIQUETA_MESA = { libre: "Libre", ocupada: "Ocupada", por_cobrar: "Por cobrar" };
