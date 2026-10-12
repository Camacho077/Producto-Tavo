/**
 * Unidades de los insumos — espejo de backend/app/modules/inventario/unidades.py
 * (el backend manda; aquí solo se usa para mostrar y para el costo en vivo de
 * los formularios). Familias: peso (kg, g), volumen (L, ml) y conteo (unidad).
 */
export const UNIDADES = [
  { valor: "kg", etiqueta: "Kilogramos (kg)", familia: "masa", factor: 1000 },
  { valor: "g", etiqueta: "Gramos (g)", familia: "masa", factor: 1 },
  { valor: "L", etiqueta: "Litros (L)", familia: "volumen", factor: 1000 },
  { valor: "ml", etiqueta: "Mililitros (ml)", familia: "volumen", factor: 1 },
  { valor: "unidad", etiqueta: "Unidades", familia: "conteo", factor: 1 },
];
const POR_VALOR = Object.fromEntries(UNIDADES.map((u) => [u.valor, u]));

export const compatibles = (a, b) => Boolean(POR_VALOR[a] && POR_VALOR[b] && POR_VALOR[a].familia === POR_VALOR[b].familia);

/** Las unidades en que se puede escribir una cantidad de un insumo que se lleva en `unidad`. */
export const unidadesDe = (unidad) => UNIDADES.filter((u) => POR_VALOR[unidad] && u.familia === POR_VALOR[unidad].familia);

/** `cantidad` en `de` expresada en `a` (null si no son compatibles). */
export function convertir(cantidad, de, a) {
  if (!compatibles(de, a)) return null;
  return (Number(cantidad) * POR_VALOR[de].factor) / POR_VALOR[a].factor;
}

const numero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 3 });

/** "200 g", "1,5 kg", "3 unidades"; en kg o L por debajo de 1, se dice en g o ml. */
export function legible(cantidad, unidad) {
  const n = Number(cantidad);
  if (!Number.isFinite(n)) return "—";
  if ((unidad === "kg" || unidad === "L") && n !== 0 && Math.abs(n) < 1) {
    return legible(convertir(n, unidad, unidad === "kg" ? "g" : "ml"), unidad === "kg" ? "g" : "ml");
  }
  if (unidad === "unidad") return `${numero.format(n)} ${n === 1 ? "unidad" : "unidades"}`;
  return `${numero.format(n)} ${unidad}`;
}

/** Unidad corta para encabezados: "por kg", "por unidad". */
export const porUnidad = (unidad) => `por ${unidad === "unidad" ? "unidad" : unidad}`;
