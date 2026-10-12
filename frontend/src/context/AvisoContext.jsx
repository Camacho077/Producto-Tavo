import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const AvisoContext = createContext(null);

// Una alerta de éxito se lee de un vistazo; una de error hay que leerla
// entera (trae la causa concreta), por eso dura más.
export const DURACION_MS = { exito: 4000, error: 7000 };
// Lo que dura el fade de salida en CSS (.alerta--saliendo). Debe coincidir
// con --duracion-alerta en pantallas.css.
export const SALIDA_MS = 180;

/**
 * Sistema único de alertas del producto: una pila de avisos arriba a la
 * derecha, verde para éxito y rojo para error. Se cierran solas (4 s las de
 * éxito, 7 s las de error) o a mano.
 *
 * Los errores NUNCA se resumen: el texto que llega es el que devolvió el
 * backend con la causa concreta (ver lib/errores.js).
 */
export function AvisoProvider({ children }) {
  const [alertas, setAlertas] = useState([]);
  // Un temporizador por alerta: el cierre automático y el de salida.
  const temporizadores = useRef(new Map());
  const siguienteId = useRef(0);

  const olvidar = useCallback((id) => {
    const pendientes = temporizadores.current.get(id);
    if (pendientes) pendientes.forEach(clearTimeout);
    temporizadores.current.delete(id);
  }, []);

  /** Marca la alerta como saliendo (fade) y la quita cuando termina. */
  const cerrar = useCallback(
    (id) => {
      olvidar(id);
      setAlertas((previas) => previas.map((a) => (a.id === id ? { ...a, saliendo: true } : a)));
      const salida = setTimeout(() => setAlertas((previas) => previas.filter((a) => a.id !== id)), SALIDA_MS);
      temporizadores.current.set(id, [salida]);
    },
    [olvidar]
  );

  const mostrar = useCallback(
    (texto, tipo = "exito") => {
      if (!texto) return undefined;
      const id = ++siguienteId.current;
      setAlertas((previas) => [...previas, { id, texto, tipo, saliendo: false }]);
      const auto = setTimeout(() => cerrar(id), DURACION_MS[tipo] ?? DURACION_MS.exito);
      temporizadores.current.set(id, [auto]);
      return id;
    },
    [cerrar]
  );

  useEffect(() => {
    const pendientes = temporizadores.current;
    return () => pendientes.forEach((ids) => ids.forEach(clearTimeout));
  }, []);

  const valor = useMemo(
    () => ({
      alertas,
      mostrar,
      cerrar,
      exito: (texto) => mostrar(texto, "exito"),
      error: (texto) => mostrar(texto, "error"),
    }),
    [alertas, mostrar, cerrar]
  );

  return <AvisoContext.Provider value={valor}>{children}</AvisoContext.Provider>;
}

export function useAviso() {
  const ctx = useContext(AvisoContext);
  if (!ctx) throw new Error("useAviso debe usarse dentro de un AvisoProvider");
  return ctx;
}
