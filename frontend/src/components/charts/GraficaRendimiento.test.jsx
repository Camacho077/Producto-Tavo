import { act, render, screen } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";

import GraficaRendimiento, { remuestrear, techo } from "@/components/charts/GraficaRendimiento";

/**
 * La gráfica dibuja escribiendo atributos a mano, fuera del ciclo de render de
 * React. Lo que hay que proteger es justamente eso:
 *   - que el trazo se calcule en JavaScript (nada de animar `d` por CSS, que
 *     en Firefox salta de golpe),
 *   - que cambiar de rango NO remonte los nodos (si se remontaran, volverían a
 *     correr las animaciones de entrada en cada clic: eso es el parpadeo),
 *   - que la capa de guía/punto/tooltip se mueva solo con transform.
 */

// jsdom no mide nada: sin un tamaño, el dibujo se salta por diseño.
const ANCHO = 900;
const ALTO = 260;
let clientWidth;
let clientHeight;

/**
 * jsdom PIDE los requestAnimationFrame pero no los EJECUTA dentro de `act`
 * (comprobado: una petición, cero ejecuciones), así que la interpolación
 * nunca correría sola en las pruebas. Aquí los cuadros se conducen a mano,
 * que además permite mirar el trazo cuadro a cuadro — justo lo que hay que
 * comprobar: que el dibujo se calcula en JavaScript y no de un salto.
 */
let pendientes = [];
let reloj = 0;
let rafReal;
let cancelReal;

function instalarCuadros() {
  rafReal = window.requestAnimationFrame;
  cancelReal = window.cancelAnimationFrame;
  pendientes = [];
  reloj = 0;
  window.requestAnimationFrame = (cb) => pendientes.push(cb);
  window.cancelAnimationFrame = () => {
    pendientes = [];
  };
}

function restaurarCuadros() {
  window.requestAnimationFrame = rafReal;
  window.cancelAnimationFrame = cancelReal;
}

/** Corre `n` cuadros de 16 ms y devuelve el trazo dejado por cada uno. */
function correrCuadros(nodo, n, pasoMs = 16) {
  const trazos = [];
  for (let i = 0; i < n; i += 1) {
    const cola = pendientes;
    pendientes = [];
    reloj += pasoMs;
    act(() => cola.forEach((cb) => cb(reloj)));
    trazos.push(nodo.getAttribute("d"));
  }
  return trazos;
}

beforeAll(() => {
  clientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
  clientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => ANCHO });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, get: () => ALTO });
});

afterAll(() => {
  if (clientWidth) Object.defineProperty(HTMLElement.prototype, "clientWidth", clientWidth);
  if (clientHeight) Object.defineProperty(HTMLElement.prototype, "clientHeight", clientHeight);
});

beforeEach(instalarCuadros);
afterEach(restaurarCuadros);

const serieDe = (valores, proyeccion = 0) => ({
  rango: "1m",
  unidad: "day",
  puntos: valores.map((v, i) => ({
    inicio: `2026-09-${String(i + 1).padStart(2, "0")}`,
    inicio_anterior: `2026-08-${String(i + 1).padStart(2, "0")}`,
    actual: v,
    anterior: v / 2,
  })),
  proyeccion: { inicio: "2026-10-01", valor: proyeccion },
});

describe("remuestrear — para poder interpolar entre rangos de distinto tamaño", () => {
  it("devuelve exactamente n puntos, conservando extremos", () => {
    expect(remuestrear([0, 10], 5)).toEqual([0, 2.5, 5, 7.5, 10]);
    expect(remuestrear([0, 4, 8], 2)).toEqual([0, 8]);
    expect(remuestrear([7], 3)).toEqual([7, 7, 7]);
  });

  it("con la serie vacía devuelve ceros, no NaN", () => {
    expect(remuestrear([], 4)).toEqual([0, 0, 0, 0]);
  });
});

describe("techo de la escala", () => {
  it("deja aire por encima del máximo", () => {
    expect(techo({ actual: [100], anterior: [50], proyeccion: 20 })).toBeCloseTo(112);
  });

  it("con todo en cero nunca devuelve 0 (dividir por él mandaría la línea al infinito)", () => {
    expect(techo({ actual: [0, 0], anterior: [0], proyeccion: 0 })).toBe(1);
  });
});

