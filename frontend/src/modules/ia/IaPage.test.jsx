import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ api: { get: vi.fn() } }));

import { api } from "@/lib/api";
import IaPage from "@/modules/ia/IaPage";

const RESPUESTA = {
  generado_en: "2026-10-01T15:00:00",
  motor: "Reglas estadísticas locales",
  privacidad: "Calculado dentro del sistema. No se envía ningún dato a servicios externos.",
  base: { ventas: 3, dias_con_venta: 2, dias: 90, suficiente: false, mensaje: "Con 3 ventas completadas en 2 días todavía no hay base." },
  secciones: [
    {
      clave: "precios",
      titulo: "Oportunidades de precio",
      descripcion: "Productos con margen menor a 15 %.",
      requiere_costos: true,
      sin_datos: null,
      sugerencias: [
        {
          clave: "precio:p1",
          tipo: "precio",
          nivel: "oportunidad",
          titulo: "Aceite deja poco margen",
          por_que: "Cuesta $9.000 y se vende a $10.000: margen de 10 %.",
          datos: [{ etiqueta: "Margen", valor: "10 %" }],
          accion: "Evalúa subir el precio hacia $12.000.",
          enlace: { recurso: "producto", id: "p1" },
        },
      ],
    },
    { clave: "patrones", titulo: "Patrones de venta", descripcion: "Días y horas.", requiere_costos: false, sin_datos: "Hacen falta al menos 10 ventas.", sugerencias: [] },
  ],
};

const montar = () => render(<MemoryRouter><IaPage /></MemoryRouter>);

beforeEach(() => vi.clearAllMocks());

describe("Sugerencias IA", () => {
  it("cada sugerencia dice por qué, con qué datos y a dónde ir", async () => {
    api.get.mockResolvedValue({ data: RESPUESTA });
    montar();
    const titulo = await screen.findByRole("heading", { name: "Aceite deja poco margen" });
    expect(titulo).toBeInTheDocument();
    expect(screen.getByText(/Cuesta \$9\.000 y se vende a \$10\.000/)).toBeInTheDocument();
    expect(screen.getByText("Margen").nextSibling).toHaveTextContent("10 %");
    expect(screen.getByRole("link", { name: "Ver plato" })).toHaveAttribute("href", "/carta/p1");
    expect(api.get).toHaveBeenCalledWith("/ia/sugerencias");
  });

  it("una sección sin sugerencias dice el motivo, y la base insuficiente se anuncia", async () => {
    api.get.mockResolvedValue({ data: RESPUESTA });
    montar();
    expect(await screen.findByText("Hacen falta al menos 10 ventas.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("todavía no hay base");
    expect(screen.getByText(/No se envía ningún dato a servicios externos/)).toBeInTheDocument();
  });

  it("si falla, muestra la causa concreta del backend", async () => {
    api.get.mockRejectedValue({ response: { data: { detail: "El plan Estándar de tu empresa no incluye las Sugerencias IA." } } });
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent("El plan Estándar de tu empresa no incluye las Sugerencias IA.");
  });
});
