import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ api: { defaults: { baseURL: "" }, get: vi.fn() } }));

import { api } from "@/lib/api";
import PanelAvisos from "@/modules/dashboard/PanelAvisos";

const montar = () =>
  render(
    <MemoryRouter>
      <PanelAvisos />
    </MemoryRouter>
  );

const AVISO_STOCK = {
  clave: "stock_agotado",
  nivel: "critico",
  titulo: "2 productos agotados",
  texto: "Teclado y Mouse en 0 unidades: no se pueden vender hasta que entre una compra.",
  enlace: { recurso: "productos", id: null },
};

beforeEach(() => vi.clearAllMocks());

describe("Panel de avisos del dashboard", () => {
  it("muestra cada aviso con su texto y un enlace al registro relacionado", async () => {
    api.get.mockResolvedValue({
      data: {
        todo_en_orden: false,
        avisos: [
          AVISO_STOCK,
          {
            clave: "mas_vendido",
            nivel: "informativo",
            titulo: "Lo más vendido de la semana: Diadema",
            texto: "9 unidades en los últimos 7 días. Revisa que no se quede corto de stock.",
            enlace: { recurso: "producto", id: "abc-123" },
          },
        ],
      },
    });
    montar();

    expect(await screen.findByText("2 productos agotados")).toBeInTheDocument();
    expect(screen.getByText(/Teclado y Mouse en 0 unidades/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver productos" })).toHaveAttribute("href", "/compras/productos");
    expect(screen.getByRole("link", { name: "Ver producto" })).toHaveAttribute("href", "/compras/productos/abc-123");
    expect(api.get).toHaveBeenCalledWith("/dashboard/avisos");
  });

  it("el nivel del aviso solo cambia su color, no su estructura", async () => {
    api.get.mockResolvedValue({
      data: {
        todo_en_orden: false,
        avisos: [
          AVISO_STOCK,
          { ...AVISO_STOCK, clave: "pedidos_estancados", nivel: "advertencia", titulo: "1 pedido sin avanzar", enlace: { recurso: "pedidos", id: null } },
          { ...AVISO_STOCK, clave: "ventas_subida", nivel: "positivo", titulo: "Las ventas subieron 40% esta semana", enlace: { recurso: "ventas", id: null } },
        ],
      },
    });
    const { container } = montar();
    await screen.findByText("2 productos agotados");

    const items = container.querySelectorAll(".aviso-item");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveClass("aviso-item--critico");
    expect(items[1]).toHaveClass("aviso-item--advertencia");
    expect(items[2]).toHaveClass("aviso-item--positivo");
  });

  it("sin avisos NUNCA queda un panel vacío: dice que todo está en orden", async () => {
    api.get.mockResolvedValue({ data: { avisos: [], todo_en_orden: true } });
    montar();
    expect(await screen.findByText(/Todo en orden/)).toBeInTheDocument();
    expect(document.querySelectorAll(".aviso-item")).toHaveLength(0);
  });

  it("mientras carga muestra el marcador, nunca el estado vacío antes de la primera respuesta", async () => {
    let resolver;
    api.get.mockReturnValue(new Promise((r) => (resolver = r)));
    montar();

    expect(screen.getByLabelText("Cargando avisos")).toBeInTheDocument();
    expect(screen.queryByText(/Todo en orden/)).toBeNull();

    resolver({ data: { avisos: [AVISO_STOCK], todo_en_orden: false } });
    expect(await screen.findByText("2 productos agotados")).toBeInTheDocument();
    expect(screen.queryByLabelText("Cargando avisos")).toBeNull();
  });

  it("si un aviso viene sin enlace utilizable, se muestra igual sin romperse", async () => {
    api.get.mockResolvedValue({
      data: { todo_en_orden: false, avisos: [{ ...AVISO_STOCK, enlace: { recurso: "desconocido", id: null } }] },
    });
    montar();
    expect(await screen.findByText("2 productos agotados")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
