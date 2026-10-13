/**
 * Espejo de `desglose` de backend/app/modules/caja/services.py, solo para
 * mostrar en vivo cuánto es la cuenta mientras se cobra (el backend vuelve
 * a calcular y es quien manda).
 */
const centavos = (v) => Math.round(Number(v) * 100) / 100;

export function desglose(totalPlatos, configuracion) {
  const imp = configuracion?.impuesto_consumo ?? { aplica: true, tasa: "8", incluido_en_precio: true };
  const total = centavos(totalPlatos);
  if (!imp.aplica) return { subtotal: total, impuesto: 0, total, tasa: 0 };
  const tasa = Number(imp.tasa);
  if (imp.incluido_en_precio) {
    const base = centavos(total / (1 + tasa / 100));
    return { subtotal: base, impuesto: centavos(total - base), total, tasa };
  }
  const impuesto = centavos((total * tasa) / 100);
  return { subtotal: total, impuesto, total: centavos(total + impuesto), tasa };
}

/** Monto escrito con el filtro "decimal" ("12500" o "12500.5"); vacío = 0. */
export function aNumero(texto) {
  const n = Number(String(texto ?? "").trim() || 0);
  return Number.isFinite(n) ? n : 0;
}
