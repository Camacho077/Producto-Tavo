import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * DISEÑO DE LAS PANTALLAS DE ACCESO (decisión del 2026-09-30): fondo negro
 * sólido, esquema oscuro forzado, panel centrado en la mitad de la pantalla
 * y totalmente transparente (sin marco, borde, fondo ni sombra), sin foto.
 */
const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const leer = (ruta) => readFileSync(path.join(RAIZ, ruta), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
// La regla cuyo selector es EXACTAMENTE `selector` (al inicio de línea), no
// cualquier otra que lo contenga, como `.auth > .auth__panel`.
const regla = (css, selector) =>
  new RegExp(`^\\s*${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`, "m").exec(css)?.[1] ?? "";

describe("pantallas de acceso", () => {
  const css = leer("src/components/auth/auth.css");

  it("el panel es transparente: sin fondo, sin borde, sin sombra", () => {
    const panel = regla(css, ".auth__panel");
    expect(panel).toMatch(/background:\s*none/);
    expect(panel).toMatch(/border:\s*0/);
    expect(panel).toMatch(/box-shadow:\s*none/);
  });

  it("el panel va centrado en la mitad de la pantalla, en una sola columna, con el pie legal abajo", () => {
    // Filas 1fr | panel | 1fr: con sitio, las de los extremos miden lo mismo y
    // el panel queda en la mitad exacta (medido ΔY=0); el pie va en la de
    // abajo, así nunca tapa el panel (2026-09-30).
    const auth = regla(css, ".auth");
    expect(auth).toMatch(/display:\s*grid/);
    expect(auth).toMatch(/grid-template-rows:\s*1fr auto 1fr/);
    expect(auth).toMatch(/justify-items:\s*center/);
    expect(auth).toMatch(/background-color:\s*var\(--fondo\)/);
    expect(regla(css, ".auth > .auth__panel")).toMatch(/grid-row:\s*2/);
    expect(regla(css, ".auth__pie-legal")).toMatch(/grid-row:\s*3/);
    expect(regla(css, ".auth__pie-legal")).not.toMatch(/position:\s*absolute/);
    expect(css).not.toMatch(/grid-template-columns/);
  });

  it("login y registro fuerzan el esquema oscuro y ya no pintan la foto", () => {
    for (const pagina of ["src/modules/auth/LoginPage.jsx", "src/modules/auth/RegistroPage.jsx"]) {
      const jsx = readFileSync(path.join(RAIZ, pagina), "utf8");
      expect(jsx).toContain('className="auth esquema-oscuro"');
      expect(jsx).not.toMatch(/FondoAuth|fondo-auth|<img/);
    }
  });

  it("el esquema oscuro forzado reusa los roles del modo oscuro (ningún color nuevo)", () => {
    const base = readFileSync(path.join(RAIZ, "src/index.css"), "utf8");
    // Desde la paleta monocromática (2026-10-01) `:root` sin atributo es el
    // claro; el bloque del oscuro es el que comparte con `.esquema-oscuro`.
    expect(base).toContain(':root[data-theme="oscuro"],\n.esquema-oscuro {');
    expect(base).toContain(":root,\n.esquema-oscuro {\n  --acento:");
  });
});
