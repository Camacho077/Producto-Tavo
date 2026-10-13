/** Una dona nunca muestra más de 6 partes (fase 8): lo demás va en "Otros". */
export const MAX_PARTES = 6;

/** Ordena de mayor a menor, descarta las vacías y agrupa desde la sexta en "Otros". */
export function agruparPartes(partes, maximo = MAX_PARTES) {
  const ordenadas = [...(partes ?? [])].filter((p) => Number(p.valor) > 0).sort((a, b) => Number(b.valor) - Number(a.valor));
  if (ordenadas.length <= maximo) return ordenadas;
  const resto = ordenadas.slice(maximo - 1).reduce((s, p) => s + Number(p.valor), 0);
  return [...ordenadas.slice(0, maximo - 1), { nombre: "Otros", valor: resto }];
}
