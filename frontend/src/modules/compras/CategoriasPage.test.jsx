import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { Aviso } from "@/components/ui";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { CategoriaDetalle, CategoriaEditar, CategoriaNueva, CategoriasLista } from "@/modules/compras/CategoriasPage";
import { ConSesion } from "@/test/sesion";

const PAGINA = (items, extra = {}) => ({
  data: { items, total: items.length, pagina: 1, por_pagina: 10, paginas: 1, ...extra },
});

/** Monta las cuatro pantallas con sus rutas reales, como en App.jsx. */
function montar(rutaInicial) {
  return render(
    <MemoryRouter initialEntries={[rutaInicial]}><ConSesion>
      <AvisoProvider>
        <Aviso />
        <Routes>
          <Route path="/compras/categorias" element={<CategoriasLista />} />
          <Route path="/compras/categorias/nuevo" element={<CategoriaNueva />} />
          <Route path="/compras/categorias/:id" element={<CategoriaDetalle />} />
          <Route path="/compras/categorias/:id/editar" element={<CategoriaEditar />} />
        </Routes>
      </AvisoProvider>
    </ConSesion></MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Categorías — listado", () => {
  it("muestra el marcador de carga y nunca el estado vacío antes de la primera respuesta", async () => {
    let resolver;
    api.get.mockReturnValue(new Promise((r) => (resolver = r)));
    montar("/compras/categorias");

    expect(screen.getByRole("status", { name: "Cargando registros" })).toBeInTheDocument();
    expect(screen.queryByText("Todavía no hay categorías registradas.")).toBeNull();

    resolver(PAGINA([]));
    expect(await screen.findByText("Todavía no hay categorías registradas.")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Cargando registros" })).toBeNull();
  });

  it("lista los registros del backend con su conteo de productos", async () => {
    api.get.mockResolvedValue(PAGINA([{ id: "1", nombre: "Bebidas", descripcion: "Frías", activo: true, productos_count: 3 }]));
    montar("/compras/categorias");
    expect(await screen.findByText("Bebidas")).toBeInTheDocument();
    expect(screen.getByText("Frías")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
  });

  it("conserva las filas actuales mientras recarga (sin volver al marcador de carga)", async () => {
    api.get.mockResolvedValueOnce(PAGINA([{ id: "1", nombre: "Bebidas", activo: true, productos_count: 0 }]));
    montar("/compras/categorias");
    await screen.findByText("Bebidas");

    let resolver;
    api.get.mockReturnValueOnce(new Promise((r) => (resolver = r)));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "beb" } });
    await waitFor(() => expect(api.get.mock.calls.at(-1)[1].params.q).toBe("beb"));

    // Mientras llega la respuesta, la fila sigue ahí y no hay skeleton.
    expect(screen.getByText("Bebidas")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Cargando registros" })).toBeNull();
    resolver(PAGINA([{ id: "1", nombre: "Bebidas", activo: true, productos_count: 0 }]));
    await waitFor(() => expect(screen.getByRole("table").closest("[aria-busy]")).toHaveAttribute("aria-busy", "false"));
  });

  it("muestra un error visible en vez de fallar en silencio", async () => {
    api.get.mockRejectedValue({ response: { data: { detail: "No se pudo conectar" } } });
    montar("/compras/categorias");
    expect(await screen.findByText("No se pudo conectar")).toBeInTheDocument();
  });

  it("no abre ningún diálogo para crear: navega a la pantalla /nuevo con migas", async () => {
    api.get.mockResolvedValue(PAGINA([]));
    montar("/compras/categorias");
    await screen.findByText("Todavía no hay categorías registradas.");

    fireEvent.click(screen.getByRole("button", { name: /nueva categoría/i }));
    expect(await screen.findByRole("heading", { level: 1, name: "Nueva categoría" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
    const migas = screen.getByRole("navigation", { name: "Ruta de navegación" });
    expect(migas).toHaveTextContent("Compras");
    expect(migas).toHaveTextContent("Categorías");
    expect(migas).toHaveTextContent("Nueva categoría");
  });

  it("cambiar de estado sí sigue siendo un diálogo de confirmación", async () => {
    api.get.mockResolvedValue(PAGINA([{ id: "1", nombre: "Bebidas", activo: true, productos_count: 0 }]));
    api.patch.mockResolvedValue({ data: {} });
    montar("/compras/categorias");
    await screen.findByText("Bebidas");
    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));
    const dialogo = await screen.findByRole("dialog");
    expect(dialogo).toHaveTextContent("Desactivar categoría");
  });
});

describe("Categorías — crear", () => {
  it("guarda, vuelve al listado y muestra el aviso de confirmación", async () => {
    const usuario = userEvent.setup();
    api.get.mockResolvedValue(PAGINA([]));
    api.post.mockResolvedValue({ data: { id: "9" } });
    montar("/compras/categorias/nuevo");

    const nombre = screen.getByLabelText(/^Nombre/);
    await usuario.click(nombre);
    await usuario.keyboard("Pinturas y acabados para exterior");
    expect(nombre).toHaveFocus();
    expect(nombre).toHaveValue("Pinturas y acabados para exterior");

    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/compras/categorias", { nombre: "Pinturas y acabados para exterior", descripcion: null });
    });
    expect(await screen.findByRole("heading", { level: 1, name: "Categorías" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Categoría creada");
  });

  it("Cancelar vuelve al listado sin llamar al backend", async () => {
    api.get.mockResolvedValue(PAGINA([]));
    montar("/compras/categorias/nuevo");
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Categorías" })).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("Categorías — detalle y editar", () => {
  const REGISTRO = { id: "1", nombre: "Bebidas", descripcion: "Frías", activo: true, productos_count: 3, created_at: "2026-01-01T00:00:00Z" };

  it("el detalle muestra el marcador de carga hasta que llega el registro, sin diálogos", async () => {
    let resolver;
    api.get.mockReturnValue(new Promise((r) => (resolver = r)));
    montar("/compras/categorias/1");
    expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();

    resolver({ data: REGISTRO });
    expect(await screen.findByRole("heading", { level: 1, name: "Bebidas" })).toBeInTheDocument();
    expect(screen.getByText("Frías")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.get).toHaveBeenCalledWith("/compras/categorias/1");
  });

  it("editar precarga el formulario en una pantalla propia y envía PUT", async () => {
    api.get.mockResolvedValue({ data: REGISTRO });
    api.put.mockResolvedValue({ data: REGISTRO });
    montar("/compras/categorias/1/editar");

    const nombre = await screen.findByLabelText(/^Nombre/);
    await waitFor(() => expect(nombre).toHaveValue("Bebidas"));
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.change(nombre, { target: { value: "Bebidas frías" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/compras/categorias/1", { nombre: "Bebidas frías", descripcion: "Frías" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Bebidas" })).toBeInTheDocument();
  });
});

describe("Categorías — exportar a CSV", () => {
  it("descarga con la búsqueda y el filtro activos, como CSV de todas las filas", async () => {
    const crearUrl = vi.fn(() => "blob:csv");
    globalThis.URL.createObjectURL = crearUrl;
    globalThis.URL.revokeObjectURL = vi.fn();
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    api.get.mockImplementation((_url, config) =>
      Promise.resolve(config?.responseType === "blob" ? { data: new Blob(["﻿Nombre\r\n"]) } : PAGINA([{ id: "1", nombre: "Bebidas", activo: true, productos_count: 0 }]))
    );
    montar("/compras/categorias");
    await screen.findByText("Bebidas");
    await userEvent.type(screen.getByRole("searchbox"), "beb");
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/compras/categorias", expect.objectContaining({ params: expect.objectContaining({ q: "beb" }) })));

    await userEvent.click(screen.getByRole("button", { name: /Exportar CSV/ }));

    await waitFor(() => expect(clic).toHaveBeenCalled());
    expect(api.get).toHaveBeenLastCalledWith("/compras/categorias", {
      params: { q: "beb", formato: "csv" },
      responseType: "blob",
    });
    expect(crearUrl).toHaveBeenCalled();
    clic.mockRestore();
  });

  it("si el backend rechaza la exportación, la alerta dice su causa (aunque llegue como archivo)", async () => {
    api.get.mockImplementation((_url, config) =>
      config?.responseType === "blob"
        ? Promise.reject({ response: { status: 413, data: new Blob([JSON.stringify({ detail: "La exportación tendría 60.000 filas y el máximo es 50.000." })]) } })
        : Promise.resolve(PAGINA([{ id: "1", nombre: "Bebidas", activo: true, productos_count: 0 }]))
    );
    montar("/compras/categorias");
    await screen.findByText("Bebidas");
    await userEvent.click(screen.getByRole("button", { name: /Exportar CSV/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La exportación tendría 60.000 filas y el máximo es 50.000.");
  });
});
