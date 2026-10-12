import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { AvisoProvider } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { ProveedorDetalle, ProveedorNuevo, ProveedoresLista } from "@/modules/compras/ProveedoresPage";
import { ConSesion } from "@/test/sesion";

const PAGINA = (items) => ({ data: { items, total: items.length, pagina: 1, por_pagina: 10, paginas: 1 } });

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockResolvedValue(PAGINA([]));
});

function montar(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}><ConSesion>
      <AvisoProvider>
        <Routes>
          <Route path="/compras/proveedores" element={<ProveedoresLista />} />
          <Route path="/compras/proveedores/nuevo" element={<ProveedorNuevo />} />
          <Route path="/compras/proveedores/:id" element={<ProveedorDetalle />} />
        </Routes>
      </AvisoProvider>
    </ConSesion></MemoryRouter>
  );
}

// Sin pausa entre teclas: con el `delay: 0` por defecto, user-event cede un
// setTimeout en cada tecla (~23 ms por tecla contra ~8 ms, medido), y bajo la
// carga de la suite en paralelo esas esperas se alargan hasta el timeout de 5 s.
// Nada en `lib/entrada.js` ni en `useFormulario` depende de esa pausa.
const TECLEO = { delay: null };

const abrirNuevo = () => {
  montar("/compras/proveedores/nuevo");
  return screen;
};

describe("Proveedor nuevo — validación y formulario condicional", () => {
  it("es una pantalla propia con migas, no un diálogo", () => {
    const d = abrirNuevo();
    expect(d.getByRole("heading", { level: 1, name: "Nuevo proveedor" })).toBeInTheDocument();
    expect(d.queryByRole("dialog")).toBeNull();
    expect(d.getByRole("navigation", { name: "Ruta de navegación" })).toHaveTextContent("Proveedores");
  });

  it("valida al salir del campo, no en cada tecla, y deshabilita Guardar con errores", async () => {
    const usuario = userEvent.setup(TECLEO);
    const d = abrirNuevo();
    const nit = d.getByLabelText(/^NIT/);

    await usuario.click(nit);
    await usuario.keyboard("890903938-1");
    expect(d.queryByText(/debería ser 8/)).toBeNull();

    await usuario.tab();
    expect(await d.findByText(/debería ser 8/)).toBeInTheDocument();
    expect(nit).toHaveAttribute("aria-invalid", "true");
    expect(d.getByRole("button", { name: "Guardar" })).toBeDisabled();
    expect(d.getByText("Hay campos con errores")).toBeInTheDocument();
  });

  it("al enviar con errores lleva el foco al primer campo inválido y no llama al backend", async () => {
    const d = abrirNuevo();
    fireEvent.submit(document.querySelector("#form-proveedor"));
    await waitFor(() => expect(d.getByLabelText(/Razón social/)).toHaveFocus());
    expect(api.post).not.toHaveBeenCalled();
    expect(d.getAllByText("Este campo es obligatorio").length).toBeGreaterThan(0);
  });

  it("cambiar a persona natural muestra documento/nombres y limpia los campos de jurídica al enviar", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockResolvedValue({ data: { id: "1" } });
    const d = abrirNuevo();

    await usuario.type(d.getByLabelText(/Razón social/), "Empresa Fantasma");
    await usuario.selectOptions(d.getByLabelText(/Tipo de persona/), "natural");

    await waitFor(() => expect(d.queryByLabelText(/Razón social/)).toBeNull());
    await usuario.selectOptions(d.getByLabelText(/Tipo de documento/), "CC");
    await usuario.type(d.getByLabelText(/Número de documento/), "1020304050");
    await usuario.type(d.getByLabelText(/^Nombres/), "María José");
    await usuario.type(d.getByLabelText(/^Apellidos/), "Gómez Pérez");
    await usuario.type(d.getByLabelText(/Teléfono/), "300 123 4567");
    await usuario.click(d.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const cuerpo = api.post.mock.calls[0][1];
    expect(cuerpo).toMatchObject({
      tipo_persona: "natural",
      tipo_documento: "CC",
      numero_documento: "1020304050",
      nombres: "María José",
      apellidos: "Gómez Pérez",
      telefono: "3001234567",
      producto_ids: [],
    });
    expect(cuerpo).not.toHaveProperty("razon_social");
    expect(cuerpo).not.toHaveProperty("nit");
    // Al guardar vuelve al listado.
    expect(await d.findByRole("heading", { level: 1, name: "Proveedores" })).toBeInTheDocument();
  });

  it("el teléfono solo admite dígitos, se formatea solo y tope de 10", async () => {
    const usuario = userEvent.setup(TECLEO);
    const d = abrirNuevo();
    const tel = d.getByLabelText(/Teléfono/);
    await usuario.type(tel, "(300) 123-4567 99");
    expect(tel).toHaveValue("300 123 4567");
  });

  it("el NIT no admite letras y el nombre no admite dígitos (bloqueo al teclear)", async () => {
    const usuario = userEvent.setup(TECLEO);
    const d = abrirNuevo();
    await usuario.type(d.getByLabelText(/^NIT/), "89a0903938x8");
    expect(d.getByLabelText(/^NIT/)).toHaveValue("890903938-8");
    await usuario.type(d.getByLabelText(/Representante legal/), "Juan 123 Mora");
    expect(d.getByLabelText(/Representante legal/)).toHaveValue("Juan  Mora");
  });

  it("pinta bajo el campo los errores que devuelve el backend (422)", async () => {
    const usuario = userEvent.setup(TECLEO);
    api.post.mockRejectedValue({
      response: { status: 422, data: { detail: "Los datos enviados no son válidos", errores: [{ campo: "email", mensaje: "Ya existe un proveedor con ese correo" }] } },
    });
    const d = abrirNuevo();
    await usuario.type(d.getByLabelText(/Razón social/), "Distribuidora Andina");
    await usuario.type(d.getByLabelText(/^NIT/), "890903938-8");
    await usuario.type(d.getByLabelText(/Representante legal/), "Juan Mora");
    await usuario.type(d.getByLabelText(/Correo/), "ventas@andina.co");
    await usuario.click(d.getByRole("button", { name: "Guardar" }));

    expect(await d.findByText("Ya existe un proveedor con ese correo")).toBeInTheDocument();
    expect(d.getByLabelText(/Correo/)).toHaveFocus();
  });
});

