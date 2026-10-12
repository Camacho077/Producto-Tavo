import { StrictMode } from "react";
import { act, render } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AppLayout from "@/components/AppLayout";
import { AvisoProvider } from "@/context/AvisoContext";
import { ConSesion } from "@/test/sesion";
import { ThemeProvider } from "@/theme/ThemeContext";

/**
 * SALIDA DE VISTA bajo StrictMode.
 *
 * En desarrollo, StrictMode suelta y vuelve a enganchar los refs al montar.
 * La salida animada se dispara en la limpieza del ref, así que antes cada
 * montaje creaba un clon de la MISMA pantalla que se desvanecía encima de
 * ella: doble exposición en cada carga. El clon solo debe aparecer cuando la
 * pantalla se va de verdad.
 */
let animarOriginal;

beforeEach(() => {
  // jsdom no trae WAAPI: sin `animate` no hay salida animada (así lo quiere
  // el producto). Aquí se simula para poder observar el clon.
  animarOriginal = HTMLElement.prototype.animate;
  HTMLElement.prototype.animate = vi.fn(() => ({ onfinish: null, oncancel: null }));
});

afterEach(() => {
  HTMLElement.prototype.animate = animarOriginal;
});

function Ir({ a }) {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(a)}>
      ir
    </button>
  );
}

function montar() {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={["/uno"]}>
        <ThemeProvider>
        <ConSesion>
          <AvisoProvider>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/uno" element={<p>pantalla uno <Ir a="/dos" /></p>} />
                <Route path="/dos" element={<p>pantalla dos</p>} />
              </Route>
            </Routes>
          </AvisoProvider>
        </ConSesion>
        </ThemeProvider>
      </MemoryRouter>
    </StrictMode>
  );
}

describe("salida de vista", () => {
  it("al montar (StrictMode) NO crea un clon de la pantalla que se queda", async () => {
    const { container } = montar();
    await act(async () => {}); // deja correr la microtarea que decide
    expect(container.ownerDocument.querySelectorAll(".vista-fantasma")).toHaveLength(0);
    expect(container.ownerDocument.querySelectorAll(".vista")).toHaveLength(1);
  });

  it("al cambiar de pantalla SÍ sale la anterior, una sola vez y con su contenido", async () => {
    const { getByRole, container } = montar();
    await act(async () => {});
    await act(async () => {
      getByRole("button", { name: "ir" }).click();
    });
    const doc = container.ownerDocument;
    const fantasmas = doc.querySelectorAll(".vista-fantasma");
    expect(fantasmas).toHaveLength(1);
    expect(fantasmas[0]).toHaveTextContent("pantalla uno");
    expect(fantasmas[0]).toHaveAttribute("aria-hidden", "true");
    expect(doc.querySelector(".vista")).toHaveTextContent("pantalla dos");
  });
});
