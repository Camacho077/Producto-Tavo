import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Table from "./Table";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const leer = (nombre) => readFileSync(path.join(AQUI, nombre), "utf8");

/**
 * La tabla pasa a TARJETAS cuando no cabe en su contenedor (2026-09-30): con
 * un umbral fijo de ventana, entre 768 y 900 px siete tablas se salían de la
 * tarjeta y la página entera se desplazaba de lado. jsdom no calcula
 * maquetación, así que se simulan el ancho mínimo de la tabla y el del
 * contenedor.
 */
const columnas = [
  { clave: "nombre", titulo: "Nombre" },
  { clave: "total", titulo: "Total", cifra: true },
];
const filas = [{ id: 1, nombre: "Arroz", total: "$ 3.200" }];

function simular({ minimoTabla, anchoContenedor, pantallaAngosta = false }) {
  vi.spyOn(HTMLTableElement.prototype, "getBoundingClientRect").mockReturnValue({ width: minimoTabla });
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(anchoContenedor);
  window.matchMedia = vi.fn().mockReturnValue({
    matches: pantallaAngosta,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  delete window.matchMedia;
});

describe("Table: tabla si cabe, tarjetas si no", () => {
  it("se queda en TABLA cuando cabe en su contenedor", () => {
    simular({ minimoTabla: 520, anchoContenedor: 1048 });
    const { container } = render(<Table columnas={columnas} filas={filas} />);
    expect(container.querySelector(".tabla-contenedor")).not.toHaveClass("tabla-contenedor--apilada");
  });

  it("pasa a TARJETAS cuando la tabla es más ancha que su contenedor", () => {
    simular({ minimoTabla: 851, anchoContenedor: 760 });
    const { container } = render(<Table columnas={columnas} filas={filas} />);
    expect(container.querySelector(".tabla-contenedor")).toHaveClass("tabla-contenedor--apilada");
  });

  it("en pantallas de menos de 768 px siempre va en tarjetas", () => {
    simular({ minimoTabla: 200, anchoContenedor: 325, pantallaAngosta: true });
    const { container } = render(<Table columnas={columnas} filas={filas} />);
    expect(container.querySelector(".tabla-contenedor")).toHaveClass("tabla-contenedor--apilada");
  });

  it("la vista de tarjetas depende de la clase, no de un media query de ventana", () => {
    const css = leer("ui.css");
    expect(css).toMatch(/\.tabla-contenedor--apilada \.tabla thead \{/);
    expect(css).not.toMatch(/@media \(max-width: 767px\) \{\s*\.tabla/);
    // Anchos proporcionales: ninguna columna con `width: 1%`.
    expect(css.replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/\.celda--ajustada \{\s*width: 1%/);
  });
});

describe("formularios de pantalla", () => {
  it(".pantalla-estrecha ocupa todo el ancho hasta 720 px (no se encoge a su contenido)", () => {
    const css = leer("pantallas.css");
    const regla = /\.pantalla-estrecha \{([^}]*)\}/.exec(css)?.[1] ?? "";
    expect(regla).toMatch(/width:\s*100%/);
    expect(regla).toMatch(/max-width:\s*720px/);
  });
});
