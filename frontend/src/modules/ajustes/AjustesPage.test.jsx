import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));

import { Aviso, GrupoCasillas } from "@/components/ui";
import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { AjustesDetalle, NegocioEditar, OperacionEditar } from "@/modules/ajustes/AjustesPage";
import { MesasLista } from "@/modules/ajustes/MesasPage";
import { ConSesion } from "@/test/sesion";

const NEGOCIO = { id: "t1", nombre_empresa: "Donde Tavo", nit: "900123456-8", direccion: null, ciudad: "Bogotá", telefono: null, correo: null, logo_id: null };
const CONFIG = {
  tipos_orden: ["local", "llevar", "domicilio"],
  origenes: ["local", "llamada", "whatsapp"],
  medios_pago: ["efectivo", "nequi"],
  impuesto_consumo: { aplica: true, tasa: "8.00", incluido_en_precio: true },
  propina_sugerida: "10.00",
  alerta_cocina_minutos: 15,
  sonido_cocina: true,
  jornada: { inicio: "06:00", fin: "22:00" },
  impresoras: [],
};

function responder(url) {
  if (url === "/ajustes/negocio") return Promise.resolve({ data: NEGOCIO });
  if (url === "/ajustes/restaurante") return Promise.resolve({ data: CONFIG });
  return Promise.resolve({ data: { items: [], total: 0, pagina: 1, por_pagina: 10, paginas: 1 } });
}

function montar(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ConSesion>
        <AvisoProvider>
          <Aviso />
          <Routes>
            <Route path="/ajustes" element={<AjustesDetalle />} />
            <Route path="/ajustes/negocio/editar" element={<NegocioEditar />} />
            <Route path="/ajustes/operacion/editar" element={<OperacionEditar />} />
            <Route path="/ajustes/mesas" element={<MesasLista />} />
          </Routes>
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation(responder);
});

describe("GrupoCasillas", () => {
  it("devuelve los elegidos en el orden de las opciones, no en el de los clics", () => {
    const onChange = vi.fn();
    const opciones = [{ valor: "a", etiqueta: "Uno" }, { valor: "b", etiqueta: "Dos" }, { valor: "c", etiqueta: "Tres" }];
    render(<GrupoCasillas etiqueta="Medios" opciones={opciones} valor={["c"]} onChange={onChange} />);
    expect(screen.getByRole("group", { name: "Medios" })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Uno"));
    expect(onChange).toHaveBeenCalledWith(["a", "c"]);
  });
});

describe("Ajustes del restaurante", () => {
  it("el detalle muestra lo configurado con nombres legibles", async () => {
    montar("/ajustes");
    expect(await screen.findByText("Donde Tavo")).toBeInTheDocument();
    expect(screen.getByText("Efectivo · Nequi")).toBeInTheDocument();
    expect(screen.getByText(/8 % · incluido en el precio/)).toBeInTheDocument();
    expect(screen.getByText(/Sin impresoras configuradas/)).toBeInTheDocument();
  });

  it("sin ningún medio de pago no deja guardar y dice por qué", async () => {
    montar("/ajustes/operacion/editar");
    const efectivo = await screen.findByLabelText("Efectivo");
    // El formulario se llena con lo guardado DESPUÉS del primer pintado.
    await waitFor(() => expect(efectivo).toBeChecked());
    fireEvent.click(efectivo);
    fireEvent.click(screen.getByLabelText("Nequi"));
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(await screen.findByText("Habilita al menos un medio de pago")).toBeInTheDocument();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("una impresora por IP exige su dirección y la configuración se guarda con el formato del backend", async () => {
    api.put.mockResolvedValue({ data: CONFIG });
    montar("/ajustes/operacion/editar");
    await waitFor(() => expect(screen.getByLabelText("Efectivo")).toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: /Agregar impresora/ }));
    fireEvent.change(screen.getByLabelText(/^Nombre/), { target: { value: "Cocina" } });
    fireEvent.change(screen.getByLabelText("Conexión"), { target: { value: "ip" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(await screen.findByText(/Escribe la dirección IP/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^Dirección IP/), { target: { value: "192.168.1.50:9100" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(api.put).toHaveBeenCalled());
    const [url, cuerpo] = api.put.mock.calls[0];
    expect(url).toBe("/ajustes/restaurante");
    expect(cuerpo.impresoras).toEqual([
      { nombre: "Cocina", uso: "ambos", ancho_mm: 80, conexion: "ip", direccion: "192.168.1.50:9100", activa: true },
    ]);
    expect(cuerpo.alerta_cocina_minutos).toBe(15);
    expect(cuerpo.impuesto_consumo).toEqual({ aplica: true, tasa: "8", incluido_en_precio: true });
  });

  it("un archivo que no es imagen se rechaza antes de subirlo", async () => {
    montar("/ajustes/negocio/editar");
    const entrada = await waitFor(() => {
      const nodo = document.querySelector('input[type="file"]');
      if (!nodo) throw new Error("sin selector");
      return nodo;
    });
    const pdf = new File(["%PDF"], "carta.pdf", { type: "application/pdf" });
    fireEvent.change(entrada, { target: { files: [pdf] } });
    expect(await screen.findAllByText(/no es una imagen JPG, PNG o WebP/)).not.toHaveLength(0);
    expect(api.put).not.toHaveBeenCalled();
  });
});

describe("Mesas", () => {
  it("lista las mesas con su zona y ofrece ir a las zonas", async () => {
    api.get.mockImplementation((url) =>
      url.startsWith("/ajustes/mesas")
        ? Promise.resolve({ data: { items: [{ id: "m1", nombre: "B2", zona_nombre: "Salón", puestos: 4, activo: true }], total: 1, pagina: 1, por_pagina: 20, paginas: 1 } })
        : responder(url)
    );
    montar("/ajustes/mesas");
    expect(await screen.findByRole("link", { name: "B2" })).toHaveAttribute("href", "/ajustes/mesas/m1");
    expect(screen.getByText("Salón")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Zonas/ })).toBeInTheDocument();
  });
});
