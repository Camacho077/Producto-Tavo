import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(() => Promise.resolve({ data: { avisos: [], todo_en_orden: true } })), post: vi.fn(), defaults: { baseURL: "http://api" } },
}));

import AppLayout from "@/components/AppLayout";
import { InicioSegunPermiso } from "@/components/ConPermiso";
import { ThemeProvider } from "@/theme/ThemeContext";
import { AvisoProvider } from "@/context/AvisoContext";
import { ConSesion } from "@/test/sesion";

function montar(permisos, ruta = "/") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ThemeProvider>
        <ConSesion permisos={permisos} usuario={{ id: "u", nombre_completo: "Carlos Cocina", rol_nombre: "Cocinero" }}>
          <AvisoProvider>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<InicioSegunPermiso><p>dashboard</p></InicioSegunPermiso>} />
                <Route path="/cocina" element={<p>pantalla de cocina</p>} />
                <Route path="/ordenes/nueva" element={<p>tomar pedido</p>} />
                <Route path="/caja" element={<p>caja</p>} />
              </Route>
            </Routes>
          </AvisoProvider>
        </ConSesion>
      </ThemeProvider>
    </MemoryRouter>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("vistas por rol (fase 7)", () => {
  it("el cocinero entra directo a la cocina, en modo enfocado: sin menú lateral ni barra inferior", () => {
    const { container } = montar({ cocina: ["ver", "cambiar_estado"] });
    expect(screen.getByText("pantalla de cocina")).toBeInTheDocument();
    expect(container.querySelector(".shell--enfocado")).not.toBeNull();
    expect(container.querySelector(".sidebar")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Navegación rápida" })).toBeNull();
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  });

  it("el mesero entra a tomar pedido y su barra inferior empieza por ahí", () => {
    montar({ ordenes: ["ver", "crear", "editar", "cambiar_estado"] });
    expect(screen.getByText("tomar pedido")).toBeInTheDocument();
    const barra = screen.getByRole("navigation", { name: "Navegación rápida" });
    const enlaces = [...barra.querySelectorAll("a")].map((a) => a.textContent);
    expect(enlaces).toEqual(["Tomar pedido", "Tablero", "Mesas"]);
  });

  it("el cajero entra a la caja", () => {
    montar({ ventas: ["ver", "crear"], caja: ["ver", "cambiar_estado"], ordenes: ["ver", "crear"] });
    expect(screen.getByText("caja")).toBeInTheDocument();
  });

  it("sin red aparece el aviso de sin conexión, y se va al volver", () => {
    montar({ cocina: ["ver"] }, "/cocina");
    expect(screen.queryByText(/Sin conexión/)).toBeNull();
    act(() => window.dispatchEvent(new Event("offline")));
    expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Sin conexión.");
    act(() => window.dispatchEvent(new Event("online")));
    expect(screen.queryByText(/Sin conexión/)).toBeNull();
  });
});
