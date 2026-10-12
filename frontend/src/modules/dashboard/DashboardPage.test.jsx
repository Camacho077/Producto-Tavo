import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { defaults: { baseURL: "" }, get: vi.fn() },
  setLogoutHandler: vi.fn(),
}));

// La gráfica se carga con `lazy()`; en jsdom no aporta nada y complica la
// espera, así que se sustituye por una marca que sí se puede observar.
vi.mock("@/components/charts/GraficaRendimiento", () => ({
  default: ({ serie }) => <div data-testid="grafica">puntos: {serie.puntos.length}</div>,
}));

import DashboardPage from "@/modules/dashboard/DashboardPage";
import { api } from "@/lib/api";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/theme/ThemeContext";

const PANEL = {
  periodo: "mes",
  ventana: { desde: "2026-09-01T00:00:00", hasta: "2026-09-26T00:00:00", dias: 25 },
  totales: {
    ventas: 482331000,
    ventas_anterior: 264973000,
    ventas_variacion: 82,
    compras: 228684000,
    compras_anterior: 0,
    compras_variacion: null,
    saldo: 253647000,
    numero_ventas: 67,
    numero_clientes: 6,
    productos_vendidos: 354,
  },
  mas_vendidos: [
    {
      producto_id: "p-1",
      nombre: "Silla ejecutiva Roble",
      categoria: "Mobiliario",
      unidades: 73,
      monto: 110960000,
      variacion: 69.8,
    },
    { producto_id: "p-2", nombre: "Lampara Onix", categoria: null, unidades: 40, monto: 20000000, variacion: null },
  ],
  inventario: {
    productos_activos: 6,
    unidades_stock: 1778,
    bajo_stock: 2,
    valor_inventario: 2900836000,
    pedidos_abiertos: 3,
    categorias: [
      { categoria_id: "c-1", nombre: "Materiales", valor: 1784500000, unidades: 430, vendido: 1, variacion: 122.2 },
      { categoria_id: "c-2", nombre: "Cocina", valor: 111438000, unidades: 453, vendido: 1, variacion: -52.5 },
    ],
  },
  proyeccion: { mes: "2026-10-01", ventas: 558866600, base_meses: 6, historial: [] },
};

const SERIE = {
  rango: "1m",
  unidad: "day",
  puntos: Array.from({ length: 30 }, (_, i) => ({
    inicio: `2026-08-${String(27 + i).padStart(2, "0")}`,
    inicio_anterior: "2026-07-28",
    actual: 1000 * (i + 1),
    anterior: 900 * (i + 1),
  })),
  proyeccion: { inicio: "2026-09-26", valor: 40000 },
};

const AVISOS = { todo_en_orden: true, avisos: [] };

/** Enruta cada URL a su respuesta, y registra qué se pidió. */
function servirApi() {
  api.get.mockImplementation((url) => {
    if (url.startsWith("/dashboard/panel")) return Promise.resolve({ data: { ...PANEL } });
    if (url.startsWith("/dashboard/serie")) return Promise.resolve({ data: { ...SERIE } });
    if (url.startsWith("/dashboard/avisos")) return Promise.resolve({ data: AVISOS });
    if (url === "/seguridad/me") return Promise.resolve({ data: { usuario: null, tenant: null } });
    return Promise.resolve({ data: {} });
  });
}

const urlsPedidas = (prefijo) => api.get.mock.calls.map(([u]) => u).filter((u) => u.startsWith(prefijo));

const montar = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            {/* Destino del buscador, para poder comprobar que navega de verdad. */}
            <Route path="/carta" element={<ListadoFalso />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>
  );

function ListadoFalso() {
  const [parametros] = useSearchParams();
  return <p>listado de productos filtrado por: {parametros.get("q")}</p>;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  servirApi();
});

