import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SkeletonTabla } from "@/components/ui/Skeleton";

const COLUMNAS = [
  { clave: "nombre", titulo: "Nombre" },
  { clave: "precio", titulo: "Precio", cifra: true },
  { clave: "acciones", titulo: "Acciones" },
];

describe("SkeletonTabla — misma forma que la tabla real", () => {
  it("es la MISMA tabla (<table class=tabla>) con los mismos títulos y clases por columna", () => {
    // Antes era una rejilla de divs: 39 px por fila contra 46,7 px de la
    // fila real, y la tabla saltaba al llegar los datos.
    const { container } = render(<SkeletonTabla columnas={COLUMNAS} filas={3} />);
    expect(screen.getByRole("status", { name: "Cargando registros" })).toBeInTheDocument();

    const tabla = container.querySelector("table.tabla");
    expect(tabla).not.toBeNull();
    const titulos = [...tabla.querySelectorAll("thead th")].map((th) => th.textContent);
    expect(titulos).toEqual(["Nombre", "Precio", "Acciones"]);
    expect(tabla.querySelectorAll("thead th")[1]).toHaveClass("celda--cifra", "celda--ajustada");
    expect(tabla.querySelectorAll("tbody tr")).toHaveLength(3);
  });

  it("la columna de acciones lleva un marcador del alto de sus botones (fija el alto de la fila)", () => {
    const { container } = render(<SkeletonTabla columnas={COLUMNAS} filas={1} />);
    const celdaAcciones = container.querySelectorAll("tbody td")[2];
    expect(celdaAcciones.querySelector(".skeleton").style.height).toBe("30px");
  });

  it("sigue aceptando un número de columnas para usos sueltos", () => {
    const { container } = render(<SkeletonTabla columnas={4} filas={2} />);
    expect(container.querySelectorAll("thead th")).toHaveLength(4);
  });
});
