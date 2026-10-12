import { afterEach, describe, expect, it, vi } from "vitest";

import { MSG, digitoVerificacionNit, errorDocumento, errorNit, esquemas, formatoNit } from "@/lib/validaciones";

describe("NIT colombiano", () => {
  it.each([
    ["890903938", 8],
    ["890904996", 1],
    ["899999068", 1],
    ["800197268", 4],
  ])("calcula el dígito de verificación de %s (mismo algoritmo que el backend)", (base, dv) => {
    expect(digitoVerificacionNit(base)).toBe(dv);
  });

  it("rechaza un dígito de verificación incorrecto con mensaje claro", () => {
    expect(errorNit("890903938-1")).toContain("debería ser 8");
    expect(errorNit("890903938-8")).toBeNull();
    expect(errorNit("abc")).toBe(MSG.nitFormato);
  });

  it("la máscara inserta el guion antes del último dígito", () => {
    expect(formatoNit("8909039388")).toBe("890903938-8");
    expect(formatoNit("8909")).toBe("8909");
  });
});

describe("Documentos por tipo", () => {
  it.each([
    ["CC", "1020304050", null],
    ["CC", "123", "La cédula de ciudadanía tiene entre 6 y 10 dígitos"],
    ["CE", "1234567", null],
    ["PA", "AB123456", null],
    ["TI", "1000123456", null],
    ["TI", "12", "La tarjeta de identidad tiene 10 u 11 dígitos"],
  ])("%s %s", (tipo, numero, esperado) => {
    expect(errorDocumento(tipo, numero)).toBe(esperado);
  });
});

describe("Esquemas espejo del backend", () => {
  const ok = (esquema, valor) => esquema.safeParse(valor).success;
  const mensaje = (esquema, valor) => esquema.safeParse(valor).error?.issues[0].message;

  it("nombre de persona: solo letras, tildes y apóstrofes", () => {
    expect(ok(esquemas.nombrePersona(), "Ana O'Neil Pérez")).toBe(true);
    expect(mensaje(esquemas.nombrePersona(), "Ana 123")).toBe(MSG.nombrePersona);
    expect(mensaje(esquemas.nombrePersona(), "A")).toBe(MSG.nombrePersona);
    expect(mensaje(esquemas.nombrePersona(), "")).toBe(MSG.obligatorio);
  });

  it("nombre de ítem (producto, categoría, marca, razón social): solo letras, sin dígitos ni símbolos", () => {
    expect(ok(esquemas.nombreItem(), "Taladro Percutor Ñandú D'Alba")).toBe(true);
    expect(mensaje(esquemas.nombreItem(), "Taladro 650W")).toBe(MSG.nombreItem);
    expect(mensaje(esquemas.nombreItem(), "Ferretería & Cía")).toBe(MSG.nombreItem);
    expect(mensaje(esquemas.nombreItem(), " Taladro")).toBe(MSG.nombreItem);
    expect(mensaje(esquemas.nombreItem(), "Taladro <script>")).toBe(MSG.nombreItem);
  });

  it("correo: formato real y normalizado a minúsculas", () => {
    const r = esquemas.email().safeParse("  Ana.Perez@Empresa.COM ");
    expect(r.success).toBe(true);
    expect(r.data).toBe("ana.perez@empresa.com");
    expect(mensaje(esquemas.email(), "ana@empresa")).toBe(MSG.email);
    expect(mensaje(esquemas.email(), "ana@@empresa.com")).toBe(MSG.email);
  });

  it("teléfono colombiano: celular 3xxxxxxxxx o fijo 60xxxxxxxx", () => {
    expect(ok(esquemas.telefono(), "3001234567")).toBe(true);
    expect(ok(esquemas.telefono(), "6012345678")).toBe(true);
    expect(ok(esquemas.telefono(), "")).toBe(true);
    expect(mensaje(esquemas.telefono(), "2001234567")).toBe(MSG.telefono);
  });

  it("precio: positivo, 2 decimales, con tope", () => {
    expect(ok(esquemas.precio(), "1250.50")).toBe(true);
    expect(mensaje(esquemas.precio(), "0")).toBe(MSG.precio);
    expect(mensaje(esquemas.precio(), "-5")).toBe(MSG.precio);
    expect(mensaje(esquemas.precio(), "1.234")).toBe(MSG.precio);
    expect(mensaje(esquemas.precio(), "1000000000")).toBe(MSG.precio);
  });

  it("entero con rango y porcentaje 0-100", () => {
    expect(ok(esquemas.entero(0, 100), "50")).toBe(true);
    expect(mensaje(esquemas.entero(0, 100), "-1")).toBe(MSG.entero(0, 100));
    expect(mensaje(esquemas.entero(0, 100), "1.5")).toBe(MSG.entero(0, 100));
    expect(ok(esquemas.porcentaje(), "100")).toBe(true);
    expect(mensaje(esquemas.porcentaje(), "101")).toBe(MSG.porcentaje);
  });

  describe("fechas: 'hoy' es el día de Colombia, no el de UTC", () => {
    // Las fechas llevan desfase explícito para que el resultado no dependa de la
    // zona de la máquina que corre las pruebas.
    afterEach(() => vi.useRealTimers());

    it.each([
      ["noche (UTC ya va en el día siguiente)", "2026-09-28T20:30:00-05:00"],
      ["mañana del mismo día", "2026-09-28T08:00:00-05:00"],
    ])("%s", (_, ahora) => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(ahora));

      expect(mensaje(esquemas.fechaNoFutura(), "2026-09-29T09:00:00-05:00")).toBe(MSG.fechaFutura);
      expect(ok(esquemas.fechaNoFutura(), "2026-09-28T07:00:00-05:00")).toBe(true);

      // Ayer en Colombia: rechazada aunque en UTC ya sea el 28.
      expect(mensaje(esquemas.fechaNoPasada(), "2026-09-27T21:00:00-05:00")).toBe(MSG.entregaPasada);
      // Hoy a primera hora: aceptada aunque en UTC (de noche) ya sea el 29.
      expect(ok(esquemas.fechaNoPasada(), "2026-09-28T00:00:00-05:00")).toBe(true);
      expect(ok(esquemas.fechaNoPasada(), "2026-09-29T09:00:00-05:00")).toBe(true);
      expect(mensaje(esquemas.fechaNoPasada(), "no es fecha")).toBe(MSG.entregaPasada);
    });
  });
});
