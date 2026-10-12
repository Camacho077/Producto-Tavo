import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import Input from "@/components/ui/Input";

function Campo({ permitir, inicial = "", maxLength }) {
  const [valor, setValor] = useState(inicial);
  return <Input etiqueta="Campo" permitir={permitir} value={valor} onChange={(e) => setValor(e.target.value)} maxLength={maxLength} />;
}

async function escribir(permitir, texto, inicial = "") {
  const usuario = userEvent.setup();
  render(<Campo permitir={permitir} inicial={inicial} />);
  const input = screen.getByLabelText("Campo");
  await usuario.click(input);
  await usuario.keyboard(texto);
  return { input, usuario };
}

describe("Bloqueo físico de entrada por tipo de campo", () => {
  it("nombre: dígitos y símbolos no producen nada; tildes, ñ, espacio y apóstrofe sí", async () => {
    const { input } = await escribir("nombre", "Ana 1M2a#r$ía O'Neil Ñ!");
    expect(input).toHaveValue("Ana María O'Neil Ñ");
  });

  it("entero: bloquea letras, signo menos y decimales", async () => {
    const { input } = await escribir("entero", "-1a5.7e+2");
    expect(input).toHaveValue("1572");
  });

  it("decimal: un solo separador, coma se vuelve punto, máximo 2 decimales, sin signo", async () => {
    const { input } = await escribir("decimal", "-12,50.99x");
    expect(input).toHaveValue("12.50");
  });

  it("digitos: solo números", async () => {
    const { input } = await escribir("digitos", "10-20a30");
    expect(input).toHaveValue("102030");
  });

  it("alfanumérico (pasaporte): letras y números en mayúsculas", async () => {
    const { input } = await escribir("alfanumerico", "ab-12 3");
    expect(input).toHaveValue("AB123");
  });

  it("teléfono: solo dígitos, máscara 300 123 4567 y tope de 10", async () => {
    const { input } = await escribir("telefono", "(300) 123-4567 99");
    expect(input).toHaveValue("300 123 4567");
  });

  it("NIT: solo dígitos y guion automático antes del dígito de verificación", async () => {
    const { input } = await escribir("nit", "890903938-8");
    expect(input).toHaveValue("890903938-8");
  });

  it("NIT corto todavía no lleva guion", async () => {
    const { input } = await escribir("nit", "8909");
    expect(input).toHaveValue("8909");
  });

  it("correo: bloquea espacios y caracteres ilegales, permite @ . - _ y pasa a minúsculas", async () => {
    const { input } = await escribir("correo", "Ana Pérez@Em presa.co!m");
    expect(input).toHaveValue("anaprez@empresa.com");
  });

  it("el pegado también se filtra", async () => {
    const usuario = userEvent.setup();
    render(<Campo permitir="entero" />);
    const input = screen.getByLabelText("Campo");
    await usuario.click(input);
    await usuario.paste("12ab-34.5");
    expect(input).toHaveValue("12345");
  });

  it("corregir una letra en la mitad del texto no mueve el cursor al final", async () => {
    const usuario = userEvent.setup();
    render(<Campo permitir="nombre" inicial="Mara" />);
    const input = screen.getByLabelText("Campo");
    await usuario.click(input);
    input.setSelectionRange(2, 2); // entre "Ma" y "ra"
    await usuario.keyboard("r9í"); // el 9 no debe entrar
    expect(input).toHaveValue("Maríra");
    expect(input.selectionStart).toBe(4); // justo después de "rí"
  });

  it("en un campo con máscara, borrar salta el separador", async () => {
    const usuario = userEvent.setup();
    render(<Campo permitir="telefono" inicial="300 123 4567" />);
    const input = screen.getByLabelText("Campo");
    await usuario.click(input);
    input.setSelectionRange(4, 4); // justo después del espacio "300 |123"
    await usuario.keyboard("{Backspace}");
    expect(input).toHaveValue("301 234 567");
    expect(input.selectionStart).toBe(2);
  });

  it("respeta maxLength aunque la inserción sea programática", async () => {
    const usuario = userEvent.setup();
    render(<Campo permitir="nombre" maxLength={5} />);
    const input = screen.getByLabelText("Campo");
    await usuario.click(input);
    await usuario.keyboard("Alejandro");
    expect(input).toHaveValue("Aleja");
  });
});
