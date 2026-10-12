import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));
vi.mock("@/lib/impresion", async (original) => ({ ...(await original()), imprimir: vi.fn(() => Promise.resolve()) }));

import { Aviso } from "@/components/ui";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { imprimir } from "@/lib/impresion";
import { MesasServicio, OrdenDetalle, OrdenesLista } from "@/modules/ordenes/OrdenesPage";
import { OrdenNueva } from "@/modules/ordenes/TomarPedidoPage";
import { ConSesion, PERMISOS_ADMIN } from "@/test/sesion";

const TECLEO = { delay: null };
const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 30, paginas: 1 } });
const CONFIG = {
  tipos_orden: ["local", "llevar", "domicilio"],
  origenes: ["local", "llamada", "whatsapp"],
  impresoras: [{ id: "i1", nombre: "Cocina", uso: "comanda", ancho_mm: 80, conexion: "navegador", activa: true }],
};
const TENANT = { plan: "pro_ia", modulos_activos: [], nombre_empresa: "Donde Tavo", configuracion: CONFIG };

const SANDWICH = {
  id: "p1", tipo: "plato", nombre: "Sándwich", precio: "12000", categoria_id: "c1", imagen_id: null, va_a_cocina: true, agotado_hoy: false,
  modificadores: [
    { id: "m1", tipo: "sin", nombre: "Sin tomate", precio: "0" },
    { id: "m2", tipo: "extra", nombre: "Extra queso", precio: "2500" },
  ],
};
const GASEOSA = { id: "p2", tipo: "plato", nombre: "Gaseosa", precio: "3500", categoria_id: "c2", imagen_id: null, va_a_cocina: false, agotado_hoy: false, modificadores: [] };
const ARROZ = { id: "p3", tipo: "plato", nombre: "Arroz con pollo", precio: "14000", categoria_id: "c1", imagen_id: null, va_a_cocina: true, agotado_hoy: true, modificadores: [] };
const CARTA = { jornada: "2026-10-12", categorias: [{ id: "c1", nombre: "Almuerzos" }, { id: "c2", nombre: "Bebidas" }], productos: [ARROZ, GASEOSA, SANDWICH] };
const MESAS = [
  { id: "me1", nombre: "B2", zona_id: "z1", zona_nombre: "Salón", puestos: 4, estado: "libre", ordenes: [] },
  { id: "me2", nombre: "T1", zona_id: "z2", zona_nombre: "Terraza", puestos: 4, estado: "ocupada", ordenes: [{ id: "o9", numero: 9, total: "12000", estado_cocina: "entrante" }] },
];
const COMANDA = { id: "k1", numero: 1, estado: "entrante", va_a_cocina: true, created_at: "2026-10-12T17:00:00" };
const ORDEN = {
  id: "o1", jornada: "2026-10-12", numero: 5, codigo: "ORD-261012-005", tipo: "local", origen: "local", mesa_id: "me1", mesa_nombre: "B2",
  cliente_nombre: null, nota: null, estado: "abierta", estado_cocina: "lista", total: "32000", mesero_nombre: "Marta Mesera",
  platos: 3, resumen: "2× Sándwich, 1× Gaseosa", created_at: "2026-10-12T17:00:00",
  items: [
    { id: "it1", comanda_id: "k1", comanda_numero: 1, producto_id: "p1", nombre: "Sándwich", cantidad: 2, precio_unitario: "14500", subtotal: "29000", modificadores: [{ id: "m2", tipo: "extra", nombre: "Extra queso", precio: "2500" }], nota: "Bien tostado", va_a_cocina: true, anulado: false },
    { id: "it2", comanda_id: "k1", comanda_numero: 1, producto_id: "p2", nombre: "Gaseosa", cantidad: 1, precio_unitario: "3500", subtotal: "3500", modificadores: [], nota: null, va_a_cocina: false, anulado: false },
  ],
  comandas: [{ ...COMANDA, estado: "lista" }],
  eventos: [{ id: "e1", tipo: "creada", nota: "Orden en el local, en el local", usuario_nombre: "Marta Mesera", created_at: "2026-10-12T17:00:00" }],
};

function montar(ruta, permisos = PERMISOS_ADMIN) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ConSesion permisos={permisos} tenant={TENANT}>
        <AvisoProvider>
          <Aviso />
          <Routes>
            <Route path="/ordenes" element={<OrdenesLista />} />
            <Route path="/ordenes/nueva" element={<OrdenNueva />} />
            <Route path="/ordenes/mesas" element={<MesasServicio />} />
            <Route path="/ordenes/:id" element={<OrdenDetalle />} />
          </Routes>
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.get.mockImplementation((url) => {
    if (url === "/ordenes/carta") return Promise.resolve({ data: CARTA });
    if (url === "/ordenes/mesas") return Promise.resolve({ data: MESAS });
    if (url === "/ordenes/jornada") return Promise.resolve({ data: { jornada: "2026-10-12", en_curso: 5, ordenes: 12 } });
    if (url === "/ordenes/o1") return Promise.resolve({ data: ORDEN });
    if (url === "/ordenes") return Promise.resolve(PAGINA([ORDEN]));
    return Promise.resolve(PAGINA([]));
  });
});

