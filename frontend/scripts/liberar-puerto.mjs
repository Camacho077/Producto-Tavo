// Se ejecuta automáticamente antes de `npm run dev` (script "predev").
//
// Cierra cualquier proceso que siga escuchando en el puerto de Vite. Sin
// esto, una instancia vieja (una terminal olvidada, un proceso de
// verificación) deja el 5175 ocupado y, como vite.config.js usa strictPort,
// el nuevo `npm run dev` falla en vez de arrancar. Con esto el puerto es
// siempre el mismo y la página que abres es siempre la del código actual.
import { execSync } from "node:child_process";

const puerto = process.argv[2] || "5175";

function pidsEnPuertoWindows() {
  const salida = execSync("netstat -ano -p tcp", { encoding: "utf8" });
  const pids = new Set();
  for (const linea of salida.split(/\r?\n/)) {
    if (!/LISTENING/.test(linea)) continue;
    const columnas = linea.trim().split(/\s+/);
    const local = columnas[1] ?? "";
    if (local.endsWith(`:${puerto}`)) pids.add(columnas.at(-1));
  }
  return [...pids].filter((p) => p && p !== "0");
}

try {
  if (process.platform === "win32") {
    for (const pid of pidsEnPuertoWindows()) {
      try {
        execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
        console.log(`[predev] Cerrado proceso viejo en :${puerto} (PID ${pid})`);
      } catch {
        // ya no existe o no hay permisos: Vite avisará si el puerto sigue ocupado
      }
    }
  } else {
    execSync(`lsof -ti tcp:${puerto} | xargs -r kill -9`, { stdio: "ignore" });
  }
} catch {
  // netstat/lsof no disponibles: seguimos, strictPort avisará si hace falta
}
