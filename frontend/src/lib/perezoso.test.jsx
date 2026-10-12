import { Suspense } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { modulo, perezoso } from "@/lib/perezoso";

/**
 * Con `lazy()` a secas la pantalla SIEMPRE suspende la primera vez, aunque su
 * archivo ya esté descargado, y React 19 retiene la revelación hasta ~300 ms.
 * `perezoso()` debe pintar directo lo que ya se precargó (lib/perezoso.js).
 */
function Hola({ nombre }) {
  return <p>hola {nombre}</p>;
}

describe("perezoso: carga diferida con precarga", () => {
  it("si el módulo ya llegó, se pinta en el primer render, sin pasar por el fallback", async () => {
    const mod = modulo(() => Promise.resolve({ Hola }));
    await mod.cargar();
    const Pantalla = perezoso(mod, "Hola");

    render(
      <Suspense fallback={<p>cargando</p>}>
        <Pantalla nombre="mundo" />
      </Suspense>
    );

    expect(screen.getByText("hola mundo")).toBeInTheDocument();
    expect(screen.queryByText("cargando")).toBeNull();
  });

  it("si no ha llegado, se comporta como lazy(): fallback y luego la pantalla", async () => {
    const mod = modulo(() => Promise.resolve({ default: Hola }));
    const Pantalla = perezoso(mod);

    render(
      <Suspense fallback={<p>cargando</p>}>
        <Pantalla nombre="tarde" />
      </Suspense>
    );

    expect(screen.getByText("cargando")).toBeInTheDocument();
    expect(await screen.findByText("hola tarde")).toBeInTheDocument();
  });

  it("varias pantallas del mismo módulo comparten UN solo import()", async () => {
    const importar = vi.fn(() => Promise.resolve({ A: Hola, B: Hola }));
    const mod = modulo(importar);
    perezoso(mod, "A");
    perezoso(mod, "B");
    await Promise.all([mod.cargar(), mod.cargar()]);
    expect(importar).toHaveBeenCalledTimes(1);
  });
});