describe("GraficaRendimiento", () => {
  it("dibuja el trazo, el área, la comparativa y la proyección con atributos calculados", () => {
    const { container } = render(<GraficaRendimiento serie={serieDe([10, 20, 30], 40)} />);

    const linea = container.querySelector(".grafica__linea");
    const area = container.querySelector(".grafica__area");
    const anterior = container.querySelector(".grafica__anterior");
    const proyeccion = container.querySelector(".grafica__proyeccion");

    for (const nodo of [linea, area, anterior, proyeccion]) {
      expect(nodo.getAttribute("d")).toMatch(/^M[\d.]+,[\d.]+/);
    }
    // El trazo tiene un punto por dato.
    expect(linea.getAttribute("d").split("L")).toHaveLength(3);
    // El área cierra contra la línea base.
    expect(area.getAttribute("d")).toMatch(/Z$/);
  });

  it("cambiar de rango INTERPOLA el trazo cuadro a cuadro, no de un salto", () => {
    const { container, rerender } = render(<GraficaRendimiento serie={serieDe([10, 20, 30])} />);
    const linea = container.querySelector(".grafica__linea");
    const antes = linea.getAttribute("d");

    act(() => {
      rerender(<GraficaRendimiento serie={serieDe([90, 15, 60, 25, 80])} />);
    });
    const trazos = correrCuadros(linea, 12);

    // Muchos valores distintos = se está calculando el camino en JavaScript.
    // Si se animara el atributo `d` por CSS, aquí habría uno o dos (y en
    // Firefox, en pantalla, saltaría de golpe al final).
    expect(new Set(trazos).size).toBeGreaterThan(8);
    expect(trazos[0]).not.toBe(antes);
    // La serie nueva tiene cinco puntos: el remuestreo los lleva a cinco desde
    // el primer cuadro, sin pasar por un estado intermedio raro.
    expect(trazos[0].split("L")).toHaveLength(5);
  });

  it("cambiar de rango NO remonta los nodos: son los mismos elementos", () => {
    const { container, rerender } = render(<GraficaRendimiento serie={serieDe([10, 20, 30])} />);
    const linea = container.querySelector(".grafica__linea");
    const area = container.querySelector(".grafica__area");

    act(() => {
      rerender(<GraficaRendimiento serie={serieDe([90, 15, 60, 25, 80])} />);
    });
    correrCuadros(linea, 5);

    // Si se remontaran, las animaciones de entrada (el trazo que se dibuja)
    // volverían a correr en CADA clic de rango: eso es el parpadeo.
    expect(container.querySelector(".grafica__linea")).toBe(linea);
    expect(container.querySelector(".grafica__area")).toBe(area);
  });

  it("al terminar la interpolación el trazo queda exactamente en la serie nueva", () => {
    const { container, rerender } = render(<GraficaRendimiento serie={serieDe([10, 20, 30])} />);
    const linea = container.querySelector(".grafica__linea");

    act(() => {
      rerender(<GraficaRendimiento serie={serieDe([0, 100])} />);
    });
    const trazos = correrCuadros(linea, 60, 20); // 1,2 s > los 750 ms del morfeo
    const final = trazos[trazos.length - 1];

    // Dos puntos: el primero en la base y el segundo arriba del todo.
    expect(final.split("L")).toHaveLength(2);
    // Y se queda quieto: el último cuadro y el anterior son idénticos.
    expect(trazos[trazos.length - 2]).toBe(final);
  });

  it("durante el morfeo la capa del punto va SIN transición (sigue a la curva) y al terminar la recupera", () => {
    // Con la transición puesta, cada escritura por cuadro la reiniciaba y el
    // punto y el tooltip se quedaban atrás de la línea mientras morfeaba.
    const { container, rerender } = render(<GraficaRendimiento serie={serieDe([10, 20, 30])} />);
    const capa = container.querySelector(".grafica__capa");
    const linea = container.querySelector(".grafica__linea");
    expect(capa).not.toHaveClass("grafica__capa--morfeo");

    act(() => {
      rerender(<GraficaRendimiento serie={serieDe([90, 15, 60])} />);
    });
    correrCuadros(linea, 3);
    expect(capa).toHaveClass("grafica__capa--morfeo");

    correrCuadros(linea, 60, 20);
    expect(capa).not.toHaveClass("grafica__capa--morfeo");
  });

  it("la capa de guía, halo, punto y tooltip se mueve con translate3d", () => {
    const { container } = render(<GraficaRendimiento serie={serieDe([10, 20, 30])} />);
    const capas = container.querySelectorAll(".grafica__pos");
    expect(capas).toHaveLength(4);
    for (const capa of capas) {
      expect(capa.style.transform).toMatch(/^translate3d\(/);
    }
  });

  it("el tooltip describe el último punto mientras no hay cursor encima", () => {
    const { container } = render(<GraficaRendimiento serie={serieDe([10, 20, 30])} />);
    expect(container.querySelector(".grafica__tip-valor").textContent.replace(/ /g, " ")).toBe("$ 30");
    expect(container.querySelector(".grafica__tip-fecha").textContent).toBe("2026-09-03");
  });

  it("el eje lleva cinco etiquetas repartidas sobre la serie", () => {
    const { container } = render(<GraficaRendimiento serie={serieDe([1, 2, 3, 4, 5, 6, 7, 8, 9])} />);
    const etiquetas = [...container.querySelectorAll(".grafica__eje span")].map((n) => n.textContent);
    expect(etiquetas).toEqual(["2026-09-01", "2026-09-03", "2026-09-05", "2026-09-07", "2026-09-09"]);
  });

  it("sin movimiento en el rango, lo dice con un mensaje útil en vez de un hueco mudo", () => {
    render(<GraficaRendimiento serie={serieDe([0, 0, 0])} />);
    expect(screen.getByText(/Todavía no hay ventas completadas en este rango/)).toBeInTheDocument();
  });

  it("con datos no muestra el mensaje de vacío", () => {
    render(<GraficaRendimiento serie={serieDe([0, 5, 0])} />);
    expect(screen.queryByText(/Todavía no hay ventas/)).toBeNull();
  });
});
