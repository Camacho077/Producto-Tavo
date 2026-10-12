/**
 * CURVAS DE MOVIMIENTO DEL PRODUCTO — una sola fuente para CSS y JavaScript.
 *
 * Regla (docs/DECISIONES.md, 2026-09-28): todo lo que se mueve usa UNA de
 * estas dos curvas, nunca `linear`, `ease` a secas ni rebotes.
 *
 *  - CURVA_SUAVE, cubic-bezier(0.32, 0.72, 0, 1): entradas, salidas, fades y
 *    cambios de color. En CSS es `--ease-suave` (index.css).
 *  - RESORTE: un resorte físico (rigidez 300, amortiguación 30, masa 1) para
 *    lo que se DESLIZA entre posiciones (indicadores, tooltip, hermanos que
 *    se reacomodan). CSS no tiene resortes, así que se muestrea la solución
 *    exacta de la ecuación y se expresa con la función `linear()` de CSS, que
 *    interpola entre esos puntos: el navegador lo ejecuta en el compositor
 *    como cualquier otra curva. Amortiguación 0,866: sobrepasa el destino un
 *    0,43 % (imperceptible, no es un rebote) y se asienta en 506 ms. En CSS es
 *    `--resorte` + `--resorte-duracion`; `movimiento.test.js` exige que los
 *    dos lados digan lo mismo.
 */

export const CURVA_SUAVE = [0.32, 0.72, 0, 1];

export const RESORTE_PARAMETROS = { rigidez: 300, amortiguacion: 30, masa: 1 };
export const RESORTE_DURACION = 506;

/** Posición del resorte (0→1) en el segundo `t`, solución subamortiguada. */
function posicionResorte(t, { rigidez, amortiguacion, masa }) {
  const w = Math.sqrt(rigidez / masa);
  const zeta = amortiguacion / (2 * Math.sqrt(rigidez * masa));
  const wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t));
}

/** El resorte como `linear(...)` de CSS: 25 muestras repartidas en su duración. */
export function resorteComoLinear(parametros = RESORTE_PARAMETROS, duracionMs = RESORTE_DURACION, muestras = 24) {
  const puntos = [];
  for (let i = 0; i <= muestras; i += 1) {
    const valor = i === muestras ? 1 : posicionResorte(((duracionMs / 1000) * i) / muestras, parametros);
    puntos.push(Number(valor.toFixed(4)));
  }
  return `linear(${puntos.join(", ")})`;
}

export const RESORTE = resorteComoLinear();

/**
 * La misma cubic-bezier que CSS, para las animaciones que corren en
 * JavaScript (contadores, morfeo de la gráfica). Se resuelve x→t con Newton y
 * bisección de respaldo, igual que hace el navegador.
 */
function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const muestraX = (t) => ((ax * t + bx) * t + cx) * t;
  const muestraY = (t) => ((ay * t + by) * t + cy) * t;
  const derivadaX = (t) => (3 * ax * t + 2 * bx) * t + cx;

  const resolverT = (x) => {
    let t = x;
    for (let i = 0; i < 8; i += 1) {
      const error = muestraX(t) - x;
      if (Math.abs(error) < 1e-6) return t;
      const d = derivadaX(t);
      if (Math.abs(d) < 1e-6) break;
      t -= error / d;
    }
    let bajo = 0;
    let alto = 1;
    t = x;
    while (bajo < alto) {
      const valor = muestraX(t);
      if (Math.abs(valor - x) < 1e-6) return t;
      if (x > valor) bajo = t;
      else alto = t;
      if (alto - bajo < 1e-7) break;
      t = (alto + bajo) / 2;
    }
    return t;
  };

  return (x) => (x <= 0 ? 0 : x >= 1 ? 1 : muestraY(resolverT(x)));
}

export const curvaSuave = cubicBezier(...CURVA_SUAVE);

export const lerp = (a, b, t) => a + (b - a) * t;

export const hayMovimientoReducido = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Traslado vertical y escala Y que el nodo muestra AHORA (incluida una
 * animación a medias). Sin DOMMatrix (jsdom) devuelve la identidad.
 */
export function trasladoVisual(nodo) {
  if (typeof DOMMatrixReadOnly !== "function" || typeof getComputedStyle !== "function") return { y: 0, escalaY: 1 };
  const valor = getComputedStyle(nodo).transform;
  if (!valor || valor === "none") return { y: 0, escalaY: 1 };
  const m = new DOMMatrixReadOnly(valor);
  return { y: m.m42, escalaY: m.d || 1 };
}

/** WAAPI no existe en jsdom ni en navegadores muy viejos: sin ella, sin movimiento. */
export const puedeAnimar = (nodo) => Boolean(nodo) && typeof nodo.animate === "function" && !hayMovimientoReducido();
