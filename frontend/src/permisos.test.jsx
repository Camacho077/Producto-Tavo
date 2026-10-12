import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import ConPermiso, { InicioSegunPermiso } from "@/components/ConPermiso";
import { modulosVisibles, primeraRutaPermitida } from "@/config/modules";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { CategoriasLista } from "@/modules/carta/CategoriasPage";
import { PlatoNuevo } from "@/modules/carta/PlatosPage";
import { RolNuevo } from "@/modules/seguridad/RolesPage";
import { ConSesion } from "@/test/sesion";

/**
 * PERMISOS EN EL FRONTEND — comodidad, no seguridad (el backend responde 403
 * de todos modos, ver backend/tests/test_permisos.py). Lo que se protege aquí
 * es que la interfaz no ofrezca lo que el rol no puede hacer.
 */

// El rol de ejemplo Cajero (backend/app/core/catalogo_permisos.py).
const CAJERO = {
  ventas: ["ver", "crear", "cambiar_estado"],
  ordenes: ["ver", "crear", "editar", "cambiar_estado"],
  productos: ["ver"],
  categorias: ["ver"],
  mesas: ["ver"],
};
const puedeCon = (permisos) => (m, a = "ver") => Boolean(permisos[m]?.includes(a));

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 10, paginas: 1 } });

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockResolvedValue(PAGINA([]));
});

describe("sidebar según el rol", () => {
  it("el Cajero ve Caja y Órdenes, el catálogo y las mesas en solo lectura, y nada de dashboard, compras ni seguridad", () => {
    const modulos = modulosVisibles("pro_ia", [], puedeCon(CAJERO));
    const claves = modulos.map((m) => m.key);
    expect(claves).toEqual(["ordenes", "carta", "ventas", "ajustes"]);
    expect(modulos.find((m) => m.key === "ordenes").hijos.map((h) => h.key)).toEqual(["tomar_pedido", "ordenes", "mesas_servicio"]);
    const carta = modulos.find((m) => m.key === "carta");
    expect(carta.hijos.map((h) => h.key)).toEqual(["productos", "combos", "categorias"]);
    expect(modulos.find((m) => m.key === "ajustes").hijos.map((h) => h.key)).toEqual(["mesas"]);
    expect(carta.path).toBe("/carta");
    expect(primeraRutaPermitida(modulos)).toBe("/ordenes/nueva");
  });

  it("sin `puede` (plan solamente) se ve todo lo del plan", () => {
    expect(modulosVisibles("pro_ia", []).length).toBe(8);
  });
});

describe("rutas bloqueadas", () => {
  it("una ruta sin permiso muestra la causa concreta en vez de la pantalla", () => {
    render(
      <MemoryRouter initialEntries={["/carta/categorias/nuevo"]}>
        <ConSesion permisos={CAJERO}>
          <Routes>
            <Route path="/carta/categorias/nuevo" element={<ConPermiso modulo="categorias" accion="crear"><p>formulario</p></ConPermiso>} />
          </Routes>
        </ConSesion>
      </MemoryRouter>
    );
    expect(screen.queryByText("formulario")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("no tiene permiso para crear categorías");
    expect(screen.getByRole("link", { name: "Ir a una pantalla disponible" })).toHaveAttribute("href", "/ordenes/nueva");
  });

  it("una ruta de un módulo NO contratado muestra el plan, aunque el rol sea administrador", () => {
    render(
      <MemoryRouter initialEntries={["/inventario/insumos"]}>
        <ConSesion tenant={{ plan: "basico", modulos_activos: [], nombre_empresa: "Tienda Básica" }}>
          <Routes>
            <Route path="/inventario/insumos" element={<ConPermiso modulo="insumos"><p>listado</p></ConPermiso>} />
          </Routes>
        </ConSesion>
      </MemoryRouter>
    );
    expect(screen.queryByText("listado")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "El plan Básico de tu empresa no incluye esta pantalla. Está disponible desde el plan Estándar o como módulo adicional"
    );
  });

  it("un add-on contratado (modulos_activos) abre el módulo aunque el plan sea menor", () => {
    render(
      <MemoryRouter>
        <ConSesion tenant={{ plan: "estandar", modulos_activos: ["ia"], nombre_empresa: "Con add-on" }}>
          <ConPermiso modulo="ia">
            <p>sugerencias</p>
          </ConPermiso>
        </ConSesion>
      </MemoryRouter>
    );
    expect(screen.getByText("sugerencias")).toBeInTheDocument();
  });

  it("con el permiso, la pantalla se muestra", () => {
    render(
      <MemoryRouter>
        <ConSesion permisos={CAJERO}>
          <ConPermiso modulo="ventas" accion="crear">
            <p>formulario de venta</p>
          </ConPermiso>
        </ConSesion>
      </MemoryRouter>
    );
    expect(screen.getByText("formulario de venta")).toBeInTheDocument();
  });

  it("quien no ve el dashboard entra directo a su primera pantalla permitida", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <ConSesion permisos={CAJERO}>
          <Routes>
            <Route path="/" element={<InicioSegunPermiso><p>dashboard</p></InicioSegunPermiso>} />
            <Route path="/ordenes/nueva" element={<p>tomar pedido</p>} />
          </Routes>
        </ConSesion>
      </MemoryRouter>
    );
    expect(screen.queryByText("dashboard")).toBeNull();
    expect(screen.getByText("tomar pedido")).toBeInTheDocument();
  });
});

