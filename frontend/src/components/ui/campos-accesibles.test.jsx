import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/pdf", () => ({ abrirPdf: vi.fn() }));

import BotonPdf from "@/components/BotonPdf";
import FormularioPantalla from "@/components/FormularioPantalla";
import { Input, Select, Textarea } from "@/components/ui";

/**
 * Fase 5 (2026-09-30): cada campo está asociado a su etiqueta, su ayuda y su
 * error, y los errores se anuncian. Protege contra volver a perder
 * aria-describedby en Select/Textarea o a anunciar el contador en cada tecla.
 */
describe("campos accesibles", () => {
  it("Input: la ayuda describe el campo; con error, lo describe el error y se anuncia", () => {
    const { rerender } = render(<Input etiqueta="Teléfono" ayuda="Celular (3…) o fijo (60…)" value="" onChange={() => {}} />);
    const campo = screen.getByRole("textbox", { name: "Teléfono" });
    expect(campo).toHaveAccessibleDescription("Celular (3…) o fijo (60…)");

    rerender(<Input etiqueta="Teléfono" ayuda="Celular (3…) o fijo (60…)" error="Teléfono inválido" value="" onChange={() => {}} />);
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("Teléfono inválido");
    expect(screen.getByRole("alert")).toHaveTextContent("Teléfono inválido");
  });

  it("Select: igual que Input (antes no tenía aria-describedby)", () => {
    const { rerender } = render(
      <Select etiqueta="Prioridad" ayuda="Define el orden de atención">
        <option>Alta</option>
      </Select>
    );
    const campo = screen.getByRole("combobox", { name: "Prioridad" });
    expect(campo).toHaveAccessibleDescription("Define el orden de atención");
    rerender(
      <Select etiqueta="Prioridad" error="Elige una prioridad">
        <option>Alta</option>
      </Select>
    );
    expect(campo).toHaveAccessibleDescription("Elige una prioridad");
    expect(screen.getByRole("alert")).toHaveTextContent("Elige una prioridad");
  });

  it("Textarea: ayuda y contador en la descripción; el contador no es región viva y el tope se anuncia una vez", () => {
    const { rerender } = render(<Textarea etiqueta="Notas" ayuda="Opcional" maxLength={10} value="hola" onChange={() => {}} />);
    const campo = screen.getByRole("textbox", { name: "Notas" });
    expect(campo).toHaveAccessibleDescription("Opcional 4 de 10 caracteres");
    expect(document.querySelector("[aria-live]")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("");

    rerender(<Textarea etiqueta="Notas" ayuda="Opcional" maxLength={10} value="0123456789" onChange={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Llegaste al máximo de 10 caracteres.");
  });

  it("BotonPdf: con texto visible, ese texto ES su nombre (WCAG 2.5.3); sin texto, 'Descargar PDF'", () => {
    const { rerender } = render(<BotonPdf url="/x" nombreArchivo="a.pdf" texto="Ver factura PDF" />);
    expect(screen.getByRole("button", { name: "Ver factura PDF" })).toBeInTheDocument();
    rerender(<BotonPdf url="/x" nombreArchivo="a.pdf" />);
    expect(screen.getByRole("button", { name: "Descargar PDF" })).toBeInTheDocument();
  });

  it("FormularioPantalla: el error general (p. ej. stock insuficiente) se anuncia", () => {
    render(
      <MemoryRouter>
        <FormularioPantalla volver="/" onSubmit={() => {}} errorGeneral="Stock insuficiente para 'Arroz': disponible 2, solicitado 5.">
          <p>campos</p>
        </FormularioPantalla>
      </MemoryRouter>
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Stock insuficiente para 'Arroz'");
  });
});
