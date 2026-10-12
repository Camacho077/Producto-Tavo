import { useApiResource } from "@/hooks/useApiResource";

/**
 * Lista completa (hasta 100) de un catálogo para llenar <Select>: productos,
 * categorías, zonas, proveedores, roles. Devuelve siempre un arreglo.
 */
export function useCatalogo(url, { soloActivos = true } = {}) {
  const separador = url.includes("?") ? "&" : "?";
  const urlCompleta = `${url}${separador}por_pagina=100${soloActivos ? "&activo=true" : ""}`;
  const { data, cargando, error, recargar } = useApiResource(urlCompleta);
  return { items: data?.items ?? [], cargando, error, recargar };
}
