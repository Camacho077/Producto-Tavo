import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Pildoras from "@/components/ui/Pildoras";

const OPCIONES = [
  { clave: "hoy", etiqueta: "Hoy" },
  { clave: "mes", etiqueta: "Mes" },
  { clave: "anio", etiqueta: "Año" },
];

describe("Píldoras segmentadas", () => {
  it("el fondo de la opción activa es UN solo nodo que se desliza", () => {
    const { container, rerender } = render(
      <Pildoras opciones={OPCIONES} valor="hoy" onCambiar={() => {}} etiqueta="Periodo" />
    );

    // Un indicador, no un fondo por botón: así el cambio es una transformación
    // y no dos repintados.
    expect(container.querySelectorAll(".pildoras__indicador")).toHaveLength(1);

    const grupo = container.querySelector(".pildoras");
    expect(grupo.style.getPropertyValue("--n")).toBe("3");
    expect(grupo.style.getPropertyValue("--i")).toBe("0");

    rerender(<Pildoras opciones={OPCIONES} valor="anio" onCambiar={() => {}} etiqueta="Periodo" />);
    // Solo cambia el índice: el desplazamiento lo calcula CSS con translateX.
    expect(grupo.style.getPropertyValue("--i")).toBe("2");
  });

  it("marca la activa con aria-pressed y avisa solo cuando cambia de verdad", () => {
    const onCambiar = vi.fn();
    render(<Pildoras opciones={OPCIONES} valor="mes" onCambiar={onCambiar} etiqueta="Periodo" />);

    expect(screen.getByRole("button", { name: "Mes" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Hoy" })).toHaveAttribute("aria-pressed", "false");

    // Volver a pulsar la que ya está activa no dispara una petición nueva.
    fireEvent.click(screen.getByRole("button", { name: "Mes" }));
    expect(onCambiar).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Año" }));
    expect(onCambiar).toHaveBeenCalledWith("anio");
  });

  it("con un valor desconocido no deja el indicador en un sitio inválido", () => {
    const { container } = render(
      <Pildoras opciones={OPCIONES} valor="semana" onCambiar={() => {}} etiqueta="Periodo" />
    );
    expect(container.querySelector(".pildoras").style.getPropertyValue("--i")).toBe("0");
  });

  it("el grupo se anuncia con su etiqueta", () => {
    render(<Pildoras opciones={OPCIONES} valor="hoy" onCambiar={() => {}} etiqueta="Rango de la gráfica" />);
    expect(screen.getByRole("group", { name: "Rango de la gráfica" })).toBeInTheDocument();
  });
});