describe("Proveedor nuevo — productos que surte (selector con búsqueda)", () => {
  it("busca productos en vivo, agrega fichas removibles y envía producto_ids", async () => {
    const usuario = userEvent.setup(TECLEO);
    const PRODUCTOS = [
      { id: "p1", nombre: "Martillo", sku: "MAR-1", stock: 0 },
      { id: "p2", nombre: "Taladro", sku: "TAL-1", stock: 0 },
    ];
    api.get.mockImplementation((url) => (url === "/compras/productos" ? Promise.resolve(PAGINA(PRODUCTOS)) : Promise.resolve(PAGINA([]))));
    api.post.mockResolvedValue({ data: { id: "1" } });
    const d = abrirNuevo();

    const buscador = d.getByLabelText("Buscar producto por nombre o SKU...");
    await usuario.click(buscador);
    expect(await d.findByRole("option", { name: /Martillo/ })).toBeInTheDocument();
    await usuario.click(d.getByRole("option", { name: /Martillo/ }));
    await usuario.click(d.getByRole("option", { name: /Taladro/ }));

    const fichas = d.getByRole("list", { name: "Elegidos" });
    expect(fichas).toHaveTextContent("Martillo");
    expect(fichas).toHaveTextContent("Taladro");
    expect(d.getByRole("option", { name: /Martillo/ })).toHaveAttribute("aria-disabled", "true");

    // Quitar uno no toca el otro.
    await usuario.click(d.getByRole("button", { name: "Quitar Taladro" }));
    expect(fichas).toHaveTextContent("Martillo");
    expect(fichas).not.toHaveTextContent("Taladro");

    await usuario.type(d.getByLabelText(/Razón social/), "Distribuidora Andina");
    await usuario.type(d.getByLabelText(/^NIT/), "890903938-8");
    await usuario.type(d.getByLabelText(/Representante legal/), "Juan Mora");
    await usuario.click(d.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post.mock.calls[0][1].producto_ids).toEqual(["p1"]);
  });
});

describe("Proveedor — detalle", () => {
  it("lista los productos que surte y enlaza a cada uno", async () => {
    api.get.mockResolvedValue({
      data: {
        id: "1",
        nombre: "Distribuidora Andina",
        tipo_persona: "juridica",
        razon_social: "Distribuidora Andina",
        nit: "890903938-8",
        activo: true,
        compras_count: 2,
        productos: [{ id: "p1", nombre: "Martillo", sku: "MAR-1", stock: 12 }],
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    montar("/compras/proveedores/1");
    expect(await screen.findByRole("heading", { level: 1, name: "Distribuidora Andina" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Martillo" })).toHaveAttribute("href", "/compras/productos/p1");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
