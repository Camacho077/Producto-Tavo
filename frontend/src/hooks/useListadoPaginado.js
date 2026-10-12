import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { extraerMensaje } from "@/hooks/useApiResource";

const RETARDO_BUSQUEDA_MS = 300;

/**
 * Listado paginado con búsqueda contra un endpoint del backend que devuelve
 * el sobre estándar {items, total, pagina, por_pagina, paginas}
 * (ver backend/app/core/paginacion.py).
 *
 * La búsqueda se envía con retardo para no golpear el backend en cada tecla
 * y vuelve a la página 1 cada vez que cambia.
 */
export function useListadoPaginado(url, { porPagina = 10, filtros = {}, busquedaInicial = "" } = {}) {
  // `busquedaInicial` permite llegar al listado con la búsqueda ya puesta
  // (el buscador del dashboard navega a /carta?q=...). Se aplica
  // de una vez, sin pasar por el retardo: el texto no lo está escribiendo nadie.
  const [busqueda, setBusqueda] = useState(busquedaInicial);
  const [busquedaAplicada, setBusquedaAplicada] = useState(busquedaInicial);
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState({ items: [], total: 0, pagina: 1, por_pagina: porPagina, paginas: 1 });
  const [cargando, setCargando] = useState(true);
  // true solo hasta la primera respuesta: es lo único que muestra el marcador
  // de carga; en recargas posteriores se conservan las filas actuales.
  const [cargaInicial, setCargaInicial] = useState(true);
  const [error, setError] = useState(null);
  const version = useRef(0);
  const filtrosClave = JSON.stringify(filtros);

  // Solo cuando el texto cambia de verdad (no en el montaje ni con el doble
  // efecto de StrictMode): si reseteara la página al montar, un clic rápido
  // en "siguiente" se perdería.
  useEffect(() => {
    if (busqueda.trim() === busquedaAplicada) return undefined;
    const id = setTimeout(() => {
      setBusquedaAplicada(busqueda.trim());
      setPagina(1);
    }, RETARDO_BUSQUEDA_MS);
    return () => clearTimeout(id);
  }, [busqueda, busquedaAplicada]);

  const recargar = useCallback(() => {
    const actual = ++version.current;
    setCargando(true);
    setError(null);
    api
      .get(url, {
        params: { q: busquedaAplicada || undefined, pagina, por_pagina: porPagina, ...JSON.parse(filtrosClave) },
      })
      .then((res) => {
        if (actual !== version.current) return;
        setDatos(res.data);
        // Si la página quedó vacía (ej. tras eliminar el último registro), retrocede.
        if (res.data.items.length === 0 && res.data.pagina > 1) setPagina(res.data.pagina - 1);
      })
      .catch((err) => {
        if (actual === version.current) setError(extraerMensaje(err));
      })
      .finally(() => {
        if (actual === version.current) {
          setCargando(false);
          setCargaInicial(false);
        }
      });
  }, [url, busquedaAplicada, pagina, porPagina, filtrosClave]);

  useEffect(() => {
    recargar();
  }, [recargar]);

  // EXPORTAR A CSV (2026-10-01): el MISMO endpoint con `formato=csv`, la
  // búsqueda aplicada y los filtros activos; el backend devuelve TODAS las
  // filas que cumplen (no solo la página visible) y aplica el mismo permiso.
  const exportar = useCallback(
    async (nombre) => {
      const res = await api.get(url, {
        params: { q: busquedaAplicada || undefined, ...JSON.parse(filtrosClave), formato: "csv" },
        responseType: "blob",
      });
      const hoy = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota" }).format(new Date());
      const enlace = document.createElement("a");
      enlace.href = URL.createObjectURL(res.data);
      enlace.download = `${nombre}-${hoy}.csv`;
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      setTimeout(() => URL.revokeObjectURL(enlace.href), 0);
    },
    [url, busquedaAplicada, filtrosClave]
  );

  return {
    items: datos.items,
    total: datos.total,
    pagina: datos.pagina,
    paginas: datos.paginas,
    porPagina,
    cargando,
    cargaInicial,
    error,
    busqueda,
    setBusqueda,
    setPagina,
    recargar,
    exportar,
  };
}
