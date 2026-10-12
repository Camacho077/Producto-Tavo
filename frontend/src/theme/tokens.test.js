import { describe, expect, it, beforeEach } from "vitest";

import { aclarar, aplicarTema, defaultTheme, oscurecer } from "@/theme/tokens";

const raiz = () => document.documentElement;

beforeEach(() => {
  raiz().style.removeProperty("--color-primario");
  raiz().style.removeProperty("--color-primario-claro");
  raiz().style.removeProperty("--color-primario-oscuro");
});

describe("aplicarTema (personalización por tenant)", () => {
  it("aplica el color del tenant en snake_case, como lo guarda el backend", () => {
    aplicarTema({ color_primario: "#7A2E2E" });

    expect(raiz().style.getPropertyValue("--color-primario")).toBe("#7a2e2e");
  });

  it("acepta también camelCase", () => {
    aplicarTema({ colorPrimario: "#1E3A5F" });

    expect(raiz().style.getPropertyValue("--color-primario")).toBe("#1e3a5f");
  });

  it("deriva las variantes de hover y activo del color del tenant", () => {
    aplicarTema({ color_primario: "#7A2E2E" });

    const claro = raiz().style.getPropertyValue("--color-primario-claro");
    const oscuro = raiz().style.getPropertyValue("--color-primario-oscuro");

    expect(claro).toBeTruthy();
    expect(oscuro).toBeTruthy();
    expect(claro).not.toBe(oscuro);
  });

  it("sin color de tenant, limpia la variable y el acento vuelve al del sistema", () => {
    aplicarTema({ color_primario: "#7A2E2E" });
    aplicarTema(defaultTheme);

    expect(raiz().style.getPropertyValue("--color-primario")).toBe("");
  });

  it("ignora un color inválido en vez de romper el tema", () => {
    aplicarTema({ color_primario: "no-es-un-color" });

    expect(raiz().style.getPropertyValue("--color-primario")).toBe("");
  });
});

describe("utilidades de color", () => {
  it("aclarar acerca el color al blanco y oscurecer al negro", () => {
    expect(aclarar("#000000", 1)).toBe("#ffffff");
    expect(oscurecer("#ffffff", 1)).toBe("#000000");
  });

  it("expande hex de 3 dígitos", () => {
    expect(aclarar("#000", 0)).toBe("#000000");
  });
});
