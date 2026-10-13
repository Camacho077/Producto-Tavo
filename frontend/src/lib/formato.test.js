import { describe, expect, it } from "vitest";
import { formatearFecha, formatearFechaHora, formatearHora, minutosDesde } from "./formato";

// El backend manda instantes UTC sin zona; la pantalla los muestra en hora de
// Colombia sin importar la zona del navegador (2026-10-13: los cierres de
// caja salían 5 horas corridos).
describe("fechas en hora de Colombia", () => {
  it("un instante UTC sin zona se muestra en hora de Bogotá", () => {
    expect(formatearFechaHora("2026-10-13T02:15:00")).toMatch(/12 de oct de 2026.*09:15\s*p\.\s*m\./);
    expect(formatearHora("2026-10-12T15:50:00")).toMatch(/10:50\s*a\.\s*m\./);
  });

  it("con zona explícita no la vuelve a mover", () => {
    expect(formatearFechaHora("2026-10-12T15:50:00Z")).toBe(formatearFechaHora("2026-10-12T15:50:00"));
    expect(formatearFechaHora("2026-10-12T10:50:00-05:00")).toBe(formatearFechaHora("2026-10-12T15:50:00"));
  });

  it("el día de un instante es el de Colombia, y una fecha sola es ese día", () => {
    expect(formatearFecha("2026-10-13T02:15:00")).toMatch(/^12 de oct/);
    expect(formatearFecha("2026-10-12")).toMatch(/^12 de oct/);
    expect(formatearFecha("2026-10-12T12:00:00")).toMatch(/^12 de oct/);
  });

  it("minutos transcurridos desde un instante UTC sin zona", () => {
    expect(minutosDesde("2026-10-12T15:50:00", Date.parse("2026-10-12T16:05:30Z"))).toBe(15);
  });

  it("sin dato, guion", () => {
    expect(formatearFecha(null)).toBe("—");
    expect(formatearFechaHora("")).toBe("—");
  });
});
