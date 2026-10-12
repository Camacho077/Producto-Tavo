import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {
    defaults: { baseURL: "http://localhost:8002/api/v1" },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import Aviso from "@/components/ui/Aviso";
import { AvisoProvider, DURACION_MS, SALIDA_MS, useAviso } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { mensajeDeError } from "@/lib/errores";
import { CategoriasLista } from "@/modules/carta/CategoriasPage";
import { ConSesion } from "@/test/sesion";

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 10, paginas: 1 } });

/** Error de axios tal como llega desde el backend. */
const errorHttp = (status, data) => Object.assign(new Error("http"), { response: { status, data } });

function Disparador() {
  const { exito, error } = useAviso();
  return (
    <>
      <button type="button" onClick={() => exito("Categoría creada")}>
        éxito
      </button>
      <button type="button" onClick={() => error("No se puede eliminar la categoría Celulares: tiene 3 productos asociados.")}>
        error
      </button>
    </>
  );
}

function montarAlertas() {
  return render(
    <AvisoProvider>
      <Aviso />
      <Disparador />
    </AvisoProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("Alertas — apariencia y accesibilidad", () => {
  it("el éxito es role=status y el error role=alert, cada uno con su color", () => {
    montarAlertas();
    fireEvent.click(screen.getByRole("button", { name: "éxito" }));
    fireEvent.click(screen.getByRole("button", { name: "error" }));

    const ok = screen.getByRole("status");
    expect(ok).toHaveTextContent("Categoría creada");
    expect(ok).toHaveClass("alerta--exito");

    const mal = screen.getByRole("alert");
    expect(mal).toHaveTextContent("No se puede eliminar la categoría Celulares: tiene 3 productos asociados.");
    expect(mal).toHaveClass("alerta--error");
  });

  it("varias alertas se apilan en orden de llegada", () => {
    montarAlertas();
    fireEvent.click(screen.getByRole("button", { name: "éxito" }));
    fireEvent.click(screen.getByRole("button", { name: "error" }));
    fireEvent.click(screen.getByRole("button", { name: "éxito" }));

    const pila = document.querySelectorAll(".alerta");
    expect(pila).toHaveLength(3);
    expect(pila[0]).toHaveClass("alerta--exito");
    expect(pila[1]).toHaveClass("alerta--error");
    expect(pila[2]).toHaveClass("alerta--exito");
  });

  it("se puede cerrar a mano", async () => {
    montarAlertas();
    fireEvent.click(screen.getByRole("button", { name: "éxito" }));
    fireEvent.click(screen.getByRole("button", { name: "Cerrar alerta" }));
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });
});

describe("Alertas — cierre automático", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("el éxito se cierra a los 4 s y el error aguanta hasta los 7 s", () => {
    montarAlertas();
    fireEvent.click(screen.getByRole("button", { name: "éxito" }));
    fireEvent.click(screen.getByRole("button", { name: "error" }));
    expect(DURACION_MS).toEqual({ exito: 4000, error: 7000 });

    // A los 4 s + el fade: el éxito ya no está, el error sigue legible.
    act(() => vi.advanceTimersByTime(DURACION_MS.exito + SALIDA_MS));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(DURACION_MS.error - DURACION_MS.exito + SALIDA_MS));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("el fade de salida no la quita antes de tiempo (sin parpadeo)", () => {
    montarAlertas();
    fireEvent.click(screen.getByRole("button", { name: "éxito" }));

    act(() => vi.advanceTimersByTime(DURACION_MS.exito));
    const saliendo = screen.getByRole("status");
    expect(saliendo).toHaveClass("alerta--saliendo");
    expect(saliendo).toHaveTextContent("Categoría creada");

    act(() => vi.advanceTimersByTime(SALIDA_MS));
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("Alertas de error — dicen el porqué que devuelve el backend", () => {
  it("muestra tal cual el detail del backend, sin resumirlo", () => {
    const causa = "No se pudo completar la venta VEN-000012: el producto Iphone 18 Pro Max solo tiene 2 unidades y se pidieron 5.";
    expect(mensajeDeError(errorHttp(409, { detail: causa }), "registrar la venta")).toBe(causa);
  });

  it("los 422 se arman campo por campo, no con un genérico", () => {
    const err = errorHttp(422, {
      detail: "Los datos enviados no son válidos",
      errores: [{ campo: "cliente_nombre", mensaje: "Es demasiado corto" }],
    });
    expect(mensajeDeError(err, "registrar la venta")).toBe("No se pudo registrar la venta: Cliente nombre: Es demasiado corto");
  });

  it("sin respuesta del servidor dice la causa real y a qué dirección no llegó", () => {
    const texto = mensajeDeError(Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" }), "eliminar la categoría");
    expect(texto).toContain("no hay conexión con el servidor");
    expect(texto).toContain("http://localhost:8002/api/v1");
  });

  it("nunca devuelve el genérico prohibido, ni siquiera sin datos utilizables", () => {
    for (const err of [errorHttp(500, {}), errorHttp(404, null), errorHttp(403, { detail: "  " })]) {
      const texto = mensajeDeError(err, "guardar el producto");
      expect(texto.toLowerCase()).not.toContain("no se pudo completar la operación");
      expect(texto.length).toBeGreaterThan(20);
    }
  });
});

describe("Alertas conectadas a una pantalla real", () => {
  function montarListado() {
    return render(
      <MemoryRouter initialEntries={["/carta/categorias"]}><ConSesion>
        <AvisoProvider>
          <Aviso />
          <Routes>
            <Route path="/carta/categorias" element={<CategoriasLista />} />
          </Routes>
        </AvisoProvider>
      </ConSesion></MemoryRouter>
    );
  }

  it("eliminar con éxito deja la alerta verde; el 409 deja la roja con la causa del backend", async () => {
    api.get.mockResolvedValue(PAGINA([{ id: "1", nombre: "Celulares", descripcion: null, activo: true, productos_count: 3 }]));
    api.delete.mockRejectedValueOnce(
      errorHttp(409, { detail: "No se puede eliminar la categoría Celulares: tiene 3 productos asociados. Puedes desactivarla en su lugar para conservar el historial." })
    );
    montarListado();

    // El botón de la fila abre el diálogo; el de confirmar vive dentro de él.
    fireEvent.click((await screen.findAllByRole("button", { name: "Eliminar" }))[0]);
    const dialogo = await screen.findByRole("dialog");
    fireEvent.click(within(dialogo).getByRole("button", { name: "Eliminar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("No se puede eliminar la categoría Celulares: tiene 3 productos asociados.");

    // Tras el fallo el diálogo sigue abierto para reintentar o cancelar.
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    api.delete.mockResolvedValueOnce({});
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Eliminar" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Celulares eliminada");
  });
});
