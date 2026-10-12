import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ api: { get: vi.fn() } }));

import { api } from "@/lib/api";
import SelectorBusqueda from "./SelectorBusqueda";

const ITEMS = [
  { id: "a", nombre: "Arroz" },
  { id: "b", nombre: "Barra" },
  { id: "c", nombre: "Café" },
];

/** Abre el selector con el foco y deja correr su retardo de 250 ms. */
async function abrir(campo) {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    act(() => campo.focus());
    await act(() => vi.runOnlyPendingTimersAsync());
  } finally {
    vi.useRealTimers();
  }
}

describe("SelectorBusqueda: combobox accesible (ARIA 1.2)", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockResolvedValue({ data: { items: ITEMS } });
  });

  it("el input es un combobox con nombre, que controla un listbox con nombre y opciones directas", async () => {
    render(<SelectorBusqueda url="/x" valor={null} onCambiar={() => {}} etiqueta="Proveedor" />);
    const campo = screen.getByRole("combobox", { name: "Proveedor" });
    expect(campo).toHaveAttribute("aria-expanded", "false");
    await abrir(campo);

    expect(campo).toHaveAttribute("aria-expanded", "true");
    const lista = screen.getByRole("listbox", { name: "Proveedor" });
    expect(campo).toHaveAttribute("aria-controls", lista.id);
    const opciones = screen.getAllByRole("option");
    expect(opciones).toHaveLength(3);
    // Cada opción es hija DIRECTA del listbox y no es un botón con foco propio.
    for (const o of opciones) {
      expect(o.parentElement).toBe(lista);
      expect(o.tagName).toBe("LI");
    }
  });

  it("↓/↑ mueven la opción activa (aria-activedescendant), Enter elige y Escape cierra", async () => {
    const onCambiar = vi.fn();
    render(<SelectorBusqueda url="/x" valor={null} onCambiar={onCambiar} etiqueta="Proveedor" />);
    const campo = screen.getByRole("combobox");
    await abrir(campo);

    fireEvent.keyDown(campo, { key: "ArrowDown" });
    expect(campo).toHaveAttribute("aria-activedescendant", screen.getByRole("option", { name: "Arroz" }).id);
    fireEvent.keyDown(campo, { key: "ArrowDown" });
    fireEvent.keyDown(campo, { key: "ArrowUp" });
    fireEvent.keyDown(campo, { key: "ArrowUp" });
    // Da la vuelta: desde la primera, ↑ va a la última.
    expect(campo).toHaveAttribute("aria-activedescendant", screen.getByRole("option", { name: "Café" }).id);
    fireEvent.keyDown(campo, { key: "Enter" });
    expect(onCambiar).toHaveBeenCalledWith(ITEMS[2]);
  });

  it("Escape cierra la lista sin elegir nada", async () => {
    const onCambiar = vi.fn();
    render(<SelectorBusqueda url="/x" valor={null} onCambiar={onCambiar} etiqueta="Proveedor" />);
    const campo = screen.getByRole("combobox");
    await abrir(campo);
    fireEvent.keyDown(campo, { key: "Escape" });
    expect(campo).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(onCambiar).not.toHaveBeenCalled();
  });

  it("'Sin resultados' se anuncia en una región de estado, fuera del listbox", async () => {
    api.get.mockResolvedValue({ data: { items: [] } });
    render(<SelectorBusqueda url="/x" valor={null} onCambiar={() => {}} etiqueta="Proveedor" />);
    await abrir(screen.getByRole("combobox"));
    expect(screen.getByRole("status")).toHaveTextContent("Sin resultados");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("el error se asocia al campo y se anuncia", async () => {
    render(<SelectorBusqueda url="/x" valor={null} onCambiar={() => {}} etiqueta="Proveedor" error="Elige un proveedor" />);
    const campo = screen.getByRole("combobox");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("Elige un proveedor");
    expect(screen.getByRole("alert")).toHaveTextContent("Elige un proveedor");
  });
});
