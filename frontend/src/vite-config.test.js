import { describe, expect, it } from "vitest";

import config from "../vite.config.js";

/**
 * Protección estructural de la configuración ACTIVA de vite.config.js
 * (ver "REGLA PERMANENTE" en CLAUDE.md): puertos fijos, strictPort y los
 * dominios de túnel con los que se comparte la demo por internet. Si una
 * limpieza los quita, este test falla antes de que vuelva a romperse CORS
 * o el túnel responda "Blocked request. This host is not allowed".
 */
const HOSTS_TUNEL = [".loca.lt", ".ngrok-free.app", ".trycloudflare.com"];

describe("vite.config.js — configuración activa", () => {
  it("desarrollo: puerto 5173 fijo con strictPort", () => {
    expect(config.server.port).toBe(5173);
    expect(config.server.strictPort).toBe(true);
  });

  it("preview (demo compilada por túnel): puerto 4173 fijo con strictPort", () => {
    expect(config.preview.port).toBe(4173);
    expect(config.preview.strictPort).toBe(true);
  });

  it("acepta cualquier subdominio de los túneles TANTO en server como en preview", () => {
    for (const host of HOSTS_TUNEL) {
      expect(config.server.allowedHosts, `server.allowedHosts debe incluir ${host}`).toContain(host);
      expect(config.preview.allowedHosts, `preview.allowedHosts debe incluir ${host}`).toContain(host);
      expect(host.startsWith("."), "el punto inicial es lo que acepta cualquier subdominio").toBe(true);
    }
  });
});

describe("vite.config.js — exige VITE_API_URL con un mensaje claro", () => {
  const conCarpeta = async (contenidoEnv, prueba) => {
    const fs = await import("fs");
    const os = await import("os");
    const path = await import("path");
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vite-env-"));
    if (contenidoEnv !== null) fs.writeFileSync(path.join(dir, ".env"), contenidoEnv);
    const anterior = process.env.VITE_API_URL;
    delete process.env.VITE_API_URL;
    try {
      await prueba(dir);
    } finally {
      if (anterior !== undefined) process.env.VITE_API_URL = anterior;
      fs.rmSync(dir, { recursive: true, force: true });
    }
  };

  it("sin frontend/.env detiene el arranque y dice qué archivo copiar", async () => {
    const { exigirVariablesDeEntorno } = await import("../vite.config.js");
    await conCarpeta(null, (dir) => {
      const plugin = exigirVariablesDeEntorno(dir);
      expect(() => plugin.config({}, { mode: "development" })).toThrow(/No existe frontend\/\.env/);
      expect(() => plugin.config({}, { mode: "development" })).toThrow(/cp frontend\/\.env\.example frontend\/\.env/);
    });
  });

  it("con .env sin la variable lo dice; con la variable pasa; en pruebas no se exige", async () => {
    const { exigirVariablesDeEntorno } = await import("../vite.config.js");
    await conCarpeta("OTRA=1\n", (dir) => {
      expect(() => exigirVariablesDeEntorno(dir).config({}, { mode: "development" })).toThrow(/no define VITE_API_URL/);
      expect(() => exigirVariablesDeEntorno(dir).config({}, { mode: "test" })).not.toThrow();
    });
    await conCarpeta("VITE_API_URL=http://localhost:8001/api/v1\n", (dir) => {
      expect(() => exigirVariablesDeEntorno(dir).config({}, { mode: "production" })).not.toThrow();
    });
  });
});
