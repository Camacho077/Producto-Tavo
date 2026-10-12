import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { extraerMensaje } from "@/hooks/useApiResource";
import { api } from "@/lib/api";

/**
 * AVISOS DEL NEGOCIO, COMPARTIDOS (2026-10-01).
 *
 * La barra superior (píldoras de estado), el sidebar (badges numéricos) y el
 * panel de avisos del dashboard leen el MISMO /dashboard/avisos. Si cada uno
 * lo pidiera por su lado, abrir el dashboard costaría dos peticiones iguales.
 * Aquí se pide una vez por carga del marco y se reparte; `pedir()` reutiliza
 * la petición en vuelo (StrictMode dispara los efectos dos veces) y no repite
 * una respuesta de hace menos de REUSO_MS.
 *
 * Es solo lectura de un endpoint que ya existía: el backend no cambia. Sin el
 * permiso dashboard:ver no se pide (el backend respondería 403).
 */
const REUSO_MS = 2000;

const AvisosContext = createContext(null);

export function AvisosProvider({ habilitado = true, children }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const enVuelo = useRef(null);
  const ultima = useRef(0);

  const pedir = useCallback(() => {
    if (!habilitado) return null;
    if (enVuelo.current) return enVuelo.current;
    if (Date.now() - ultima.current < REUSO_MS) return null;
    enVuelo.current = api
      .get("/dashboard/avisos")
      .then((res) => {
        setData(res.data);
        setError(null);
      })
      .catch((err) => setError(extraerMensaje(err)))
      .finally(() => {
        enVuelo.current = null;
        ultima.current = Date.now();
      });
    return enVuelo.current;
  }, [habilitado]);

  useEffect(() => {
    pedir();
  }, [pedir]);

  const valor = useMemo(() => ({ data, error, pedir }), [data, error, pedir]);
  return <AvisosContext.Provider value={valor}>{children}</AvisosContext.Provider>;
}

/** Los avisos compartidos, o null fuera del marco (pruebas de una pantalla suelta). */
export function useAvisos() {
  return useContext(AvisosContext);
}

/**
 * Cifra de un aviso que cuenta cosas ("3 productos bajo el mínimo"): los
 * títulos de esas reglas empiezan por la cantidad (backend, avisos.py).
 */
function cantidadDe(aviso) {
  const m = /^(\d+)\s/.exec(aviso?.titulo ?? "");
  return m ? Number(m[1]) : 0;
}

/** Qué avisos suman en el badge de cada submódulo del sidebar. */
const AVISOS_POR_MODULO = {
  productos: ["stock_agotado", "stock_bajo"],
  pedidos: ["pedidos_estancados"],
};

/** {clave de módulo: número} para los badges del sidebar (solo los > 0). */
export function badgesDeAvisos(avisos = []) {
  const res = {};
  for (const [modulo, claves] of Object.entries(AVISOS_POR_MODULO)) {
    const n = avisos.filter((a) => claves.includes(a.clave)).reduce((s, a) => s + cantidadDe(a), 0);
    if (n > 0) res[modulo] = n;
  }
  return res;
}

/** Avisos que piden atención (crítico o advertencia), para la barra superior. */
export function avisosDeEstado(avisos = []) {
  return avisos.filter((a) => a.nivel === "critico" || a.nivel === "advertencia");
}
