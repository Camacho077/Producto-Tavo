import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * PROTECCIÓN AUTOMATIZADA de la paleta MONOCROMÁTICA (decisión del
 * 2026-10-01, sustituye a la Espresso/Marfil del 2026-09-28).
 *
 * Cero color: solo blanco, negro y grises. Once tokens en claro (el principal)
 * y siete en oscuro. La jerarquía se hace con valor y peso tipográfico. Los
 * colores "de prueba" (verde, azul, oro, rojo…) y los restos de la paleta
 * cálida anterior se cuelan solos en cualquier ajuste rápido; este test lee el
 * código y falla si pasa.
 *
 * Si alguna vez hay un caso legítimo, la excepción se documenta AQUÍ con su
 * porqué, no se borra el test.
 */

const SRC = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.join(SRC, "..");

const CLARO = {
  "claro-fondo": "#EDEDF0",
  "claro-superficie": "#FFFFFF",
  "claro-relleno": "#F7F7F9",
  "claro-sutil": "#F1F1F4",
  "claro-borde": "#E4E4E9",
  "claro-divisor": "#F0F0F3",
  "claro-eje": "#D4D4DA",
  "claro-secundario": "#6B6B76",
  "claro-terciario": "#52525B",
  "claro-nav": "#3F3F46",
  "claro-texto": "#18181B",
};
const OSCURO = {
  "oscuro-fondo": "#0A0A0B",
  "oscuro-superficie": "#141416",
  "oscuro-relleno": "#1C1C1F",
  "oscuro-sutil": "#232327",
  "oscuro-borde": "#2A2A2F",
  "oscuro-secundario": "#8A8A94",
  "oscuro-texto": "#F4F4F5",
};
const PALETA = { ...OSCURO, ...CLARO };
const HEX_PERMITIDOS = new Set(Object.values(PALETA).map((h) => h.toUpperCase()));

function archivos(dir, extensiones) {
  return readdirSync(dir).flatMap((nombre) => {
    const completo = path.join(dir, nombre);
    if (statSync(completo).isDirectory()) return archivos(completo, extensiones);
    return extensiones.some((e) => nombre.endsWith(e)) ? [completo] : [];
  });
}

const esTest = (f) => /\.test\.[jt]sx?$/.test(f);
// tokens.js mezcla el color del TENANT con blanco/negro para derivar su hover
// y su activo: esos dos literales son aritmética, no un color del producto.
const esLogicaDeTenant = (f) => f.endsWith(path.join("theme", "tokens.js"));

const codigo = archivos(SRC, [".css", ".jsx", ".js"]).filter((f) => !esTest(f) && !esLogicaDeTenant(f));
const indexCss = readFileSync(path.join(SRC, "index.css"), "utf8");

/** Líneas de un archivo sin comentarios de bloque ni de línea. */
function lineasDeCodigo(archivo) {
  const texto = readFileSync(archivo, "utf8").replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  return texto.split("\n").map((l) => (archivo.endsWith(".css") ? l : l.replace(/\/\/.*$/, "")));
}

function hallazgos(regex, { excepto = () => false } = {}) {
  const res = [];
  for (const archivo of codigo) {
    lineasDeCodigo(archivo).forEach((linea, i) => {
      for (const m of linea.matchAll(regex)) {
        if (!excepto(archivo, m[0])) res.push(`${path.relative(SRC, archivo)}:${i + 1}  ${m[0]}`);
      }
    });
  }
  return res;
}

