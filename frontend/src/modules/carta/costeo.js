import { convertir } from "@/lib/unidades";

/**
 * Costo EN VIVO mientras se arma una receta (solo para mostrar; el backend
 * recalcula y manda: backend/app/modules/catalogo/recetas.py). Mismas reglas:
 * cantidad × (1 + merma) convertida a la unidad del insumo × su costo, y el
 * margen sobre el precio SIN el impuesto al consumo si la carta lo incluye.
 */
export function costoDeLinea(linea, insumo) {
  if (!insumo || insumo.costo_unitario == null || linea.cantidad === "" || !linea.unidad) return null;
  const bruto = Number(linea.cantidad) * (1 + Number(linea.merma_porcentaje || 0) / 100);
  const enUnidadDelInsumo = convertir(bruto, linea.unidad, insumo.unidad);
  if (enUnidadDelInsumo == null || !Number.isFinite(enUnidadDelInsumo)) return null;
  return enUnidadDelInsumo * Number(insumo.costo_unitario);
}

export function costoDeReceta(lineas, insumosPorId) {
  if (!lineas.length) return null;
  let total = 0;
  for (const l of lineas) {
    const c = costoDeLinea(l, insumosPorId[l.insumo_id]);
    if (c == null) return null;
    total += c;
  }
  return total;
}

export function precioNeto(precio, configuracion) {
  const p = Number(precio);
  if (!Number.isFinite(p)) return null;
  const imp = configuracion?.impuesto_consumo;
  if (imp?.aplica && imp?.incluido_en_precio) return p / (1 + Number(imp.tasa) / 100);
  return p;
}

/** {costo, neto, margen, porcentaje} o nulls si falta algo. */
export function costeo(costo, precio, configuracion) {
  const neto = precioNeto(precio, configuracion);
  if (costo == null || neto == null || neto <= 0) return { costo, neto, margen: null, porcentaje: null };
  return { costo, neto, margen: neto - costo, porcentaje: (costo / neto) * 100 };
}
