import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: "http://api" } },
}));

import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { Cocina } from "@/modules/cocina/CocinaPage";
import { ConSesion } from "@/test/sesion";

const hace = (min) => new Date(Date.now() - min * 60000).toISOString().replace("Z", "");
const COMANDA = (id, estado, minutos, extra = {}) => ({
  id, numero: 1, estado, created_at: hace(minutos), lista_en: estado === "lista" ? hace(2) : null, tomada_por: null,
  orden_id: `o-${id}`, orden_numero: Number(id.slice(1)), tipo: "local", destino: "Mesa B2", mesero_nombre: "Marta Mesera", nota: null,
  items: [{ id: `i-${id}`, nombre: "Sándwich", cantidad: 2, nota: "Bien tostado", modificadores: [{ id: "m1", tipo: "sin", nombre: "Sin cebolla" }], anulado: false }],
  ...extra,
});

function montar(permisos = { cocina: ["ver", "cambiar_estado"] }) {
  return render(
    <MemoryRouter>
      <ConSesion permisos={permisos}>
        <AvisoProvider>
          <Cocina />
        </AvisoProvider>
      </ConSesion>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockResolvedValue({
    data: {
      alerta_minutos: 15,
      sonido: true,
      comandas: [COMANDA("c5", "entrante", 20), COMANDA("c6", "en_preparacion", 3), COMANDA("c7", "lista", 9)],
      avisos: [{ id: "a1", orden_numero: 4, texto: "Orden #4: se quitó 1× Jugo: Se fue", created_at: hace(1) }],
    },
  });
});

describe("Pantalla de cocina", () => {
  it("reparte las comandas en tres columnas, con modificadores en mayúsculas y la demora marcada", async () => {
    montar();
    const entrantes = await screen.findByRole("region", { name: "Entrantes" });
    const tarjeta = within(entrantes).getByRole("article", { name: "Orden 5" });
    expect(tarjeta).toHaveClass("cocina-tarjeta--tarde");
    expect(within(tarjeta).getByText("▲ 20 min")).toBeInTheDocument();
    expect(within(tarjeta).getByText("SIN CEBOLLA", { exact: false })).toBeInTheDocument();
    expect(within(tarjeta).getByText("» Bien tostado")).toBeInTheDocument();
    const preparacion = screen.getByRole("region", { name: "En preparación" });
    expect(within(preparacion).getByRole("article", { name: "Orden 6" })).not.toHaveClass("cocina-tarjeta--tarde");
    expect(within(screen.getByRole("region", { name: "Listos" })).getByText("Espera al mesero")).toBeInTheDocument();
    expect(screen.getByText(/se quitó 1× Jugo/)).toBeInTheDocument();
  });

  it("Tomar y Finalizar llaman a la cocina y recargan", async () => {
    const usuario = userEvent.setup({ delay: null });
    api.post.mockResolvedValue({ data: {} });
    montar();
    const entrantes = await screen.findByRole("region", { name: "Entrantes" });
    await usuario.click(within(entrantes).getByRole("button", { name: /Tomar/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/cocina/comandas/c5/tomar"));
    await usuario.click(within(screen.getByRole("region", { name: "En preparación" })).getByRole("button", { name: /Finalizar/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/cocina/comandas/c6/finalizar"));
    expect(api.get.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("solo mirar: sin permiso de cambiar estado no hay botones", async () => {
    montar({ cocina: ["ver"] });
    await screen.findByRole("region", { name: "Entrantes" });
    expect(screen.queryByRole("button", { name: /Tomar|Finalizar/ })).toBeNull();
  });
});
