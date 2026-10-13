import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));

import { Aviso } from "@/components/ui";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { CargaInicial } from "@/modules/inventario/CargaInicialPage";
import { ConteoDetalle, ConteoNuevo, MermaNueva, MovimientosLista } from "@/modules/inventario/MovimientosPage";
import { ConSesion, PERMISOS_ADMIN } from "@/test/sesion";

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 20, paginas: 1 } });
const TECLEO = { delay: null };

const QUESO = { id: "i1", nombre: "Queso", unidad: "kg", grupo: "Lácteos", existencia: "2", minimo: "0", activo: true };
const ARROZ = { id: "i2", nombre: "Arroz", unidad: "kg", grupo: "Abarrotes", existencia: "10", minimo: "0", activo: true };
const MERMA = {
  id: "m1", insumo_id: "i1", insumo_nombre: "Queso", unidad: "kg", tipo: "merma", cantidad: "-0.300", existencia_resultante: "1.700",
  valor: "-6000.00", motivo: "Vencido", usuario_nombre: "Ana Bodega", created_at: "2026-10-12T15:00:00",
};
const AJUSTE = { ...MERMA, id: "m2", tipo: "ajuste", cantidad: "1.000", documento_tipo: "conteo", documento_id: "c1", documento_codigo: "CON-000001", motivo: "Cierre" };

function montar(ruta, permisos = PERMISOS_ADMIN) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ConSesion permisos={permisos}>
        <AvisoProvider>
          <Aviso />
          <Routes>
            <Route path="/inventario/movimientos" element={<MovimientosLista />} />
            <Route path="/inventario/insumos" element={<p>listado de insumos</p>} />
            <Route path="/inventario/insumos/:id" element={<p>detalle del insumo</p>} />
            <Route path="/inventario/insumos/:id/merma" element={<MermaNueva />} />
            <Route path="/inventario/conteos" element={<p>listado de conteos</p>} />
            <Route path="/inventario/conteos/nuevo" element={<ConteoNuevo />} />
            <Route path="/inventario/conteos/:id" element={<ConteoDetalle />} />
            <Route path="/inventario/carga-inicial" element={<CargaInicial />} />
          </Routes>
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/inventario/insumos/i1") return Promise.resolve({ data: QUESO });
    if (url === "/inventario/insumos") return Promise.resolve(PAGINA([QUESO, ARROZ]));
    if (url.startsWith("/inventario/movimientos")) return Promise.resolve(PAGINA([MERMA, AJUSTE]));
    return Promise.resolve(PAGINA([]));
  });
});

describe("Historial general de movimientos", () => {
  it("muestra quién, cuánto y por qué, y enlaza el ajuste a su conteo", async () => {
    montar("/inventario/movimientos");
    const fila = (await screen.findAllByText("Ana Bodega"))[0].closest("tr");
    expect(within(fila).getByText("−300 g")).toBeInTheDocument();
    expect(within(fila).getByText("Vencido")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CON-000001" })).toHaveAttribute("href", "/inventario/conteos/c1");
    expect(screen.getByRole("columnheader", { name: "Valor a costo" })).toBeInTheDocument();
  });

  it("sin permiso de costos no muestra el valor", async () => {
    montar("/inventario/movimientos", { movimientos: ["ver"] });
    await screen.findAllByText("Ana Bodega");
    expect(screen.queryByRole("columnheader", { name: "Valor a costo" })).not.toBeInTheDocument();
  });
});

describe("Merma", () => {
  it("convierte a la unidad del insumo, dice cuánto quedaría y exige detalle con «Otro»", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: MERMA });
    montar("/inventario/insumos/i1/merma");

    const cantidad = await screen.findByLabelText(/Cantidad/);
    await usuario.selectOptions(screen.getByLabelText(/Unidad/), "g");
    await usuario.type(cantidad, "300");
    expect(screen.getByText("Quedarían 1,7 kg.")).toBeInTheDocument();

    await usuario.selectOptions(screen.getByLabelText(/Motivo/), "otro");
    await usuario.click(screen.getByRole("button", { name: "Registrar merma" }));
    expect(await screen.findByText(/con el motivo «Otro» el detalle es obligatorio/)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();

    await usuario.type(screen.getByLabelText(/Detalle/), "Se cortó");
    await usuario.click(screen.getByRole("button", { name: "Registrar merma" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/inventario/insumos/i1/merma", { cantidad: "300", unidad: "g", motivo: "otro", detalle: "Se cortó" }));
    expect(await screen.findByText("detalle del insumo")).toBeInTheDocument();
    expect(screen.getByText("Merma de Queso registrada")).toBeInTheDocument();
  });

  it("avisa antes de enviar si la merma es más de lo que hay", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/inventario/insumos/i1/merma");
    await usuario.type(await screen.findByLabelText(/Cantidad/), "3");
    expect(await screen.findByText(/Es más de lo que hay \(2 kg\)/)).toBeInTheDocument();
  });
});

describe("Conteo físico", () => {
  it("envía solo los insumos contados y muestra la diferencia en vivo", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "c1" } });
    montar("/inventario/conteos/nuevo");

    const arroz = await screen.findByLabelText("Contado de Arroz en kg");
    await usuario.type(arroz, "8.5");
    expect(screen.getByText("▼ −1,5 kg")).toBeInTheDocument();
    await usuario.type(screen.getByLabelText(/Motivo/), "Cierre de mes");
    await usuario.click(screen.getByRole("button", { name: /Registrar conteo/ }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/inventario/conteos", { motivo: "Cierre de mes", lineas: [{ insumo_id: "i2", contado: "8.5" }] })
    );
    expect(await screen.findByText("listado de conteos")).toBeInTheDocument();
  });

  it("sin ningún insumo contado no envía y dice por qué", async () => {
    const usuario = userEvent.setup(TECLEO);
    montar("/inventario/conteos/nuevo");
    await screen.findByLabelText("Contado de Arroz en kg");
    await usuario.click(screen.getByRole("button", { name: /Registrar conteo/ }));
    expect(screen.getByRole("alert")).toHaveTextContent("Escribe lo que contaste en al menos un insumo.");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("el detalle muestra sistema, contado y diferencia", async () => {
    api.get.mockResolvedValue({
      data: {
        id: "c1", numero: 1, codigo: "CON-000001", motivo: "Cierre", usuario_nombre: "Ana Bodega", lineas: 1, con_diferencia: 1,
        valor_diferencia: "-6000.00", created_at: "2026-10-12T15:00:00",
        items: [{ insumo_id: "i2", insumo_nombre: "Arroz", unidad: "kg", sistema: "10", contado: "8.5", diferencia: "-1.5", valor: "-6000.00" }],
      },
    });
    montar("/inventario/conteos/c1");
    expect(await screen.findByRole("heading", { level: 1, name: "Conteo CON-000001" })).toBeInTheDocument();
    const fila = screen.getByRole("link", { name: "Arroz" }).closest("tr");
    expect(within(fila).getByText("8,5 kg")).toBeInTheDocument();
    expect(within(fila).getByText("▼ −1,5 kg")).toBeInTheDocument();
  });
});

