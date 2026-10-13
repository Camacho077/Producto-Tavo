import { describe, expect, it } from "vitest";
import { hojasDe, inicioDeRol, modulosVisibles } from "@/config/modules";

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

// Los cuatro roles de ejemplo (backend/app/core/catalogo_permisos.py).
const ROLES = {
  cajero: { ventas: ["ver", "crear"], caja: ["ver", "cambiar_estado"], ordenes: ["ver", "crear", "editar", "cambiar_estado"] },
  mesero: { ordenes: ["ver", "crear", "editar", "cambiar_estado"] },
  cocinero: { cocina: ["ver", "cambiar_estado"] },
};
const puedeCon = (permisos) => (m, a = "ver") => Boolean(permisos[m]?.includes(a));

describe("cada rol entra a su pantalla (fase 7)", () => {
  it("administrador al dashboard, cajero a la caja, mesero a tomar pedido, cocinero a la cocina", () => {
    const todo = () => true;
    expect(inicioDeRol(modulosVisibles("pro_ia", [], todo), todo)).toBe("/");
    for (const [rol, destino] of [["cajero", "/caja"], ["mesero", "/ordenes/nueva"], ["cocinero", "/cocina"]]) {
      const puede = puedeCon(ROLES[rol]);
      expect(inicioDeRol(modulosVisibles("pro_ia", [], puede), puede), rol).toBe(destino);
    }
  });

  it("el menú de cada rol trae solo lo suyo", () => {
    const hojas = (rol) => hojasDe(modulosVisibles("pro_ia", [], puedeCon(ROLES[rol]))).map((h) => h.path);
    expect(hojas("mesero")).toEqual(["/ordenes/nueva", "/ordenes", "/ordenes/mesas"]);
    expect(hojas("cocinero")).toEqual(["/cocina"]);
    expect(hojas("cajero")).toEqual(["/ordenes/nueva", "/ordenes", "/ordenes/mesas", "/caja", "/caja/ventas", "/caja/cierres"]);
  });
});
