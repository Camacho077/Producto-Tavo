import { describe, expect, it } from "vitest";
import { modulosVisibles } from "@/config/modules";

describe("modulosVisibles", () => {
  it("solo muestra los módulos básicos para el plan básico", () => {
    const claves = modulosVisibles("basico").map((m) => m.key);
    expect(claves).toEqual(["dashboard", "seguridad"]);
  });

  it("agrega compras y ventas para el plan estándar", () => {
    const claves = modulosVisibles("estandar").map((m) => m.key);
    expect(claves).toEqual(["dashboard", "compras", "ventas", "seguridad"]);
  });

  it("incluye el módulo de IA solo en el plan pro_ia", () => {
    const claves = modulosVisibles("pro_ia").map((m) => m.key);
    expect(claves).toContain("ia");
    expect(modulosVisibles("basico").map((m) => m.key)).not.toContain("ia");
  });
});
