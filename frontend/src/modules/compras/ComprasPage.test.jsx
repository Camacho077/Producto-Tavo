import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { CompraNueva, ComprasLista } from "@/modules/compras/ComprasPage";
import { ProductoDetalle, ProductoNuevo } from "@/modules/compras/ProductosPage";
import { ConSesion } from "@/test/sesion";

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 10, paginas: 1 } });

const MARTILLO = { id: "p1", nombre: "Martillo", sku: "MAR-1", stock: 3, stock_minimo: 0, precio: "1000", precio_compra: "800", activo: true };
const TALADRO = { id: "p2", nombre: "Taladro", sku: "TAL-1", stock: 0, stock_minimo: 0, precio: "5000", precio_compra: null, activo: true };
const PROVEEDOR = { id: "prov1", nombre: "Distribuidora Andina", nit: "890903938-8", activo: true, productos: [{ id: "p1", nombre: "Martillo", sku: "MAR-1", stock: 3 }] };

// Sin pausa entre teclas: con el `delay: 0` por defecto, user-event cede un
// setTimeout en cada tecla y bajo la carga de la suite en paralelo esas esperas
// se acumulan hasta el timeout de 5 s.
const TECLEO = { delay: null };

/**
 * Abre un SelectorBusqueda (se abre con el foco, igual que al hacer clic) y
 * deja correr su retardo de búsqueda de 250 ms con relojes falsos en vez de
 * esperarlo de verdad. Dentro de la ventana de relojes falsos no se usa
 * user-event ni waitFor/findBy: Testing Library no reconoce los relojes de
 * Vitest y su `setTimeout(0)` de cierre nunca dispararía (se cuelga). Por eso
 * solo se falsea `setTimeout` y los relojes reales vuelven enseguida.
 */
async function abrirSelector(campo) {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    act(() => campo.focus());
    await act(() => vi.runOnlyPendingTimersAsync());
  } finally {
    vi.useRealTimers();
  }
}

function montar(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}><ConSesion>
      <AvisoProvider>
        <Routes>
          <Route path="/compras" element={<ComprasLista />} />
          <Route path="/compras/nuevo" element={<CompraNueva />} />
          <Route path="/compras/productos/nuevo" element={<ProductoNuevo />} />
          <Route path="/compras/productos/:id" element={<ProductoDetalle />} />
        </Routes>
      </AvisoProvider>
    </ConSesion></MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url.startsWith("/compras/proveedores")) return Promise.resolve(PAGINA([PROVEEDOR]));
    if (url.startsWith("/compras/productos?")) {
      const soloDelProveedor = url.includes("proveedor_id=prov1");
      return Promise.resolve(PAGINA(soloDelProveedor ? [MARTILLO] : [MARTILLO, TALADRO]));
    }
    return Promise.resolve(PAGINA([]));
  });
});

describe("Registrar compra — proveedor primero, productos filtrados", () => {
  it("el selector de productos queda limitado a los que surte el proveedor, con opción de ver todos", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/compras/nuevo");
    expect(screen.getByRole("heading", { level: 1, name: "Registrar compra" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();

    // Sin proveedor, todavía no se pide el listado filtrado.
    await abrirSelector(screen.getByRole("combobox", { name: "Proveedor" }));
    await usuario.click(screen.getByRole("option", { name: /Distribuidora Andina/ }));

    // Solo el producto que surte.
    const selectProducto = screen.getByLabelText(/^Producto/);
    await waitFor(() => expect(screen.getByRole("option", { name: /Martillo/ })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: /Taladro/ })).toBeNull();
    expect(screen.getByText(/Se muestran solo los 1 producto\(s\) que surte/)).toBeInTheDocument();

    // "Mostrar todos" amplía el listado.
    await usuario.click(screen.getByLabelText(/Mostrar todos los productos/));
    await waitFor(() => expect(screen.getByRole("option", { name: /Taladro/ })).toBeInTheDocument());

    // Al elegir producto se sugiere el costo de compra y el total se calcula en vivo.
    await usuario.selectOptions(selectProducto, "p1");
    expect(screen.getByLabelText(/Costo unitario/)).toHaveValue("800");
    await usuario.clear(screen.getByLabelText(/Cantidad/));
    await usuario.type(screen.getByLabelText(/Cantidad/), "12");
    expect(screen.getByText(/Total:/)).toHaveTextContent("9.600");

    api.post.mockResolvedValue({ data: { id: "c1" } });
    await usuario.click(screen.getByRole("button", { name: /Registrar compra ·/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, cuerpo] = api.post.mock.calls[0];
    expect(url).toBe("/compras/compras");
    expect(cuerpo.proveedor_id).toBe("prov1");
    expect(cuerpo.confirmar).toBe(true);
    expect(cuerpo.items).toEqual([{ producto_id: "p1", cantidad: 12, precio_unitario: "800" }]);
    expect(await screen.findByRole("heading", { level: 1, name: "Compras" })).toBeInTheDocument();
  });

  it("sin proveedor no deja enviar: muestra el mensaje y no llama al backend", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/compras/nuevo");
    await usuario.click(screen.getByRole("button", { name: /Registrar compra ·/ }));
    expect(await screen.findByText("Selecciona un proveedor")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("Producto — stock solo por movimientos", () => {
  it("el formulario de crear no tiene campo de stock editable y envía sin stock_inicial", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "p9" } });
    montar("/compras/productos/nuevo");

    expect(screen.queryByLabelText(/Stock inicial/)).toBeNull();
    expect(screen.getByLabelText(/Stock actual/)).toBeDisabled();

    await usuario.type(screen.getByLabelText(/^Nombre/), "Martillo");
    await usuario.type(screen.getByLabelText(/^SKU/), "MAR-1");
    await usuario.type(screen.getByLabelText(/Precio de venta/), "1000");
    await usuario.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const cuerpo = api.post.mock.calls[0][1];
    expect(cuerpo).not.toHaveProperty("stock_inicial");
    expect(cuerpo).not.toHaveProperty("stock");
  });

  it("el detalle muestra el stock, los proveedores y el historial de movimientos", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/compras/productos/p1") {
        return Promise.resolve({ data: { ...MARTILLO, stock: 12, proveedores: [{ id: "prov1", nombre: "Distribuidora Andina" }], created_at: "2026-01-01T00:00:00Z" } });
      }
      if (url === "/compras/productos/p1/movimientos") {
        return Promise.resolve(
          PAGINA([
            { id: "m2", tipo: "anulacion_compra", cantidad: -12, stock_resultante: 0, documento_tipo: "compra", documento_id: "c1", documento_codigo: "OC-000001", usuario_nombre: "Ana", created_at: "2026-02-01T10:00:00Z" },
            { id: "m1", tipo: "compra", cantidad: 12, stock_resultante: 12, documento_tipo: "compra", documento_id: "c1", documento_codigo: "OC-000001", usuario_nombre: "Ana", created_at: "2026-02-01T09:00:00Z" },
          ])
        );
      }
      return Promise.resolve(PAGINA([]));
    });
    montar("/compras/productos/p1");

    expect(await screen.findByRole("heading", { level: 1, name: "Martillo" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Distribuidora Andina" })).toHaveAttribute("href", "/compras/proveedores/prov1");
    expect(await screen.findByText("Anulación de compra")).toBeInTheDocument();
    expect(screen.getByText("+12")).toBeInTheDocument();
    expect(screen.getByText("-12")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "OC-000001" })[0]).toHaveAttribute("href", "/compras/c1");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