describe("Carga inicial", () => {
  const archivo = () => new File(["x"], "plantilla.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

  it("revisa el archivo y muestra cada error con hoja, fila y columna, sin ofrecer guardar", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({
      data: {
        valido: false, aplicado: false, total_errores: 1,
        errores: [{ hoja: "Insumos", fila: 3, columna: "Unidad", mensaje: "Debe ser una de estas opciones: kg, g, L, ml o unidad" }],
        hojas: [{ hoja: "Insumos", filas: 2, nuevos: 1, actualizados: 0 }, { hoja: "Platos", filas: 0, nuevos: 0, actualizados: 0 }, { hoja: "Recetas", filas: 0, platos: 0 }],
      },
    });
    montar("/inventario/carga-inicial");
    await usuario.upload(screen.getByLabelText(/Archivo/), archivo());
    await usuario.click(screen.getByRole("button", { name: /Revisar archivo/ }));

    const fila = (await screen.findByText(/Debe ser una de estas opciones/)).closest("tr");
    expect(within(fila).getByText("Insumos")).toBeInTheDocument();
    expect(within(fila).getByText("3")).toBeInTheDocument();
    expect(within(fila).getByText("Unidad")).toBeInTheDocument();
    expect(screen.getByText(/1 error\(es\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Guardar carga/ })).not.toBeInTheDocument();
    expect(api.post.mock.calls[0][0]).toBe("/inventario/carga-inicial/validar");
  });

  it("con el archivo limpio confirma y guarda", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockImplementation((url) =>
      Promise.resolve({
        data: {
          valido: true, aplicado: url.endsWith("aplicar"), total_errores: 0, errores: [],
          hojas: [{ hoja: "Insumos", filas: 2, nuevos: 2, actualizados: 0 }, { hoja: "Platos", filas: 0, nuevos: 0, actualizados: 0 }, { hoja: "Recetas", filas: 0, platos: 0 }],
        },
      })
    );
    montar("/inventario/carga-inicial");
    await usuario.upload(screen.getByLabelText(/Archivo/), archivo());
    await usuario.click(screen.getByRole("button", { name: /Revisar archivo/ }));
    await usuario.click(await screen.findByRole("button", { name: /Guardar carga/ }));
    await usuario.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("listado de insumos")).toBeInTheDocument();
    expect(api.post.mock.calls.at(-1)[0]).toBe("/inventario/carga-inicial/aplicar");
    expect(screen.getByText("Carga inicial guardada")).toBeInTheDocument();
  });

  it("un CSV pide la hoja y la adivina por el nombre del archivo", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { valido: true, aplicado: false, total_errores: 0, errores: [], hojas: [] } });
    montar("/inventario/carga-inicial");
    await usuario.upload(screen.getByLabelText(/Archivo/), new File(["x"], "plantilla-recetas.csv", { type: "text/csv" }));
    expect(screen.getByLabelText(/Qué hoja es este CSV/)).toHaveValue("Recetas");
    await usuario.click(screen.getByRole("button", { name: /Revisar archivo/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/inventario/carga-inicial/validar", expect.any(File), { params: { hoja: "Recetas" }, headers: { "Content-Type": "text/csv" } }));
  });
});
