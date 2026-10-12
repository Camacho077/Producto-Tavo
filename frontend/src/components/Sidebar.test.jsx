import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import Sidebar from "@/components/Sidebar";
import { ThemeProvider } from "@/theme/ThemeContext";

function renderizar(ruta = "/", plan = "pro_ia") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ThemeProvider>
        <Sidebar plan={plan} nombreEmpresa="Empresa Test" />
      </ThemeProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("Sidebar con grupos desplegables", () => {
  it("muestra los grupos Compras, Caja, Seguridad y Ajustes con sus submódulos", () => {
    renderizar();
    const grupo = screen.getByRole("button", { name: /compras/i });
    expect(grupo).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(grupo);
    expect(grupo).toHaveAttribute("aria-expanded", "true");
    for (const nombre of ["Productos", "Categorías", "Proveedores"]) {
      expect(screen.getByRole("link", { name: nombre })).toHaveAttribute("href", expect.stringContaining("/compras/"));
    }

    fireEvent.click(screen.getByRole("button", { name: /caja/i }));
    expect(screen.getByRole("link", { name: "Órdenes" })).toHaveAttribute("href", "/ventas/pedidos");


    fireEvent.click(screen.getByRole("button", { name: /seguridad/i }));
    expect(screen.getByRole("link", { name: "Usuarios" })).toHaveAttribute("href", "/seguridad/usuarios");
    expect(screen.getByRole("link", { name: "Roles" })).toHaveAttribute("href", "/seguridad/roles");

    fireEvent.click(screen.getByRole("button", { name: /ajustes/i }));
    expect(screen.getByRole("link", { name: "Restaurante" })).toHaveAttribute("href", "/ajustes");
    expect(screen.getByRole("link", { name: "Mesas" })).toHaveAttribute("href", "/ajustes/mesas");
  });

  it("el chevron rota al abrir el grupo", () => {
    renderizar();
    const grupo = screen.getByRole("button", { name: /compras/i });
    const chevron = grupo.querySelector(".sidebar__chevron");
    expect(chevron).not.toHaveClass("sidebar__chevron--abierto");
    fireEvent.click(grupo);
    expect(chevron).toHaveClass("sidebar__chevron--abierto");
  });

  it("al cargar TODOS los grupos están cerrados, aunque la ruta sea de un grupo", () => {
    renderizar("/compras/proveedores");
    for (const nombre of [/compras/i, /caja/i, /seguridad/i, /ajustes/i]) {
      expect(screen.getByRole("button", { name: nombre })).toHaveAttribute("aria-expanded", "false");
    }
    expect(screen.queryByRole("link", { name: "Proveedores" })).toBeNull();
  });

  it("no recuerda el grupo abierto entre recargas", () => {
    const { unmount } = renderizar();
    fireEvent.click(screen.getByRole("button", { name: /caja/i }));
    unmount();

    renderizar();
    expect(screen.getByRole("button", { name: /caja/i })).toHaveAttribute("aria-expanded", "false");
  });

  it("solo un grupo abierto a la vez: abrir uno cierra el anterior", () => {
    renderizar();
    const compras = screen.getByRole("button", { name: /compras/i });
    const ventas = screen.getByRole("button", { name: /caja/i });
    fireEvent.click(compras);
    expect(compras).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(ventas);
    expect(ventas).toHaveAttribute("aria-expanded", "true");
    expect(compras).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Productos" })).toBeNull();
    fireEvent.click(ventas);
    expect(ventas).toHaveAttribute("aria-expanded", "false");
  });

  it("al abrir el grupo de la ruta actual marca el submódulo activo", () => {
    renderizar("/compras/proveedores");
    fireEvent.click(screen.getByRole("button", { name: /compras/i }));
    expect(screen.getByRole("link", { name: "Proveedores" })).toHaveClass("sidebar__activo");
  });

  it("hay UN solo indicador del ítem activo (se desliza, no aparece en cada ítem)", () => {
    const { container } = renderizar("/");
    const indicadores = container.querySelectorAll(".sidebar__indicador");
    expect(indicadores).toHaveLength(1);
    // En Dashboard es la píldora de la maqueta.
    expect(indicadores[0]).toHaveClass("sidebar__indicador--visible");
    expect(indicadores[0].dataset.cara).toBe("fuerte");
    expect(indicadores[0].style.transform).toMatch(/^translate3d\(/);
  });

  it("con la ruta dentro de un grupo cerrado, el indicador (cara sutil) va a la cabecera; abierto, al submódulo", () => {
    const { container } = renderizar("/compras/proveedores");
    const indicador = container.querySelector(".sidebar__indicador");
    expect(indicador.dataset.cara).toBe("sutil");
    fireEvent.click(screen.getByRole("button", { name: /compras/i }));
    expect(indicador.dataset.cara).toBe("sutil");
    expect(indicador).toHaveClass("sidebar__indicador--visible");
  });

  it("al cerrar un grupo sus submódulos salen animados, pero dejan de ser navegables desde el mismo clic", () => {
    const { container } = renderizar();
    const compras = screen.getByRole("button", { name: /compras/i });
    fireEvent.click(compras);
    fireEvent.click(compras);
    // Siguen en el DOM mientras se van (salida animada)...
    const panel = container.querySelector("#sidebar-grupo-compras");
    expect(panel).toHaveClass("sidebar__panel-interior--saliendo");
    // ...pero fuera del árbol accesible y sin foco.
    expect(panel).toHaveAttribute("aria-hidden", "true");
    expect(panel).toHaveAttribute("inert");
    expect(screen.queryByRole("link", { name: "Productos" })).toBeNull();
  });

  it("oculta Compras y Caja en el plan básico", () => {
    renderizar("/", "basico");
    expect(screen.queryByRole("button", { name: /compras/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /caja/i })).toBeNull();
    expect(screen.getByRole("button", { name: /seguridad/i })).toBeInTheDocument();
  });
});