describe("acciones según el rol", () => {
  const categoria = { id: "c1", nombre: "Bebidas", descripcion: null, activo: true, productos_count: 2 };

  function montarCategorias(permisos) {
    api.get.mockResolvedValue(PAGINA([categoria]));
    return render(
      <MemoryRouter initialEntries={["/carta/categorias"]}>
        <ConSesion permisos={permisos}>
          <AvisoProvider>
            <Routes>
              <Route path="/carta/categorias" element={<CategoriasLista />} />
            </Routes>
          </AvisoProvider>
        </ConSesion>
      </MemoryRouter>
    );
  }

  it("solo lectura: ve el listado y el detalle, sin crear, editar, cambiar estado ni eliminar", async () => {
    montarCategorias(CAJERO);
    await screen.findByText("Bebidas");
    expect(screen.getByRole("button", { name: "Ver detalle" })).toBeInTheDocument();
    for (const nombre of [/nueva categoría/i, "Editar", "Desactivar", "Eliminar"]) {
      expect(screen.queryByRole("button", { name: nombre })).toBeNull();
    }
  });

  it("con todos los permisos aparecen todas las acciones", async () => {
    montarCategorias(undefined); // administrador
    await screen.findByText("Bebidas");
    for (const nombre of [/nueva categoría/i, "Editar", "Desactivar", "Eliminar"]) {
      expect(screen.getByRole("button", { name: nombre })).toBeInTheDocument();
    }
  });

  it("el costo del plato no se muestra a quien no ve costos", async () => {
    const sinCompras = { ...CAJERO, productos: ["ver", "crear"], insumos: ["ver"] };
    const { unmount } = render(
      <MemoryRouter>
        <ConSesion permisos={sinCompras}>
          <AvisoProvider>
            <PlatoNuevo />
          </AvisoProvider>
        </ConSesion>
      </MemoryRouter>
    );
    await screen.findByLabelText(/precio de venta/i);
    expect(screen.queryByText(/costo de la porción/i)).toBeNull();
    unmount();

    render(
      <MemoryRouter>
        <ConSesion>
          <AvisoProvider>
            <PlatoNuevo />
          </AvisoProvider>
        </ConSesion>
      </MemoryRouter>
    );
    expect(await screen.findByText(/costo de la porción/i)).toBeInTheDocument();
  });
});

describe("matriz de permisos", () => {
  it("cada módulo muestra solo sus acciones; el resto dice 'No aplica'", async () => {
    api.get.mockImplementation((url) =>
      url === "/seguridad/permisos"
        ? Promise.resolve({
            data: {
              modulos: [
                { clave: "ventas", nombre: "Ventas", acciones: ["ver", "crear", "cambiar_estado", "anular"] },
                { clave: "dashboard", nombre: "Dashboard", acciones: ["ver"] },
              ],
              acciones: [
                { clave: "ver", nombre: "Ver" },
                { clave: "crear", nombre: "Crear" },
                { clave: "editar", nombre: "Editar" },
                { clave: "cambiar_estado", nombre: "Cambiar estado" },
                { clave: "anular", nombre: "Anular" },
                { clave: "eliminar", nombre: "Eliminar" },
              ],
            },
          })
        : Promise.resolve(PAGINA([]))
    );
    render(
      <MemoryRouter>
        <ConSesion>
          <AvisoProvider>
            <RolNuevo />
          </AvisoProvider>
        </ConSesion>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByRole("checkbox", { name: "Ventas: Anular" })).toBeInTheDocument());
    expect(screen.queryByRole("checkbox", { name: "Ventas: Editar" })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Dashboard: Crear" })).toBeNull();
    // Ventas no tiene editar ni eliminar; el dashboard solo tiene ver: 2 + 5.
    expect(screen.getAllByText("No aplica")).toHaveLength(7);
  });
});
