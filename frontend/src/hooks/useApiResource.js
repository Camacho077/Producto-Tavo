import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const MENSAJE_ERROR_DEFAULT = "No se pudo cargar la información. Intenta de nuevo.";

function extraerMensaje(err) {
  const detalle = err.response?.data?.detail;
  if (typeof detalle === "string") return detalle;
  return MENSAJE_ERROR_DEFAULT;
}

/**
 * Hook para páginas que consultan un recurso del backend: expone siempre
 * {data, cargando, error, recargar} para que ninguna página falle en
 * silencio si el request falla.
 */
export function useApiResource(url, deps = []) {
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  // Descarta respuestas de peticiones viejas: StrictMode dispara el efecto
  // dos veces en desarrollo y solo la última respuesta debe contar, así la
  // vista nunca alterna entre estados.
  const version = useRef(0);

  const recargar = useCallback(() => {
    if (!url) return;
    const actual = ++version.current;
    setCargando(true);
    setError(null);
    api
      .get(url)
      .then((res) => {
        if (actual === version.current) setData(res.data);
      })
      .catch((err) => {
        if (actual === version.current) setError(extraerMensaje(err));
      })
      .finally(() => {
        if (actual === version.current) setCargando(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  useEffect(() => {
    recargar();
  }, [recargar]);

  return { data, cargando, error, recargar };
}

export { extraerMensaje };