describe("Dashboard — datos reales del tenant", () => {
  it("pide las cifras y la serie por separado, y los avisos en paralelo", async () => {
    montar();
    await screen.findByText("Silla ejecutiva Roble");

    expect(urlsPedidas("/dashboard/panel")).toEqual(["/dashboard/panel?periodo=mes"]);
    expect(urlsPedidas("/dashboard/serie")).toEqual(["/dashboard/serie?rango=1m"]);
    expect(urlsPedidas("/dashboard/avisos")).toEqual(["/dashboard/avisos"]);
  });

  it("pinta los más vendidos con su categoría, su monto y su variación", async () => {
    montar();
    await screen.findByText("Silla ejecutiva Roble");

    expect(screen.getByText("Mobiliario")).toBeInTheDocument();
    // El monto CUENTA hasta su valor (CifraAnimada, ~900 ms): lo que importa
    // es que termine exactamente en el dato real.
    expect(await screen.findByText("$ 110.960.000", {}, { timeout: 2500 })).toBeInTheDocument();
    expect(screen.getByText("69,8%")).toBeInTheDocument();
    // Las tarjetas que se leen con el cursor encima no se elevan en hover
    // (review-animations, 2026-09-29): borde y luz sí, desplazamiento no.
    expect(screen.getByText("Productos más vendidos").closest(".tarjeta")).toHaveClass("tarjeta--quieta");
    expect(screen.getByLabelText("Rendimiento")).toHaveClass("tarjeta--quieta");
    // Cada producto enlaza a su ficha.
    expect(screen.getByRole("link", { name: /Silla ejecutiva Roble/ })).toHaveAttribute(
      "href",
      "/carta/p-1"
    );
    // Sin categoría no se inventa una: se dice que no la tiene.
    expect(screen.getByText("Sin categoría")).toBeInTheDocument();
  });

  it("fila de KPI con capa doble: cuatro tarjetas, cifras que cuentan hasta el dato y su tendencia", async () => {
    montar();
    await screen.findByText("Silla ejecutiva Roble");

    const kpis = [...document.querySelectorAll(".kpi")];
    expect(kpis.map((k) => k.querySelector(".kpi__etiqueta").textContent)).toEqual([
      "Total vendido",
      "Compras",
      "Clientes",
      "Productos vendidos",
    ]);
    // Cifra e icono DENTRO del bloque gris; la tendencia, fuera de él.
    for (const kpi of kpis) {
      const bloque = kpi.querySelector(":scope > .kpi__bloque");
      expect(bloque.querySelector(".kpi__icono svg")).not.toBeNull();
      expect(bloque.querySelector(".kpi__valor")).not.toBeNull();
      expect(kpi.querySelector(":scope > .kpi__tendencia")).not.toBeNull();
    }
    const valor = (i) => kpis[i].querySelector(".kpi__valor");
    // Todas terminan a la vez (~900 ms); los conteos van redondeados.
    await waitFor(() => expect(valor(0)).toHaveTextContent("$ 482.331.000"), { timeout: 2500 });
    expect(valor(1)).toHaveTextContent("$ 228.684.000");
    expect(valor(2)).toHaveTextContent(/^6$/);
    expect(valor(3)).toHaveTextContent(/^354$/);
    // Ventas trae variación; compras no tiene base: dice el periodo, sin %.
    expect(kpis[0].querySelector(".kpi__tendencia")).toHaveTextContent("▲82,0%vs. mismo tramo del mes anterior");
    expect(kpis[1].querySelector(".kpi__tendencia")).toHaveTextContent("Sin comparativa en este mes");
    expect(kpis[1].querySelector(".insignia")).toBeNull();
    // El timbre y el usuario ya no están en el encabezado del dashboard.
    expect(screen.queryByLabelText("Ir a los avisos")).toBeNull();
  });

  it("sin base de comparación NO inventa una variación", async () => {
    montar();
    await screen.findByText("Lampara Onix");
    // compras_anterior = 0 y la variación del segundo producto es null: en
    // ninguno de los dos casos puede aparecer un porcentaje.
    const insignias = document.querySelectorAll(".insignia");
    const textos = [...insignias].map((n) => n.textContent);
    expect(textos).not.toContain("▲100,0%");
  });

  it("arma la rejilla de inventario por categoría con un objeto 3D cada una", async () => {
    montar();
    await screen.findByText("Materiales");

    expect(screen.getByText("Cocina")).toBeInTheDocument();
    expect(screen.getByText("430 insumos")).toBeInTheDocument();
    expect(document.querySelectorAll(".objeto3d")).toHaveLength(2);
  });

  it("cambiar de periodo vuelve a pedir SOLO las cifras, nunca la serie", async () => {
    montar();
    await screen.findByText("Silla ejecutiva Roble");

    fireEvent.click(screen.getByRole("button", { name: "Año" }));

    await waitFor(() => expect(urlsPedidas("/dashboard/panel")).toHaveLength(2));
    expect(urlsPedidas("/dashboard/panel")[1]).toBe("/dashboard/panel?periodo=anio");
    expect(urlsPedidas("/dashboard/serie")).toHaveLength(1);
  });

  it("cambiar de rango vuelve a pedir SOLO la serie, nunca las cifras", async () => {
    montar();
    await screen.findByTestId("grafica");

    fireEvent.click(screen.getByRole("button", { name: "1A" }));

    await waitFor(() => expect(urlsPedidas("/dashboard/serie")).toHaveLength(2));
    expect(urlsPedidas("/dashboard/serie")[1]).toBe("/dashboard/serie?rango=1a");
    expect(urlsPedidas("/dashboard/panel")).toHaveLength(1);
  });

  it("al recargar conserva el contenido: nunca vuelve al esqueleto", async () => {
    montar();
    await screen.findByText("Silla ejecutiva Roble");
    expect(screen.queryByLabelText("Cargando cifras")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Hoy" }));

    // Mientras llega la respuesta nueva, el contenido actual sigue en pantalla.
    expect(screen.getByText("Silla ejecutiva Roble")).toBeInTheDocument();
    expect(screen.queryByLabelText("Cargando cifras")).toBeNull();
    await waitFor(() => expect(urlsPedidas("/dashboard/panel")).toHaveLength(2));
    expect(screen.queryByLabelText("Cargando cifras")).toBeNull();
  });

  it("el esqueleto y el contenido son las MISMAS tarjetas: la entrada no se repite al llegar los datos", async () => {
    // Si al llegar la respuesta se montaran tarjetas nuevas, su `.reveal`
    // volvería a correr desde opacidad 0 justo después del esqueleto: eso es
    // el parpadeo que CLAUDE.md prohíbe.
    let responderPanel;
    api.get.mockImplementation((url) => {
      if (url.startsWith("/dashboard/panel")) return new Promise((r) => (responderPanel = r));
      if (url.startsWith("/dashboard/serie")) return Promise.resolve({ data: { ...SERIE } });
      if (url.startsWith("/dashboard/avisos")) return Promise.resolve({ data: AVISOS });
      return Promise.resolve({ data: {} });
    });
    montar();
    const seccion = screen.getByLabelText("Cargando cifras");
    const tarjetasAntes = [...seccion.querySelectorAll(".reveal")];
    expect(tarjetasAntes.length).toBeGreaterThanOrEqual(4);

    responderPanel({ data: { ...PANEL } });
    await screen.findByText("Silla ejecutiva Roble");

    const tarjetasDespues = [...screen.getByLabelText("Resumen del periodo").querySelectorAll(".reveal")];
    expect(tarjetasDespues).toEqual(tarjetasAntes);
    tarjetasDespues.forEach((nodo, i) => expect(nodo).toBe(tarjetasAntes[i]));
  });

  it("muestra el esqueleto antes de la primera respuesta, nunca el estado vacío", () => {
    api.get.mockImplementation(() => new Promise(() => {}));
    montar();
    expect(screen.getByLabelText("Cargando cifras")).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay ventas/)).toBeNull();
  });

  it("con el periodo sin ventas, el estado vacío explica qué falta", async () => {
    api.get.mockImplementation((url) => {
      if (url.startsWith("/dashboard/panel")) {
        return Promise.resolve({
          data: {
            ...PANEL,
            mas_vendidos: [],
            inventario: { ...PANEL.inventario, categorias: [] },
          },
        });
      }
      if (url.startsWith("/dashboard/serie")) return Promise.resolve({ data: SERIE });
      return Promise.resolve({ data: AVISOS });
    });
    montar();

    expect(await screen.findByText(/Todavía no hay ventas completadas en este periodo/)).toBeInTheDocument();
    expect(screen.getByText(/Aún no hay insumos con existencias/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Crear insumo" })).toHaveAttribute(
      "href",
      "/inventario/insumos/nuevo"
    );
  });

  it("el buscador lleva al listado de productos con la búsqueda ya aplicada", async () => {
    montar();
    await screen.findByText("Silla ejecutiva Roble");

    const campo = screen.getByLabelText("Buscar productos");
    fireEvent.change(campo, { target: { value: "silla roble" } });
    fireEvent.submit(campo.closest("form"));

    expect(await screen.findByText(/listado de productos filtrado por: silla roble/)).toBeInTheDocument();
  });
});
