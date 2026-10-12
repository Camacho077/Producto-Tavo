import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { CURVA_SUAVE, RESORTE, RESORTE_DURACION } from "@/lib/movimiento";

/**
 * PROTECCIÓN AUTOMATIZADA de las reglas de rendimiento de la maqueta
 * (docs/dashboard-referencia.html, sección 2 del encargo).
 *
 * Son reglas que se pierden solas: alguien agrega un `backdrop-filter` porque
 * queda bonito, o una transición de `height` porque es lo primero que se
 * ocurre, y el flashazo y el tirón vuelven sin que nadie lo note hasta medir.
 * Este test lee el CSS del producto y falla si eso pasa.
 *
 * Si alguna vez hay un caso legítimo, la excepción se documenta ABAJO con su
 * porqué, no se borra el test.
 */

const RAIZ = path.join(path.dirname(fileURLToPath(import.meta.url)));

function archivosCss(dir) {
  return readdirSync(dir).flatMap((nombre) => {
    const completo = path.join(dir, nombre);
    if (statSync(completo).isDirectory()) return archivosCss(completo);
    return nombre.endsWith(".css") ? [completo] : [];
  });
}

/** El CSS sin comentarios, conservando los saltos de línea (para citar la línea). */
function sinComentarios(texto) {
  return texto.replace(/\/\*[\s\S]*?\*\//g, (comentario) => comentario.replace(/[^\n]/g, " "));
}

/**
 * Cada declaración de una propiedad en el CSS del producto, con su archivo y
 * su línea. Lee la declaración COMPLETA aunque ocupe varias líneas (antes se
 * leía línea a línea y un `transition:` partido en varias se escapaba).
 */
function declaraciones(propiedades) {
  const encontradas = [];
  const patron = new RegExp(`(?:^|[\\s;{])(${propiedades})\\s*:\\s*([^;{}]+);`, "g");
  for (const archivo of archivosCss(RAIZ)) {
    const texto = sinComentarios(readFileSync(archivo, "utf8"));
    for (const m of texto.matchAll(patron)) {
      encontradas.push({
        archivo: path.relative(RAIZ, archivo).replace(/\\/g, "/"),
        linea: texto.slice(0, m.index).split("\n").length + (m[0].startsWith("\n") ? 1 : 0),
        propiedad: m[1],
        valor: m[2].replace(/\s+/g, " ").trim(),
      });
    }
  }
  return encontradas;
}

/** Cada declaración `transition:` del producto, con su archivo y su línea. */
const transiciones = () => declaraciones("transition(?:-property)?");

// Desde el 2026-09-30 la pantalla de acceso también sigue las reglas de
// curvas (se rediseñó: fondo negro sólido, panel centrado y transparente).
const FUERA_DE_ALCANCE = [];

/** Propiedades que NO se pueden animar: obligan a recalcular layout o a
 *  repintar la caja entera en cada cuadro. */
const PROHIBIDAS = [
  "width",
  "height",
  "top",
  "left",
  "right",
  "bottom",
  "margin",
  "padding",
  "box-shadow",
  "grid-template-rows",
  "grid-template-columns",
];

describe("reglas de movimiento y rendimiento (maqueta aprobada)", () => {
  it("no hay ni un backdrop-filter en el producto", () => {
    const culpables = archivosCss(RAIZ)
      .map((archivo) => ({ archivo, texto: readFileSync(archivo, "utf8") }))
      // Las menciones dentro de comentarios son justamente la explicación de
      // por qué NO se usa; solo se persigue la declaración real.
      .filter(({ texto }) => /^\s*-?(webkit-)?backdrop-filter\s*:/m.test(texto))
      .map(({ archivo }) => path.relative(RAIZ, archivo));

    expect(
      culpables,
      "backdrop-filter sobre un panel grande obliga a rasterizar todo lo que hay debajo " +
        "antes del primer pintado: era la causa del flashazo al cargar. Se reemplaza por " +
        "un fondo con degradado semiopaco (ver --marco-fondo en index.css)."
    ).toEqual([]);
  });

  it("solo se animan transform y opacity — nunca width, height, top, left o box-shadow", () => {
    const malas = transiciones().filter(({ valor }) =>
      PROHIBIDAS.some((prop) => new RegExp(`(^|[\\s,])${prop}([\\s,]|$)`).test(valor))
    );

    expect(
      malas.map((t) => `${t.archivo}:${t.linea} -> ${t.valor}`),
      "animar una propiedad de layout recalcula la caja en cada cuadro; el movimiento " +
        "solo puede ir por transform y opacity (más color, que es repintado barato)."
    ).toEqual([]);
  });

  it("nunca `transition: all`", () => {
    const malas = transiciones().filter(({ valor }) => /^all\b/.test(valor));
    expect(malas.map((t) => `${t.archivo}:${t.linea}`)).toEqual([]);
  });

  it("solo dos animaciones en bucle: el halo del punto y la flotación de las miniaturas", () => {
    const enBucle = declaraciones("animation|animation-iteration-count")
      .filter(({ valor }) => /\binfinite\b/.test(valor))
      .map(({ archivo, linea, valor }) => ({ archivo, linea, texto: valor }));

    // Lista cerrada. Agregar algo aquí es una decisión explícita, no un
    // descuido: cada bucle nuevo es una capa que el compositor repinta para
    // siempre.
    const permitidas = [
      "grafica-halo", // el latido del punto actual de la gráfica
      "objeto-flota", // la flotación suave de los objetos 3D del inventario
      "spinner", // el giro del indicador de carga
      "girar",
      // (La deriva de la foto y las vetas del acceso se fueron con la foto,
      // 2026-09-30: el acceso ya no tiene ningún bucle.)
    ];
    const noPermitidas = enBucle.filter((x) => !permitidas.some((nombre) => x.texto.includes(nombre)));

    expect(
      noPermitidas.map((x) => `${x.archivo}:${x.linea} -> ${x.texto}`),
      "cada animación corre UNA vez y se queda quieta; los únicos bucles permitidos están " +
        "en la lista de este test, y agregar uno nuevo es una decisión explícita."
    ).toEqual([]);
  });

  it("curvas: solo los tokens del producto — nunca `ease` por defecto, `linear` suelto ni cubic-bezier a mano", () => {
    // Excepción documentada (docs/DECISIONES.md): el spinner gira a
    // velocidad constante; con cualquier curva la rotación late en cada vuelta.
    const excepciones = [/^spinner-giro \d+m?s linear infinite( !important)?$/];
    const malas = declaraciones("transition|animation|animation-timing-function|transition-timing-function")
      .filter(({ archivo }) => !FUERA_DE_ALCANCE.includes(archivo))
      .filter(({ valor }) => !excepciones.some((e) => e.test(valor)))
      // Los tokens (`var(--ease-suave)`) son justamente lo permitido.
      .map((t) => ({ ...t, crudo: t.valor.replace(/var\([^()]*(\([^()]*\))?[^()]*\)/g, "") }))
      .filter(
        ({ crudo }) =>
          /(^|[\s,])ease(-in|-out|-in-out)?([\s,]|$)/.test(crudo) ||
          /(^|[\s,])linear([\s,]|$)/.test(crudo) ||
          /cubic-bezier\(/.test(crudo)
      );
    expect(
      malas.map((t) => `${t.archivo}:${t.linea} -> ${t.valor}`),
      "las curvas salen de index.css: --ease-suave (entradas, salidas, color), --resorte " +
        "(lo que se desliza) y --vaiven (solo los dos bucles)."
    ).toEqual([]);
  });

  it("nada de rebotes: ninguna cubic-bezier con Y fuera de [0, 1]", () => {
    const rebotes = [];
    for (const archivo of archivosCss(RAIZ)) {
      const texto = sinComentarios(readFileSync(archivo, "utf8"));
      for (const m of texto.matchAll(/cubic-bezier\(([^)]+)\)/g)) {
        const [, y1, , y2] = m[1].split(",").map(Number);
        if (y1 < 0 || y1 > 1 || y2 < 0 || y2 > 1) rebotes.push(`${path.relative(RAIZ, archivo)} -> ${m[0]}`);
      }
    }
    expect(rebotes, "los rebotes y elásticos se ven anticuados").toEqual([]);
  });

  it("los tokens de curva valen lo aprobado y el resorte de CSS es el mismo que el de JavaScript", () => {
    const base = readFileSync(path.join(RAIZ, "index.css"), "utf8");
    const valor = (token) => new RegExp(`${token}:\\s*([^;]+);`).exec(base)?.[1].trim();
    expect(valor("--ease-suave")).toBe(`cubic-bezier(${CURVA_SUAVE.join(", ")})`);
    expect(valor("--resorte")).toBe(RESORTE);
    expect(valor("--resorte-duracion")).toBe(`${RESORTE_DURACION}ms`);
  });

  it("ningún atajo `animation` inválido (dos fill-mode invalidan la declaración ENTERA)", () => {
    // Así se rompieron las barras de más vendidos: `backwards forwards` hizo
    // que el navegador descartara la línea, no se animaban y se pintaban al 100 %.
    const invalidas = declaraciones("animation").filter(
      ({ valor }) => valor.split(",").some((capa) => (capa.match(/\b(forwards|backwards|both)\b/g) ?? []).length > 1)
    );
    expect(invalidas.map((t) => `${t.archivo}:${t.linea} -> ${t.valor}`)).toEqual([]);
  });

  it("las barras de proporción guardan su valor como ESTADO (scaleX), no solo en una animación", () => {
    const css = readFileSync(path.join(RAIZ, "modules/dashboard/dashboard.css"), "utf8");
    const regla = /\.barra__relleno\s*\{([^}]*)\}/.exec(sinComentarios(css))?.[1] ?? "";
    expect(regla).toMatch(/transform:\s*scaleX\(var\(--proporcion/);
    expect(regla).not.toMatch(/\banimation\s*:/);
  });

  it("el MARCO (.app) no se anima: es una capa del tamaño de la pantalla y atrasaba el LCP", () => {
    // Medido el 2026-09-28: con el marco animado (opacidad o solo transform)
    // el saludo tardaba ~750-900 ms en contar como pintado tras montarse; sin
    // animarlo, ~185 ms. Lo que entra al recargar es lo de DENTRO.
    const shell = sinComentarios(readFileSync(path.join(RAIZ, "components/shell.css"), "utf8"));
    const regla = /\.app\s*\{([^}]*)\}/.exec(shell)?.[1] ?? "";
    expect(regla).not.toMatch(/\b(animation|transition)\s*:/);
    const vista = /\.vista\s*\{([^}]*)\}/.exec(sinComentarios(readFileSync(path.join(RAIZ, "index.css"), "utf8")))?.[1] ?? "";
    expect(vista, "la entrada de vista no lleva retardo (atrasaba el LCP)").not.toMatch(/\d+ms\s+backwards/);
  });

  it("movimiento reducido = menos movimiento, no cero feedback: spinner lento, fades sin desplazamiento", () => {
    // 2026-09-29: el `*` con !important congelaba el spinner (la regla de
    // 2 s en ui.css perdía) y quitaba hasta el fade de la vista y las alertas.
    const base = sinComentarios(readFileSync(path.join(RAIZ, "index.css"), "utf8"));
    const bloque = base.slice(base.indexOf("@media (prefers-reduced-motion: reduce)"));
    const regla = (sel) => new RegExp(`\\${sel}\\s*\\{([^}]*)\\}`).exec(bloque)?.[1] ?? "";
    expect(regla(".spinner"), "el spinner sigue girando").toMatch(/spinner-giro\s+\d+m?s\s+linear\s+infinite\s*!important/);
    expect(regla(".vista"), "la vista conserva un fade").toMatch(/animation:\s*vista-aparece\b/);
    expect(regla(".alerta"), "la alerta conserva su fade").toMatch(/transition-duration:\s*var\(--duracion-alerta\)\s*!important/);
    // Ninguna excepción trae retardo ni desplazamiento.
    for (const sel of [".vista", ".alerta"]) expect(regla(sel)).not.toMatch(/delay|\d+ms\s+\d+ms/);
    const aparece = /@keyframes vista-aparece\s*\{([\s\S]*?)\n\}/.exec(base)?.[1] ?? "";
    expect(aparece).toMatch(/opacity/);
    expect(aparece).not.toMatch(/transform/);
  });

  it("la secuencia de entrada de la gráfica termina en 1,2 s como máximo, y los bloques del dashboard duran 300 ms", () => {
    const base = sinComentarios(readFileSync(path.join(RAIZ, "index.css"), "utf8"));
    const token = (n) => Number(new RegExp(`${n}:\\s*(\\d+)ms`).exec(base)?.[1]);
    const ms = (v) => (v.startsWith("var(") ? token(v.slice(4, -1)) : Number(v.replace("ms", "")));
    expect(token("--dur-bloque")).toBe(300);
    const graficas = declaraciones("animation")
      .filter(({ archivo }) => archivo === "components/charts/charts.css")
      .filter(({ valor }) => !/\binfinite\b/.test(valor));
    expect(graficas.length).toBeGreaterThanOrEqual(6);
    for (const { valor } of graficas) {
      const tiempos = valor.split(/\s+/).filter((t) => /^(var\(--dur-[a-z]+\)|\d+ms)$/.test(t));
      const [duracion, retardo = "0ms"] = tiempos;
      expect(ms(duracion) + ms(retardo), valor).toBeLessThanOrEqual(1200);
    }
  });

  it("las tarjetas que se leen con el cursor no se elevan, y todo botón da feedback al pulsar", () => {
    const dash = sinComentarios(readFileSync(path.join(RAIZ, "modules/dashboard/dashboard.css"), "utf8"));
    expect(/\.tarjeta--quieta:hover\s*\{([^}]*)\}/.exec(dash)?.[1]).toMatch(/transform:\s*none/);
    const ui = sinComentarios(readFileSync(path.join(RAIZ, "components/ui/ui.css"), "utf8"));
    expect(/\.btn:not\(:disabled\):active\s*\{([^}]*)\}/.exec(ui)?.[1]).toMatch(/transform:\s*scale\(0\.9[5-8]\)/);
    expect(/\.btn\s*\{([^}]*)\}/.exec(ui)?.[1]).toMatch(/transform var\(--dur-color\)/);
  });

  it("`prefers-reduced-motion` anula también los RETARDOS, no solo las duraciones", () => {
    const base = readFileSync(path.join(RAIZ, "index.css"), "utf8");
    const bloque = base.slice(base.indexOf("@media (prefers-reduced-motion: reduce)"));
    for (const propiedad of [
      "animation-duration",
      "animation-delay",
      "transition-duration",
      "transition-delay",
    ]) {
      expect(bloque, `falta ${propiedad} en el bloque de movimiento reducido`).toContain(
        `${propiedad}: 0`
      );
    }
  });
});
