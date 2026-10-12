import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Sin frontend/.env, api.js caía en silencio a un valor por defecto y el
// error aparecía después como ERR_CONNECTION_REFUSED o "CORS". Ahora
// `npm run dev` / `npm run build` se detienen con un mensaje que dice qué
// copiar. En las pruebas (mode "test") no se exige: no llaman a la API.
// La variable puede venir de un .env* o del entorno (Docker la pasa así).
export function exigirVariablesDeEntorno(raiz = __dirname) {
  return {
    name: 'exigir-variables-de-entorno',
    config(_config, { mode }) {
      if (mode === 'test') return
      const env = loadEnv(mode, raiz, 'VITE_')
      if (env.VITE_API_URL) return
      const hayEnv = fs.existsSync(path.join(raiz, '.env'))
      throw new Error(
        [
          '',
          '='.repeat(78),
          'ERROR DE CONFIGURACIÓN: falta VITE_API_URL (la URL de la API del backend).',
          '='.repeat(78),
          hayEnv
            ? 'frontend/.env existe pero no define VITE_API_URL. Compáralo con frontend/.env.example.'
            : 'No existe frontend/.env. Créalo a partir de la plantilla:',
          '    Windows (PowerShell):  Copy-Item frontend\\.env.example frontend\\.env',
          '    Linux / macOS:         cp frontend/.env.example frontend/.env',
          'O corre el arranque automático: .\\automatizaciones\\setup.ps1  (o ./automatizaciones/setup.sh)',
          '='.repeat(78),
        ].join('\n')
      )
    },
  }
}

// CONFIGURACIÓN CRÍTICA — NO ELIMINAR en limpiezas de código.
// Dominios de túnel para compartir la app por internet (ver
// automatizaciones/demo/start-demo-tunel.ps1 y "Compartir una demo por
// internet" en el README). El punto inicial acepta cualquier subdominio,
// así no hay que tocar esto cada vez que el túnel genere una URL nueva.
// Sin esto Vite responde "Blocked request. This host is not allowed".
const HOSTS_TUNEL = ['.loca.lt', '.ngrok-free.app', '.trycloudflare.com']

// https://vite.dev/config/
export default defineConfig({
  plugins: [exigirVariablesDeEntorno(), react(), tailwindcss()],
  esbuild: {
    jsx: "automatic",
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Separación de las librerías pesadas en paquetes propios: cuando se publica
  // una versión nueva, el navegador solo vuelve a bajar lo que cambió (React se
  // queda en caché entre despliegues).
  build: {
    rollupOptions: {
      output: {
        // Rolldown (Vite 8) espera una FUNCIÓN, no el objeto de Rollup:
        // con un objeto falla el build con "manualChunks is not a function".
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          // React y el router SÍ hacen falta desde el primer pintado, así
          // que tenerlos aparte no cuesta nada y el navegador los conserva
          // en caché entre despliegues.
          if (id.includes("react-router") || /node_modules[\/]react(-dom)?[\/]/.test(id) || id.includes("scheduler")) {
            return "vendor-react";
          }
          if (id.includes("zod")) return "vendor-validacion";
          // NADA MÁS lleva nombre de paquete fijo, a propósito. En cuanto se le
          // da uno, Vite lo mete en el <link rel="modulepreload"> del HTML y se
          // descarga hasta en la pantalla de inicio de sesión. Así se midió con
          // Recharts (109 kB comprimidos que no hacían falta para iniciar
          // sesión); Recharts ya no está en el proyecto —la gráfica del
          // dashboard es SVG propio, ver components/charts/GraficaRendimiento—
          // pero la regla sigue valiendo para la siguiente librería pesada:
          // déjala dentro de su import() dinámico y no la agrupes.
          return undefined;
        },
      },
    },
  },
  server: {
    host: true,
    // Puertos del Producto Tavo: 5175 (dev) y 4175 (preview). El 5173 y el
    // 4173 son del Producto JS, que corre a la vez en esta máquina (mapa en
    // docs/DECISIONES.md §1). CONFIGURACIÓN CRÍTICA: no se borra.
    port: 5175,
    // strictPort: si el 5175 está ocupado, Vite FALLA con un mensaje claro
    // en vez de saltar silenciosamente al siguiente puerto. Ese salto silencioso ya
    // rompió CORS varias veces sin avisar: el backend quedaba configurado
    // para un puerto y el navegador llamaba desde otro. Si falla acá, cierra
    // la instancia vieja de Vite (ver automatizaciones/dev/start-frontend.ps1).
    strictPort: true,
    allowedHosts: HOSTS_TUNEL,
  },
  // `vite preview` sirve la versión COMPILADA (dist/) con los tipos MIME
  // correctos: es lo que se expone por el túnel en las demos. Un servidor
  // de desarrollo por túnel sirve cientos de .jsx sueltos, el túnel les
  // pone text/plain y el navegador los bloquea (NS_ERROR_CORRUPTED_CONTENT).
  // Puerto 4175, ADICIONAL al 5175 de desarrollo (no lo reemplaza).
  preview: {
    host: true,
    port: 4175,
    strictPort: true,
    allowedHosts: HOSTS_TUNEL,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
    globals: true,
    // Medio procesador como máximo (2026-09-30): sin límite, en una máquina de
    // 16 núcleos arrancaban 15 workers de jsdom que se peleaban por disco y
    // CPU; la suite tardaba MÁS (18,6–19,7 s frente a 15,5–16,8 s, 3 corridas
    // de cada una) y en dos ocasiones tests sueltos pasaron de los 5 s.
    maxWorkers: "50%",
    // 15 s por prueba (2026-10-02; el valor por defecto de vitest es 5 s).
    // Varias pruebas teclean formularios completos tecla a tecla, como una
    // persona (~70 teclas pasan por el bloqueo de entrada y la validación).
    // Con la máquina ocupada por otros programas, la de proveedor persona
    // natural tardó 5,5 s SOLA y una corrida completa dio 13 "timed out in
    // 5000ms" en pruebas distintas cada vez. Un fallo real no se esconde con
    // esto: solo tarda más en reportarse.
    testTimeout: 15_000,
  },
})
