import { useApiResource } from "@/hooks/useApiResource";

/**
 * Lista completa (hasta 100) de un catálogo para llenar <Select>: productos,
 * categorías, zonas, proveedores, roles. Devuelve siempre un arreglo.
 */
export function useCatalogo(url, { soloActivos = true } = {}) {
  // Sin url (p. ej. el rol no puede ver ese catálogo) no se pide nada.
  const separador = url?.includes("?") ? "&" : "?";
  const urlCompleta = url ? `${url}${separador}por_pagina=100${soloActivos ? "&activo=true" : ""}` : null;
  const { data, cargando, error, recargar } = useApiResource(urlCompleta);
  return { items: data?.items ?? [], cargando, error, recargar };
}
