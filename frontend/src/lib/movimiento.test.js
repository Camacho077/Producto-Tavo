import { describe, expect, it } from "vitest";

import { RESORTE, RESORTE_DURACION, curvaSuave, resorteComoLinear } from "@/lib/movimiento";

describe("curvas de movimiento del producto", () => {
  it("curvaSuave es la cubic-bezier(0.32, 0.72, 0, 1): parte de 0, llega a 1 y nunca retrocede", () => {
    expect(curvaSuave(0)).toBe(0);
    expect(curvaSuave(1)).toBe(1);
    let previo = 0;
    for (let i = 1; i <= 100; i += 1) {
      const y = curvaSuave(i / 100);
      expect(y).toBeGreaterThanOrEqual(previo);
      previo = y;
    }
    // Arranca rápido (curva de salida): a mitad de tiempo ya va muy avanzada.
    expect(curvaSuave(0.5)).toBeGreaterThan(0.8);
  });

  it("el resorte (rigidez 300, amortiguación 30) se asienta en 1 sin rebote visible", () => {
    const puntos = RESORTE.slice("linear(".length, -1).split(",").map(Number);
    expect(puntos[0]).toBe(0);
    expect(puntos.at(-1)).toBe(1);
    // Sobrepasa menos de un 1 %: físico, pero no es un rebote.
    expect(Math.max(...puntos)).toBeLessThan(1.01);
    expect(RESORTE_DURACION).toBeGreaterThan(400);
    expect(RESORTE_DURACION).toBeLessThan(600);
  });

  it("dentro de la regla del usuario: rigidez 260–320 y amortiguación 28–34 dan curvas válidas", () => {
    for (const [rigidez, amortiguacion] of [
      [260, 28],
      [320, 34],
    ]) {
      const curva = resorteComoLinear({ rigidez, amortiguacion, masa: 1 });
      expect(curva).toMatch(/^linear\(0, /);
    }
  });
});
