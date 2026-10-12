import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * CSS POR RUTA (2026-10-02): los estilos del dashboard, la gráfica, la IA y
 * el legal se descargan con su pantalla, no en el login. Eso solo es seguro
 * si esos archivos NO redefinen clases de otros: si lo hicieran, una misma
 * pantalla se vería distinta según qué ruta se visitó antes (pasó con
 * `.miniatura`, que el dashboard también definía y teñía las miniaturas de
 * la tabla de Productos; ahora es `.dash-miniatura`).
 *
 * Regla: en un CSS de ruta, cada selector EMPIEZA por una clase propia de
 * ese archivo (se permite ajustar una clase compartida debajo de ella, como
 * `.ia .encabezado-pagina`).
 */
const SRC = path.dirname(fileURLToPath(import.meta.url));
const POR_RUTA = [
  "modules/dashboard/dashboard.css",
  "components/charts/charts.css",
  "modules/ia/ia.css",
  "modules/legal/legal.css",
];

function archivosCss(dir) {
  return readdirSync(dir).flatMap((n) => {
    const c = path.join(dir, n);
    return statSync(c).isDirectory() ? archivosCss(c) : n.endsWith(".css") ? [c] : [];
  });
}

/** Selectores de reglas (sin @media/@keyframes/@layer ni pasos de keyframes). */
function selectores(archivo) {
  const texto = readFileSync(archivo, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const res = [];
  for (const m of texto.matchAll(/([^{};]+)\{/g)) {
    const cabeza = m[1].trim();
    if (!cabeza || cabeza.startsWith("@") || /^(from|to|\d+%)/.test(cabeza)) continue;
    res.push(...cabeza.split(",").map((s) => s.trim()).filter(Boolean));
  }
  return res;
}

const primeraClase = (sel) => /\.([a-zA-Z][\w-]*)/.exec(sel)?.[1] ?? null;

describe("CSS por ruta: sin colisiones de clases", () => {
  const todos = archivosCss(SRC);
  const clasesDe = (archivo) => new Set(selectores(archivo).map(primeraClase).filter(Boolean));

  for (const relativo of POR_RUTA) {
    it(`${relativo} solo define selectores que empiezan por una clase propia`, () => {
      const archivo = path.join(SRC, relativo);
      const ajenas = new Set(todos.filter((f) => f !== archivo).flatMap((f) => [...clasesDe(f)]));
      const invasores = selectores(archivo).filter((sel) => {
        const c = primeraClase(sel);
        return c && ajenas.has(c);
      });
      expect(invasores).toEqual([]);
    });
  }

  it("el login no descarga los estilos de las rutas (no están en index.css)", () => {
    const base = readFileSync(path.join(SRC, "index.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    for (const relativo of [...POR_RUTA, "components/ui/listados.css", "components/ui/pantallas.css", "components/ui/movimiento.css"]) {
      expect(base).not.toContain(path.basename(relativo));
    }
  });
});
