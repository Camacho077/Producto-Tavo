import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import PieLegal from "@/components/PieLegal";
import { EMPRESA } from "@/config/empresa";
import { VERSIONES_LEGALES } from "@/config/legal";
import { PoliticaDatosPage, TerminosPage } from "@/modules/legal/LegalPage";
import { rellenar } from "@/modules/legal/markdown";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const leer = (ruta) => readFileSync(path.join(AQUI, ruta), "utf8");

const ver = (Pagina) =>
  render(
    <MemoryRouter>
      <Pagina />
    </MemoryRouter>
  );

describe("documentos legales (Fase 6, 2026-09-30)", () => {
  it("las versiones del frontend son las mismas que guarda el backend", () => {
    const backend = leer("../../../../backend/app/core/legal.py");
    for (const [clave, version] of Object.entries(VERSIONES_LEGALES)) {
      const constante = clave === "politica_datos" ? "POLITICA_DATOS" : "TERMINOS";
      expect(backend).toMatch(new RegExp(`${constante}:\\s*"${version.replace(/\./g, "\\.")}"`));
    }
  });

  it.each([
    ["Política", PoliticaDatosPage, "politica_datos", /Política de tratamiento de datos personales/],
    ["Términos", TerminosPage, "terminos", /Términos y condiciones del servicio/],
  ])("%s: se lee como BORRADOR, con su versión y los datos de la empresa", (_, Pagina, clave, titulo) => {
    ver(Pagina);
    expect(screen.getByRole("heading", { level: 1, name: titulo })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/BORRADOR PENDIENTE DE REVISIÓN POR ABOGADO/);
    expect(document.body).toHaveTextContent(`Versión ${VERSIONES_LEGALES[clave]}`);
    expect(document.body).toHaveTextContent(EMPRESA.nit);
    // Ningún marcador {{campo}} sin reemplazar.
    expect(document.body.textContent).not.toMatch(/\{\{\w+\}\}/);
  });

  it("la política cubre lo que exige la ley: roles, derechos, plazos, canal y almacenamiento del navegador", () => {
    const texto = rellenar(leer("textos/politica-datos.md"), EMPRESA);
    for (const obligatorio of [
      "Ley Estatutaria 1581 de 2012",
      "Decreto 1377 de 2013",
      "Como Responsable",
      "Como Encargado",
      "Conocer, actualizar y rectificar",
      "Revocar la autorización y/o solicitar la supresión",
      "diez (10) días hábiles",
      "quince (15) días hábiles",
      "js_company_token",
      "js_company_modo",
      "no usa cookies",
      EMPRESA.correoDatos,
    ]) {
      expect(texto, obligatorio).toContain(obligatorio);
    }
  });

  it("los términos cubren alcance, planes, pagos, cancelación, disponibilidad, soporte, propiedad, portabilidad y responsabilidad", () => {
    const texto = leer("textos/terminos.md");
    for (const seccion of [
      "Alcance del servicio",
      "Planes",
      "Pagos",
      "Cancelación y reembolsos",
      "Disponibilidad",
      "Soporte",
      "Propiedad de los datos",
      "Portabilidad y terminación",
      "Limitación de responsabilidad",
    ]) {
      expect(texto).toMatch(new RegExp(`^## \\d+\\. ${seccion}`, "m"));
    }
    expect(texto).toContain("son del Cliente");
  });

  it("el pie muestra nombre, NIT, correo y ciudad, y enlaza a los dos documentos", () => {
    ver(PieLegal);
    const pie = screen.getByRole("contentinfo");
    for (const dato of [EMPRESA.razonSocial, `NIT ${EMPRESA.nit}`, EMPRESA.correo, EMPRESA.ciudad]) {
      expect(pie).toHaveTextContent(dato);
    }
    expect(screen.getByRole("link", { name: "Política de tratamiento de datos" })).toHaveAttribute("href", "/legal/privacidad");
    expect(screen.getByRole("link", { name: "Términos y condiciones" })).toHaveAttribute("href", "/legal/terminos");
  });
});
