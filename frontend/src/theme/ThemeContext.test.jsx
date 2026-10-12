import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";

import { ThemeProvider, useTheme } from "@/theme/ThemeContext";

function Sonda() {
  const { modo, alternarModo } = useTheme();
  return (
    <button onClick={alternarModo} data-modo={modo}>
      modo: {modo}
    </button>
  );
}

function renderConTema() {
  return render(
    <ThemeProvider>
      <Sonda />
    </ThemeProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeProvider", () => {
  // Desde la paleta monocromática (2026-10-01) el claro es el principal.
  it("arranca en modo claro por defecto", () => {
    renderConTema();

    expect(screen.getByRole("button")).toHaveAttribute("data-modo", "claro");
    expect(document.documentElement.getAttribute("data-theme")).toBe("claro");
  });

  it("alterna a oscuro y lo persiste", () => {
    renderConTema();

    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("button")).toHaveAttribute("data-modo", "oscuro");
    expect(document.documentElement.getAttribute("data-theme")).toBe("oscuro");
    expect(localStorage.getItem("js_company_modo")).toBe("oscuro");
  });

  it("respeta el modo guardado de una sesión anterior", () => {
    localStorage.setItem("js_company_modo", "oscuro");

    renderConTema();

    expect(screen.getByRole("button")).toHaveAttribute("data-modo", "oscuro");
  });
});
