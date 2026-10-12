// Sistema de diseño — lógica de tema.
//
// ÚNICO origen de los valores de color: src/index.css (variables CSS con
// roles semánticos que cambian entre modo claro y oscuro). Este módulo NO
// duplica esos valores; solo:
//   1. Aplica la personalización por cliente (Tenant.theme_config) sobre la
//      capa de acento, sin tocar el resto del sistema.
//   2. Lee tokens ya resueltos del DOM, para que las gráficas respeten a la
//      vez el modo claro/oscuro y el color del tenant.

export const MODO_OSCURO = "oscuro";
export const MODO_CLARO = "claro";

// Tema por defecto del producto (JS Company). Un tenant puede sobreescribir
// su color primario y el producto entero responde.
export const defaultTheme = {
  colorPrimario: null, // null = usar el acento del modo activo (marfil / tierra)
};

function normalizarHex(hex) {
  if (typeof hex !== "string") return null;
  const limpio = hex.trim().toLowerCase();
  if (!/^#([0-9a-f]{3}|[0-9a-f]{6})$/.test(limpio)) return null;
  if (limpio.length === 4) {
    return `#${limpio[1]}${limpio[1]}${limpio[2]}${limpio[2]}${limpio[3]}${limpio[3]}`;
  }
  return limpio;
}

function mezclar(hex, objetivo, proporcion) {
  const base = normalizarHex(hex);
  if (!base) return hex;
  const canales = [1, 3, 5].map((i) => parseInt(base.slice(i, i + 2), 16));
  const destino = [1, 3, 5].map((i) => parseInt(objetivo.slice(i, i + 2), 16));
  const mezclados = canales.map((c, i) =>
    Math.round(c + (destino[i] - c) * proporcion).toString(16).padStart(2, "0")
  );
  return `#${mezclados.join("")}`;
}

// El objetivo lleva "#" porque mezclar() indexa igual que un hex normalizado.
export const aclarar = (hex, proporcion = 0.18) => mezclar(hex, "#ffffff", proporcion);
export const oscurecer = (hex, proporcion = 0.18) => mezclar(hex, "#000000", proporcion);

/**
 * Aplica la personalización del tenant. Acepta las dos convenciones que
 * existen en el sistema: camelCase (frontend) y snake_case (lo que guarda el
 * backend en Tenant.theme_config, ver automatizaciones/deploy/alta_tenant.py).
 *
 * Solo toca la capa de acento: el resto del sistema de diseño (espresso y
 * marfil, blanco y crema, tipografía) es la base del producto y no se
 * personaliza.
 */
export function aplicarTema(theme = defaultTheme) {
  const root = document.documentElement;
  const colorPrimario = normalizarHex(theme?.colorPrimario ?? theme?.color_primario ?? null);

  if (colorPrimario) {
    root.style.setProperty("--color-primario", colorPrimario);
    root.style.setProperty("--color-primario-claro", aclarar(colorPrimario, 0.18));
    root.style.setProperty("--color-primario-oscuro", oscurecer(colorPrimario, 0.18));
  } else {
    // Sin color de tenant: el acento vuelve al del modo activo.
    root.style.removeProperty("--color-primario");
    root.style.removeProperty("--color-primario-claro");
    root.style.removeProperty("--color-primario-oscuro");
  }

  const fuente = theme?.fuente ?? theme?.fuente_base;
  if (fuente) {
    root.style.setProperty("--fuente-base", fuente);
  }
}

/** Lee un token CSS ya resuelto (respeta modo claro/oscuro y tenant). */
export function leerToken(nombre, fallback = "") {
  if (typeof window === "undefined") return fallback;
  const valor = getComputedStyle(document.documentElement).getPropertyValue(nombre);
  return valor ? valor.trim() : fallback;
}

/* ==========================================================================
   TOKENS QUE NECESITA EL JAVASCRIPT

   Por qué existe esta capa: en SVG, `var(--x)` dentro de un ATRIBUTO de
   presentación (stroke, fill, stop-color) NO resuelve — solo funciona cuando
   el color se aplica por CSS. La gráfica de rendimiento escribe esos
   atributos, así que necesita los colores ya calculados.

   Ningún componente escribe un hex: pide el token por su nombre y lo resuelve
   aquí, de modo que sigue respetando las dos capas de tema (modo claro/oscuro
   y el color de marca del tenant).
   ========================================================================== */
export const TOKENS_GRAFICA = {
  // Serie actual: acento del modo (o el color del tenant) y las tres paradas
  // de su degradado horizontal.
  acento: "--acento",
  serieInicio: "--serie-inicio",
  serieMedio: "--serie-medio",
  serieFin: "--serie-fin",
  acentoLuz: "--acento-luz",
  acentoProfundo: "--acento-profundo",
  // Serie de comparación (periodo anterior) y rejilla.
  comparacion: "--serie-comparacion",
  grid: "--grid-grafica",
  // Superficies y textos que usa la gráfica.
  superficie: "--superficie",
  texto: "--texto",
  textoTerciario: "--texto-terciario",
  borde: "--borde",
  linea: "--linea",
  negativo: "--negativo-texto",
};

/** Resuelve de una vez todos los tokens que la gráfica escribe en atributos SVG. */
export function leerTokensGrafica() {
  return Object.fromEntries(
    Object.entries(TOKENS_GRAFICA).map(([clave, variable]) => [clave, leerToken(variable)])
  );
}