/** Cuerpo del bloque CSS que empieza con `selector {`. */
function bloque(selector) {
  const inicio = indexCss.indexOf(`${selector} {`);
  expect(inicio, `no encontré el bloque ${selector}`).toBeGreaterThan(-1);
  const fin = indexCss.indexOf("\n}", inicio);
  return indexCss.slice(inicio, fin).replace(/\/\*[\s\S]*?\*\//g, "");
}

describe("paleta del producto: monocromática estricta (11 tokens en claro, 7 en oscuro)", () => {
  it("index.css define exactamente los dieciocho tokens con sus valores", () => {
    for (const [nombre, hex] of Object.entries(PALETA)) {
      expect(indexCss, `--${nombre}`).toMatch(new RegExp(`--${nombre}:\\s*${hex};`, "i"));
    }
  });

  it("ningún hex fuera de los dieciocho tokens en CSS, JSX ni JS", () => {
    const fuera = hallazgos(/#[0-9a-fA-F]{3,8}\b/g, {
      excepto: (_, hex) => HEX_PERMITIDOS.has(hex.toUpperCase()),
    });
    expect(fuera).toEqual([]);
  });

  it("los hex de la paleta solo se escriben en index.css", () => {
    const fuera = hallazgos(/#[0-9a-fA-F]{6}\b/g, { excepto: (archivo) => archivo.endsWith("index.css") });
    expect(fuera).toEqual([]);
  });

  it("nada de rgb()/hsl()/oklch() ni colores con nombre (white, black, red…)", () => {
    const funciones = hallazgos(/\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\(/g);
    const nombres = hallazgos(
      /(?<![-\w])(?:white|black|red|green|blue|gold|goldenrod|navy|teal|maroon|orange|yellow|purple|gray|grey|silver)(?![-\w])/g
    );
    expect([...funciones, ...nombres]).toEqual([]);
  });

  it("ni clases de color de Tailwind (bg-red-500, text-emerald-600…)", () => {
    const fuera = hallazgos(
      /\b(?:bg|text|border|ring|fill|stroke|from|via|to|shadow|outline|divide|decoration|accent)-(?:red|green|blue|emerald|amber|yellow|gray|slate|zinc|neutral|stone|white|black|teal|sky|indigo|rose|orange|lime|cyan|violet|purple|fuchsia|pink)(?:-\d{2,3})?\b/g
    );
    expect(fuera).toEqual([]);
  });

  it("no queda ningún nombre de las paletas viejas (verde bosque y Espresso/Marfil)", () => {
    const fuera = hallazgos(
      // Solo variables (`var(--x)` o `--x:`), no modificadores BEM como `.badge--positivo`.
      /(?:var\(|^\s*)--(?:verde[\w-]*|pizarra[\w-]*|onix[\w-]*|noche|humo|piedra|positivo|negativo|advertencia|espresso|carbon|sombra|ceniza|lino|marfil|blanco|crema(?:-hondo)?|arena|tierra|marron)(?=[):])/gm
    );
    expect(fuera).toEqual([]);
  });

  it("los componentes usan ROLES: los tokens de paleta solo se leen en index.css", () => {
    const nombres = Object.keys(PALETA).join("|");
    const fuera = hallazgos(new RegExp(`var\\(--(?:${nombres})\\)`, "g"), {
      excepto: (archivo) => archivo.endsWith("index.css"),
    });
    expect(fuera).toEqual([]);
  });

  it("el modo oscuro solo usa los tokens del oscuro, y el claro solo los del claro", () => {
    const usados = (css) => [...css.matchAll(/var\(--([\w-]+)\)/g)].map((m) => m[1]).filter((n) => n in PALETA);
    const claro = usados(bloque(':root,\n:root[data-theme="claro"]'));
    const oscuro = usados(bloque(':root[data-theme="oscuro"],\n.esquema-oscuro'));

    expect(oscuro.length).toBeGreaterThan(0);
    expect(claro.length).toBeGreaterThan(0);
    expect(oscuro.filter((n) => !(n in OSCURO))).toEqual([]);
    expect(claro.filter((n) => !(n in CLARO))).toEqual([]);
  });

  it("el botón primario es el texto principal: grafito con blanco / casi blanco con casi negro", () => {
    const claro = bloque(':root,\n:root[data-theme="claro"]');
    const oscuro = bloque(':root[data-theme="oscuro"],\n.esquema-oscuro');
    expect(claro).toMatch(/--boton-base:\s*var\(--claro-texto\);/);
    expect(claro).toMatch(/--texto-sobre-acento:\s*var\(--claro-superficie\);/);
    expect(oscuro).toMatch(/--boton-base:\s*var\(--oscuro-texto\);/);
    expect(oscuro).toMatch(/--texto-sobre-acento:\s*var\(--oscuro-fondo\);/);
  });

  it("el claro es el modo por defecto: `:root` sin atributo pinta en claro", () => {
    expect(indexCss).toContain(':root,\n:root[data-theme="claro"] {');
  });

  it("cero tinte: cada hex de la paleta es un gris (R, G y B a menos de 12 puntos entre sí)", () => {
    // #6B6B76 es el más alejado (11): es el gris secundario aprobado.
    const conTinte = Object.entries(PALETA).filter(([, hex]) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      return Math.max(r, g, b) - Math.min(r, g, b) > 11;
    });
    expect(conTinte).toEqual([]);
  });

  it("la capa de tenant sigue mandando sobre el acento, el botón y la serie", () => {
    expect(indexCss).toMatch(/--acento:\s*var\(--color-primario,/);
    expect(indexCss).toMatch(/--boton:\s*var\(--color-primario,/);
    expect(indexCss).toMatch(/--serie-medio:\s*var\(--color-primario,/);
  });

  it("los recursos gráficos (SVG 3D y favicon) solo usan hex de la paleta", () => {
    const svgs = [
      ...archivos(path.join(SRC, "assets"), [".svg"]),
      ...archivos(path.join(FRONTEND, "public"), [".svg"]),
    ];
    const fuera = [];
    for (const archivo of svgs) {
      const texto = readFileSync(archivo, "utf8");
      for (const m of texto.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) {
        if (!HEX_PERMITIDOS.has(m[0].toUpperCase())) fuera.push(`${path.basename(archivo)}  ${m[0]}`);
      }
      if (/display-p3|rgba?\(/.test(texto)) fuera.push(`${path.basename(archivo)}  color fuera de sRGB hex`);
    }
    expect(fuera).toEqual([]);
  });
});
