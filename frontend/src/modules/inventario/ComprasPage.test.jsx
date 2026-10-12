import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));

import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { CompraNueva, ComprasLista } from "@/modules/inventario/ComprasPage";
import { InsumoDetalle, InsumoEditar, InsumoNuevo } from "@/modules/inventario/InsumosPage";
import { ConSesion } from "@/test/sesion";

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 10, paginas: 1 } });

const QUESO = { id: "i1", nombre: "Queso", unidad: "g", grupo: "Lácteos", existencia: "300", minimo: "500", costo_unitario: "30", costo_total: "9000", bajo_minimo: true, activo: true, platos_count: 2 };
const ARROZ = { id: "i2", nombre: "Arroz", unidad: "kg", grupo: "Abarrotes", existencia: "0", minimo: "0", costo_unitario: "4000", costo_total: "0", bajo_minimo: false, activo: true, platos_count: 0 };
const PROVEEDOR = { id: "prov1", nombre: "Distribuidora Andina", nit: "890903938-8", activo: true, insumos: [{ id: "i1", nombre: "Queso", unidad: "g", existencia: "300" }] };

const TECLEO = { delay: null };

/** Abre un SelectorBusqueda dejando correr su retardo de 250 ms con relojes falsos (ver la prueba heredada). */
async function abrirSelector(campo) {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    act(() => campo.focus());
    await act(() => vi.runOnlyPendingTimersAsync());
  } finally {
    vi.useRealTimers();
  }
}

function montar(ruta, permisos) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ConSesion permisos={permisos}>
        <AvisoProvider>
          <Routes>
            <Route path="/inventario/compras" element={<ComprasLista />} />
            <Route path="/inventario/compras/nuevo" element={<CompraNueva />} />
            <Route path="/inventario/insumos" element={<p>listado de insumos</p>} />
            <Route path="/inventario/insumos/nuevo" element={<InsumoNuevo />} />
            <Route path="/inventario/insumos/:id" element={<InsumoDetalle />} />
            <Route path="/inventario/insumos/:id/editar" element={<InsumoEditar />} />
          </Routes>
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url.startsWith("/compras/proveedores")) return Promise.resolve(PAGINA([PROVEEDOR]));
    if (url.startsWith("/inventario/insumos?")) {
      return Promise.resolve(PAGINA(url.includes("proveedor_id=prov1") ? [QUESO] : [QUESO, ARROZ]));
    }
    if (url === "/inventario/grupos") return Promise.resolve({ data: ["Abarrotes", "Lácteos"] });
    return Promise.resolve(PAGINA([]));
  });
});

