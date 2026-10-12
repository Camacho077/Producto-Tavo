import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Button from "@/components/ui/Button";

describe("Button", () => {
  it("usa la variante primaria y el tamaño md por defecto", () => {
    render(<Button>Guardar</Button>);
    const boton = screen.getByRole("button", { name: "Guardar" });

    expect(boton).toHaveClass("btn", "btn--primario", "btn--md");
  });

  it("aplica cada variante pedida", () => {
    const variantes = ["primario", "secundario", "terciario", "destructivo"];
    variantes.forEach((variante) => {
      const { unmount } = render(<Button variante={variante}>Acción</Button>);
      expect(screen.getByRole("button", { name: "Acción" })).toHaveClass(`btn--${variante}`);
      unmount();
    });
  });

  it("cuando está cargando queda deshabilitado, marca aria-busy y no dispara onClick", () => {
    const alHacerClic = vi.fn();
    render(
      <Button cargando onClick={alHacerClic}>
        Guardando...
      </Button>
    );
    const boton = screen.getByRole("button", { name: "Guardando..." });

    expect(boton).toBeDisabled();
    expect(boton).toHaveAttribute("aria-busy", "true");

    fireEvent.click(boton);
    expect(alHacerClic).not.toHaveBeenCalled();
  });

  it("deshabilitado no dispara onClick", () => {
    const alHacerClic = vi.fn();
    render(
      <Button disabled onClick={alHacerClic}>
        Bloqueado
      </Button>
    );

    fireEvent.click(screen.getByRole("button", { name: "Bloqueado" }));
    expect(alHacerClic).not.toHaveBeenCalled();
  });

  it("el spinner de carga es decorativo: no ensucia el nombre accesible", () => {
    render(<Button cargando>Ingresando...</Button>);

    // Si el spinner expusiera su propio rol/etiqueta, este query fallaría.
    expect(screen.getByRole("button", { name: "Ingresando..." })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("es un submit real cuando se le pide", () => {
    const alEnviar = vi.fn((e) => e.preventDefault());
    render(
      <form onSubmit={alEnviar}>
        <Button type="submit">Enviar</Button>
      </form>
    );

    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(alEnviar).toHaveBeenCalledTimes(1);
  });
});
