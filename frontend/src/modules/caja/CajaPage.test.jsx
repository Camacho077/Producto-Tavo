import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));
vi.mock("@/lib/impresion", async (original) => ({ ...(await original()), imprimirComprobante: vi.fn(() => Promise.resolve()) }));

import { Aviso } from "@/components/ui";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { imprimirComprobante } from "@/lib/impresion";
import { CajaInicio, CierreCaja, Cobrar } from "@/modules/caja/CajaPage";
import { desglose } from "@/modules/caja/dinero";
import { ConSesion, PERMISOS_ADMIN } from "@/test/sesion";

const TECLEO = { delay: null };
const CONFIG = { medios_pago: ["efectivo", "nequi", "tarjeta"], propina_sugerida: "10", impuesto_consumo: { aplica: true, tasa: "8", incluido_en_precio: true } };
const TENANT = { plan: "pro_ia", modulos_activos: [], nombre_empresa: "Donde Tavo", configuracion: CONFIG };
const RESUMEN = { ventas: 3, ventas_anuladas: 0, total_ventas: "54000", propinas: "2700", impuesto: "4000", gastos_de_caja: "8000", base_inicial: "50000", esperado: { efectivo: "70000", nequi: "12000" } };
const CAJA = { id: "c1", numero: 7, estado: "abierta", abierta_en: "2026-10-12T11:30:00", abierta_por: "Carla Caja", base_inicial: "50000", resumen: RESUMEN };
const ORDEN = {
  id: "o1", numero: 5, tipo: "local", mesa_nombre: "B2", cliente_nombre: null,
  items: [
    { id: "i1", nombre: "Sándwich", cantidad: 2, precio_unitario: "10800", modificadores: [], anulado: false, venta_id: null },
    { id: "i2", nombre: "Gaseosa", cantidad: 1, precio_unitario: "5400", modificadores: [], anulado: false, venta_id: null },
  ],
};

function montar(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ConSesion permisos={PERMISOS_ADMIN} tenant={TENANT}>
        <AvisoProvider>
          <Aviso />
          <Routes>
            <Route path="/caja" element={<CajaInicio />} />
            <Route path="/caja/cobrar/:id" element={<Cobrar />} />
            <Route path="/caja/cierre" element={<CierreCaja />} />
            <Route path="/caja/ventas/:id" element={<p>detalle del comprobante</p>} />
            <Route path="/caja/cierres/:id" element={<p>reporte del cierre</p>} />
          </Routes>
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/caja/actual") return Promise.resolve({ data: { caja: CAJA } });
    if (url === "/caja/por-cobrar") return Promise.resolve({ data: [{ id: "o1", numero: 5, tipo: "local", mesa_nombre: "B2", estado_cocina: "entregada", por_cobrar: "27000", platos: 3, created_at: "2026-10-12T17:00:00" }] });
    if (url === "/ordenes/o1") return Promise.resolve({ data: ORDEN });
    return Promise.resolve({ data: null });
  });
});

describe("desglose del impuesto al consumo", () => {
  it("incluido en el precio, sumado o sin impuesto", () => {
    expect(desglose(27000, CONFIG)).toEqual({ subtotal: 25000, impuesto: 2000, total: 27000, tasa: 8 });
    expect(desglose(10800, { impuesto_consumo: { aplica: true, tasa: "8", incluido_en_precio: false } })).toEqual({ subtotal: 10800, impuesto: 864, total: 11664, tasa: 8 });
    expect(desglose(10800, { impuesto_consumo: { aplica: false, tasa: "8", incluido_en_precio: true } }).impuesto).toBe(0);
  });
});

