import { describe, expect, it } from "vitest";
import { modulosVisibles } from "@/config/modules";

describe("modulosVisibles", () => {
  it("el plan básico trae lo que un restaurante necesita para operar", () => {
    const claves = modulosVisibles("basico").map((m) => m.key);
    expect(claves).toEqual(["dashboard", "ordenes", "cocina", "carta", "ventas", "seguridad", "ajustes"]);
  });

  it("agrega el inventario en el plan estándar", () => {
    const claves = modulosVisibles("estandar").map((m) => m.key);
    expect(claves).toEqual(["dashboard", "ordenes", "cocina", "carta", "inventario", "ventas", "seguridad", "ajustes"]);
  });

  it("un submódulo con `permiso` se muestra según ese permiso (Combos usa el de productos)", () => {
    const carta = modulosVisibles("pro_ia", [], (m) => m === "productos").find((m) => m.key === "carta");
    expect(carta.hijos.map((h) => h.key)).toEqual(["productos", "combos"]);
  });

  it("incluye el módulo de IA solo en el plan pro_ia", () => {
    const claves = modulosVisibles("pro_ia").map((m) => m.key);
    expect(claves).toContain("ia");
    expect(modulosVisibles("basico").map((m) => m.key)).not.toContain("ia");
  });
});