describe("Tomar pedido", () => {
  it("mesa, platos con un toque, modificadores y nota; envía, imprime la comanda y va al detalle", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { ...ORDEN, comandas: [COMANDA] } });
    montar("/ordenes/nueva");

    await usuario.click(await screen.findByRole("radio", { name: /B2/ }));
    await usuario.click(screen.getByRole("button", { name: /^Sándwich/ }));
    await usuario.click(screen.getByRole("button", { name: /^Sándwich/ }));
    await usuario.click(screen.getByRole("button", { name: /^Gaseosa/ }));
    const pedido = screen.getByRole("complementary", { name: "Pedido" });
    await usuario.click(within(pedido).getByRole("button", { name: /Extra queso/ }));
    await usuario.type(within(pedido).getByLabelText("Nota de Sándwich"), "Bien tostado");
    expect(screen.getByText("$ 32.500")).toBeInTheDocument();

    await usuario.click(screen.getByRole("button", { name: /Enviar orden/ }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/ordenes", expect.objectContaining({
        tipo: "local", mesa_id: "me1",
        items: [
          { producto_id: "p1", cantidad: 2, modificador_ids: ["m2"], nota: "Bien tostado" },
          { producto_id: "p2", cantidad: 1, modificador_ids: [], nota: null },
        ],
      }))
    );
    expect(await screen.findByRole("heading", { level: 1, name: "Orden #5" })).toBeInTheDocument();
    expect(screen.getByText("Orden #5 enviada a cocina")).toBeInTheDocument();
    expect(imprimir).toHaveBeenCalledTimes(1);
    expect(imprimir.mock.calls[0][0].cuerpo).toContain("EXTRA QUESO");
    expect(localStorage.getItem("orden-borrador")).toBeNull();
  });

  it("un plato agotado hoy no se puede tocar", async () => {
    montar("/ordenes/nueva");
    expect(await screen.findByRole("button", { name: /Arroz con pollo.*agotado hoy/ })).toBeDisabled();
  });

  it("sin mesa no envía en el local y lo dice", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/ordenes/nueva");
    await usuario.click(await screen.findByRole("button", { name: /^Gaseosa/ }));
    await usuario.click(screen.getByRole("button", { name: /Enviar orden/ }));
    expect(screen.getByText("Elige la mesa")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("si falta un insumo, dice cuánto queda y ofrece marcar el plato agotado", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockImplementation((url) => {
      if (url === "/ordenes/agotados") return Promise.resolve({ data: null });
      return Promise.reject({
        response: {
          status: 409,
          data: {
            detail: "No se pudo enviar la orden: quedan 200 g de Queso y la orden necesita 300 g.",
            datos: { faltantes: [{ insumo_id: "q1", insumo: "Queso" }], productos: [{ producto_id: "p1", nombre: "Sándwich", insumo_ids: ["q1"] }, { producto_id: "p2", nombre: "Gaseosa", insumo_ids: ["b1"] }] },
          },
        },
      });
    });
    montar("/ordenes/nueva");
    await usuario.click(await screen.findByRole("radio", { name: /llevar/i }));
    await usuario.click(screen.getByRole("button", { name: /^Sándwich/ }));
    await usuario.click(screen.getByRole("button", { name: /^Gaseosa/ }));
    await usuario.click(screen.getByRole("button", { name: /Enviar orden/ }));

    const fallo = await screen.findByText(/quedan 200 g de Queso/, { selector: ".pedido__fallo p" });
    const caja = fallo.closest(".pedido__fallo");
    expect(within(caja).queryByRole("button", { name: /Gaseosa/ })).toBeNull();
    await usuario.click(within(caja).getByRole("button", { name: "Marcar «Sándwich» agotado hoy" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/ordenes/agotados", { producto_id: "p1" }));
    expect(within(screen.getByRole("complementary", { name: "Pedido" })).queryByText("Sándwich")).toBeNull();
  });

  it("guarda el borrador para no perder el pedido si se recarga", async () => {
    const usuario = userEvent.setup(TECLEO);
    const { unmount } = montar("/ordenes/nueva");
    await usuario.click(await screen.findByRole("button", { name: /^Gaseosa/ }));
    unmount();
    montar("/ordenes/nueva");
    const pedido = await screen.findByRole("complementary", { name: "Pedido" });
    expect(await within(pedido).findByText("Gaseosa")).toBeInTheDocument();
  });
});

describe("Tablero, detalle y mesas", () => {
  it("el tablero muestra la jornada y las órdenes con su estado", async () => {
    montar("/ordenes");
    expect(await screen.findByText(/Jornada del lunes 12\/10 · 5 en curso · 12 en el día/)).toBeInTheDocument();
    const fila = (await screen.findByRole("link", { name: "#5" })).closest("tr");
    expect(within(fila).getByText("Mesa B2")).toBeInTheDocument();
    expect(within(fila).getByText("Lista")).toBeInTheDocument();
    expect(within(fila).getByRole("button", { name: "Entregar la orden #5" })).toBeInTheDocument();
  });

  it("anular un plato pide motivo y lo manda", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: ORDEN });
    montar("/ordenes/o1");
    await usuario.click(await screen.findByRole("button", { name: "Quitar Sándwich de la orden" }));
    const dialogo = screen.getByRole("dialog");
    const quitar = within(dialogo).getByRole("button", { name: "Quitar plato" });
    expect(quitar).toBeDisabled();
    await usuario.type(within(dialogo).getByLabelText(/Motivo/), "Se demoró mucho");
    await usuario.click(quitar);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/ordenes/o1/items/it1/anular", { motivo: "Se demoró mucho" }));
  });

  it("el mesero sin permiso de anular no ve el botón", async () => {
    montar("/ordenes/o1", { ordenes: ["ver", "crear", "editar", "cambiar_estado"] });
    await screen.findByRole("heading", { level: 1, name: "Orden #5" });
    expect(screen.queryByRole("button", { name: /^Anular/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Entregar/ })).toBeInTheDocument();
  });

  it("las mesas muestran su estado y sus órdenes", async () => {
    montar("/ordenes/mesas");
    expect(await screen.findByText("1 libres · 1 ocupadas · 0 por cobrar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /#9/ })).toHaveAttribute("href", "/ordenes/o9");
  });
});