describe("Registrar compra de insumos — proveedor primero", () => {
  it("ofrece solo lo que surte el proveedor, deja comprar en kg lo que se lleva en g y calcula el total en vivo", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/inventario/compras/nuevo");
    expect(screen.getByRole("heading", { level: 1, name: "Registrar compra" })).toBeInTheDocument();

    await abrirSelector(screen.getByRole("combobox", { name: "Proveedor" }));
    await usuario.click(screen.getByRole("option", { name: /Distribuidora Andina/ }));

    const insumo = screen.getByLabelText(/^Insumo/);
    await waitFor(() => expect(screen.getByRole("option", { name: /Queso/ })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: /Arroz/ })).toBeNull();
    expect(screen.getByText(/Se muestran solo los 1 insumo\(s\) que surte/)).toBeInTheDocument();

    await usuario.click(screen.getByLabelText(/Mostrar todos los insumos/));
    await waitFor(() => expect(screen.getByRole("option", { name: /Arroz/ })).toBeInTheDocument());

    await usuario.selectOptions(insumo, "i1");
    const unidad = screen.getByLabelText(/^Unidad/);
    expect(unidad).toHaveValue("g");
    // Solo unidades de la misma familia (peso): g y kg, nunca L ni unidades.
    expect([...unidad.querySelectorAll("option")].map((o) => o.value)).toEqual(["", "kg", "g"]);
    await usuario.selectOptions(unidad, "kg");
    await usuario.type(screen.getByLabelText(/^Cantidad/), "2.5");
    await usuario.type(screen.getByLabelText(/^Precio por unidad/), "30000");
    expect(screen.getByText(/Total:/)).toHaveTextContent("75.000");

    api.post.mockResolvedValue({ data: { id: "c1" } });
    await usuario.click(screen.getByRole("button", { name: /Registrar compra ·/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, cuerpo] = api.post.mock.calls[0];
    expect(url).toBe("/compras/compras");
    expect(cuerpo.proveedor_id).toBe("prov1");
    expect(cuerpo.items).toEqual([{ insumo_id: "i1", cantidad: "2.5", unidad: "kg", precio_unitario: "30000" }]);
    expect(await screen.findByRole("heading", { level: 1, name: "Compras" })).toBeInTheDocument();
  });

  it("sin proveedor no deja enviar", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/inventario/compras/nuevo");
    await usuario.click(screen.getByRole("button", { name: /Registrar compra ·/ }));
    expect(await screen.findByText("Selecciona un proveedor")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("Insumos — la existencia solo cambia con movimientos", () => {
  it("al crear se pide la existencia inicial, que no vuelve a aparecer al editar", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "nuevo" } });
    montar("/inventario/insumos/nuevo");
    await usuario.type(screen.getByLabelText(/^Nombre/), "Pechuga de pollo");
    await usuario.selectOptions(screen.getByLabelText(/^Unidad/), "kg");
    await usuario.clear(screen.getByLabelText(/^Existencia inicial/));
    await usuario.type(screen.getByLabelText(/^Existencia inicial/), "12.5");
    await usuario.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(api.post.mock.calls[0][1]).toMatchObject({ nombre: "Pechuga de pollo", unidad: "kg", existencia_inicial: "12.5" });
    expect(await screen.findByText("listado de insumos")).toBeInTheDocument();
  });

  it("la cantidad no admite letras ni signo menos al teclear", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/inventario/insumos/nuevo");
    const minimo = screen.getByLabelText(/^Mínimo/);
    await usuario.clear(minimo);
    await usuario.type(minimo, "-1a,5");
    expect(minimo).toHaveValue("1.5");
  });

  it("el editor no trae la existencia y quien no ve costos no ve el costo", async () => {
    api.get.mockImplementation((url) => (url === "/inventario/insumos/i1" ? Promise.resolve({ data: QUESO }) : Promise.resolve({ data: [] })));
    montar("/inventario/insumos/i1/editar", { insumos: ["ver", "editar"] });
    const nombre = await screen.findByLabelText(/^Nombre/);
    await waitFor(() => expect(nombre).toHaveValue("Queso"));
    expect(screen.queryByLabelText(/Existencia/)).toBeNull();
    expect(screen.queryByLabelText(/Costo unitario/)).toBeNull();
  });

  it("el detalle muestra la existencia, el aviso de mínimo y el historial con su documento", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/inventario/insumos/i1") return Promise.resolve({ data: { ...QUESO, proveedores: [{ id: "prov1", nombre: "Distribuidora Andina" }], created_at: "2026-01-01T00:00:00Z" } });
      if (url.startsWith("/catalogo/productos")) {
        return Promise.resolve(PAGINA([{ id: "pl1", nombre: "Hamburguesa", porcentaje_costo: "35.2", receta: [{ insumo_id: "i1", cantidad: "30", unidad: "g" }] }]));
      }
      if (url === "/inventario/insumos/i1/movimientos") {
        return Promise.resolve(
          PAGINA([
            { id: "m2", tipo: "venta", cantidad: "-300", existencia_resultante: "300", valor: "-9000", documento_tipo: "venta", documento_id: "v1", documento_codigo: "VEN-000001", usuario_nombre: "Ana", created_at: "2026-02-01T10:00:00Z" },
            { id: "m1", tipo: "compra", cantidad: "600", existencia_resultante: "600", valor: "18000", documento_tipo: "compra", documento_id: "c1", documento_codigo: "COM-000001", usuario_nombre: "Ana", created_at: "2026-02-01T09:00:00Z" },
          ])
        );
      }
      return Promise.resolve(PAGINA([]));
    });
    montar("/inventario/insumos/i1");
    expect(await screen.findByRole("heading", { level: 1, name: "Queso" })).toBeInTheDocument();
    expect(screen.getByText(/Bajo el mínimo de 500 g/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "COM-000001" })).toHaveAttribute("href", "/inventario/compras/c1");
    expect(screen.getByText("−300 g")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Hamburguesa" })).toHaveAttribute("href", "/carta/pl1");
    expect(screen.getByRole("link", { name: "Distribuidora Andina" })).toHaveAttribute("href", "/inventario/proveedores/prov1");
    fireEvent.click(screen.getByRole("button", { name: /Eliminar/ }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("desactívalo en su lugar");
  });
});