describe("Caja", () => {
  it("con la caja cerrada ofrece abrirla con su base", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.get.mockImplementation((url) => Promise.resolve({ data: url === "/caja/actual" ? { caja: null } : [] }));
    api.post.mockResolvedValue({ data: CAJA });
    montar("/caja");
    await usuario.type(await screen.findByLabelText(/Base inicial/), "50000");
    await usuario.click(screen.getByRole("button", { name: /Abrir caja/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/caja/abrir", { base_inicial: "50000" }));
  });

  it("con la caja abierta muestra el cuadre en vivo y lo que hay por cobrar", async () => {
    montar("/caja");
    expect(await screen.findByRole("heading", { level: 1, name: "Caja 7" })).toBeInTheDocument();
    expect(screen.getAllByText("$ 70.000").length).toBeGreaterThan(0);
    expect(await screen.findByRole("button", { name: "Cobrar la orden #5" })).toBeInTheDocument();
  });

  it("cobra con dos medios, propina y devueltas; imprime el comprobante", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "v1", codigo: "CI-000012", items: [], pagos: [] } });
    montar("/caja/cobrar/o1");
    const cuenta = await screen.findByRole("complementary", { name: "Cuenta" });
    expect(within(cuenta).getByText("$ 25.000")).toBeInTheDocument(); // base
    await usuario.click(within(cuenta).getByRole("button", { name: "10 %" }));
    expect(within(cuenta).getByText("$ 29.700")).toBeInTheDocument();

    const [monto] = within(cuenta).getAllByLabelText("Monto");
    await usuario.type(monto, "20000");
    await usuario.type(within(cuenta).getByLabelText("Recibido"), "50000");
    expect(within(cuenta).getByText("$ 30.000")).toBeInTheDocument(); // devueltas
    expect(screen.getByText("Faltan $ 9.700")).toBeInTheDocument();
    await usuario.click(within(cuenta).getByRole("button", { name: /Otro medio/ }));
    expect(screen.getByText("Los pagos cuadran con la cuenta.")).toBeInTheDocument();

    await usuario.click(within(cuenta).getByRole("button", { name: /Cobrar \$\s29\.700/ }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/caja/cobros", expect.objectContaining({
        orden_id: "o1", items: null, propina: "2700",
        pagos: [{ medio: "efectivo", monto: "20000", recibido: "50000" }, { medio: "nequi", monto: "9700", recibido: null }],
      }))
    );
    expect(await screen.findByText("detalle del comprobante")).toBeInTheDocument();
    expect(imprimirComprobante).toHaveBeenCalledTimes(1);
  });

  it("dividir la cuenta: cobra solo un sándwich", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "v1", codigo: "CI-000013", items: [], pagos: [] } });
    montar("/caja/cobrar/o1");
    await usuario.click(await screen.findByRole("button", { name: "Uno menos de Sándwich" }));
    await usuario.click(screen.getByRole("checkbox", { name: "Gaseosa" }));
    const cuenta = screen.getByRole("complementary", { name: "Cuenta" });
    await usuario.type(within(cuenta).getByLabelText("Monto"), "10800");
    await usuario.click(within(cuenta).getByRole("button", { name: /Cobrar \$\s10\.800/ }));
    await waitFor(() => expect(api.post.mock.calls[0][1].items).toEqual([{ orden_item_id: "i1", cantidad: 1 }]));
  });

  it("el cierre exige motivo cuando no cuadra", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "c1", numero: 7 } });
    montar("/caja/cierre");
    await usuario.type(await screen.findByLabelText("Contado en Efectivo"), "69200");
    await usuario.type(screen.getByLabelText("Contado en Nequi"), "12000");
    await usuario.type(screen.getByLabelText("Contado en Tarjeta"), "0");
    expect(screen.getByText("▼ Faltan $ 800")).toBeInTheDocument();
    const cerrar = screen.getByRole("button", { name: /Cerrar caja/ });
    expect(cerrar).toBeDisabled();
    await usuario.type(screen.getByLabelText(/Motivo de la diferencia/), "Devueltas mal dadas");
    await usuario.click(cerrar);
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/caja/cerrar", { contado: { efectivo: "69200", nequi: "12000", tarjeta: "0" }, motivo_diferencia: "Devueltas mal dadas" })
    );
    expect(await screen.findByText("reporte del cierre")).toBeInTheDocument();
  });
});
