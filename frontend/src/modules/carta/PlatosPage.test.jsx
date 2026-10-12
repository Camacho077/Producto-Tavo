import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));

import { Aviso } from "@/components/ui";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { PlatoDetalle, PlatoNuevo, PlatosLista } from "@/modules/carta/PlatosPage";
import { ConSesion, PERMISOS_ADMIN } from "@/test/sesion";

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 20, paginas: 1 } });
const TECLEO = { delay: null };
const CONFIG = { impuesto_consumo: { aplica: true, tasa: "8.00", incluido_en_precio: true } };
const TENANT = { plan: "pro_ia", modulos_activos: [], nombre_empresa: "Donde Tavo", configuracion: CONFIG };

const QUESO = { id: "i1", nombre: "Queso", unidad: "kg", costo_unitario: "30000", activo: true };
const TOMATE = { id: "i2", nombre: "Tomate", unidad: "kg", costo_unitario: "4000", activo: true };
const PLATO = {
  id: "p1", tipo: "plato", nombre: "Sándwich de queso", precio: "16200.00", activo: true, categoria_id: null, categoria_nombre: "Almuerzos",
  imagen_id: null, va_a_cocina: true, agotado_hoy: false, vigente: true, disponible: true, sku: null, descripcion: null,
  receta: [{ id: "r1", insumo_id: "i1", insumo_nombre: "Queso", insumo_unidad: "kg", cantidad: "100.000", unidad: "g", merma_porcentaje: "10.00", costo: "3300.00" }],
  modificadores: [{ id: "m1", tipo: "extra", nombre: "Queso", precio: "2500.00", insumo_id: "i1", insumo_nombre: "Queso", cantidad: "30.000", unidad: "g", activo: true, costo: "900.00" }],
  componentes: [], tiene_receta: true, costo: "3300.00", precio_neto: "15000.00", margen: "11700.00", porcentaje_costo: "22.00", created_at: "2026-10-12T12:00:00",
};

function montar(ruta, permisos = PERMISOS_ADMIN) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ConSesion permisos={permisos} tenant={TENANT}>
        <AvisoProvider>
          <Aviso />
          <Routes>
            <Route path="/carta" element={<PlatosLista />} />
            <Route path="/carta/nuevo" element={<PlatoNuevo />} />
            <Route path="/carta/:id" element={<PlatoDetalle />} />
          </Routes>
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url.startsWith("/inventario/insumos")) return Promise.resolve(PAGINA([QUESO, TOMATE]));
    if (url.startsWith("/catalogo/categorias")) return Promise.resolve(PAGINA([{ id: "c1", nombre: "Almuerzos" }]));
    if (url === "/catalogo/productos/p1") return Promise.resolve({ data: PLATO });
    if (url.startsWith("/catalogo/productos")) return Promise.resolve(PAGINA([PLATO]));
    return Promise.resolve(PAGINA([]));
  });
});

describe("Plato nuevo — receta con costo en vivo", () => {
  it("calcula el costo con la merma, en g aunque el insumo vaya en kg, y el margen sin impuesto", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/carta/nuevo");
    await usuario.type(screen.getByLabelText(/^Nombre/), "Sándwich de queso");
    await usuario.type(screen.getByLabelText(/^Precio de venta/), "16200");
    await usuario.click(screen.getByRole("button", { name: /Agregar insumo/ }));
    await waitFor(() => expect(screen.getByRole("option", { name: /Queso \(kg\)/ })).toBeInTheDocument());
    await usuario.selectOptions(screen.getByLabelText(/^Insumo/), "i1");
    expect(screen.getAllByLabelText(/^Unidad/)[0]).toHaveValue("g"); // se sugiere g para un insumo en kg
    await usuario.type(screen.getAllByLabelText(/^Cantidad/)[0], "100");
    await usuario.type(screen.getByLabelText(/^Merma/), "10");

    expect(screen.getByText(/Costo de la porción/)).toHaveTextContent("3.300");
    expect(screen.getByText(/% de costo/)).toHaveTextContent("22 %");
    expect(screen.getByText(/% de costo/)).toHaveTextContent("11.700");

    api.post.mockResolvedValue({ data: { id: "p9" } });
    await usuario.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, cuerpo] = api.post.mock.calls[0];
    expect(url).toBe("/catalogo/productos");
    expect(cuerpo).toMatchObject({
      tipo: "plato",
      nombre: "Sándwich de queso",
      precio: "16200",
      va_a_cocina: true,
      receta: [{ insumo_id: "i1", cantidad: "100", unidad: "g", merma_porcentaje: "10" }],
      modificadores: [],
    });
  });

  it("un «sin» no tiene precio y un «extra» con insumo exige la cantidad", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/carta/nuevo");
    await usuario.type(screen.getByLabelText(/^Nombre/), "Hamburguesa");
    await usuario.type(screen.getByLabelText(/^Precio de venta/), "15000");
    await usuario.click(screen.getByRole("button", { name: /Agregar modificador/ }));
    const tipo = await screen.findByLabelText(/^Tipo/);
    await usuario.type(screen.getAllByLabelText(/^Nombre/)[1], "Queso");
    await usuario.selectOptions(screen.getAllByLabelText(/^Insumo/)[0], "i1");
    await usuario.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Indica cuánto lleva el extra")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();

    await usuario.selectOptions(tipo, "sin");
    expect(screen.getAllByLabelText(/^Precio/)[1]).toBeDisabled();
  });

  it("quien no ve costos arma la receta pero no ve el costo", async () => {
    const usuario = userEvent.setup(TECLEO);
    const { costos: _sinCostos, ...sinCostos } = PERMISOS_ADMIN;
    montar("/carta/nuevo", sinCostos);
    await usuario.click(screen.getByRole("button", { name: /Agregar insumo/ }));
    await waitFor(() => expect(screen.getByRole("option", { name: /Queso \(kg\)/ })).toBeInTheDocument());
    expect(screen.queryByText(/Costo de la porción/)).toBeNull();
  });
});

describe("Carta — listado y detalle", () => {
  it("el listado muestra costo, % de costo y margen solo a quien ve costos", async () => {
    montar("/carta");
    expect(await screen.findByRole("link", { name: "Sándwich de queso" })).toHaveAttribute("href", "/carta/p1");
    expect(screen.getByText("22 %")).toBeInTheDocument();
    expect(screen.getByText("Disponible")).toBeInTheDocument();
  });

  it("sin permiso de costos el listado no trae esas columnas", async () => {
    montar("/carta", { productos: ["ver"], categorias: ["ver"] });
    await screen.findByRole("link", { name: "Sándwich de queso" });
    expect(screen.queryByRole("columnheader", { name: /% costo/i })).toBeNull();
  });

  it("el detalle muestra la receta, el modificador como sale en la comanda y marca agotado hoy con confirmación", async () => {
    api.patch.mockResolvedValue({ data: { ...PLATO, agotado_hoy: true } });
    montar("/carta/p1");
    expect(await screen.findByRole("heading", { level: 1, name: "Sándwich de queso" })).toBeInTheDocument();
    expect(screen.getByText("EXTRA QUESO")).toBeInTheDocument();
    expect(screen.getByText("Suma 30 g de Queso")).toBeInTheDocument();
    expect(screen.getByText("100 g")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Agotado hoy/ }));
    const dialogo = await screen.findByRole("dialog");
    expect(dialogo).toHaveTextContent("Mañana vuelve solo");
    fireEvent.click(within(dialogo).getByRole("button", { name: "Marcar agotado" }));
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/catalogo/productos/p1/agotado", { agotado: true }));
  });
});
