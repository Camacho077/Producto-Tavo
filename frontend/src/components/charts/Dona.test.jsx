import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Dona from "@/components/charts/Dona";
import { MAX_PARTES, agruparPartes } from "@/components/charts/partes";

describe("Dona de participación", () => {
  it("nunca más de 6 partes: desde la sexta se suman en «Otros»", () => {
    const partes = Array.from({ length: 9 }, (_, i) => ({ nombre: `P${i}`, valor: 100 - i }));
    const agrupadas = agruparPartes(partes);
    expect(agrupadas).toHaveLength(MAX_PARTES);
    expect(agrupadas.at(-1)).toEqual({ nombre: "Otros", valor: 95 + 94 + 93 + 92 });
    expect(agruparPartes([{ nombre: "Cero", valor: 0 }])).toEqual([]);
  });

  it("dibuja un arco por parte con su leyenda, y un anillo completo si hay una sola", () => {
    const { container } = render(<Dona titulo="Medios" partes={[{ nombre: "Efectivo", valor: 1 }]} formato={String} />);
    expect(container.querySelectorAll("path")).toHaveLength(1);
    expect(container.querySelector("path").getAttribute("d")).toMatch(/A46 46 .* A46 46 /);
    expect(screen.getByRole("img")).toHaveAccessibleName("Medios: Efectivo 100 %");
  });
});
