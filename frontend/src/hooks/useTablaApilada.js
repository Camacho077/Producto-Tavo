import { useCallback, useLayoutEffect, useState } from "react";

const CLASE = "tabla-contenedor--apilada";
const PANTALLA_ANGOSTA = "(max-width: 767px)";

/**
 * ¿La tabla va en vista de TARJETAS? Sí cuando la pantalla mide menos de
 * 768 px (como siempre) o cuando la tabla NO CABE en su tarjeta.
 *
 * Por qué no basta un media query (medido el 2026-09-30): el ancho mínimo de
 * las tablas va de 266 px (productos de un proveedor) a 851 px (listado de
 * proveedores) y el espacio disponible depende del sidebar, que vuelve a
 * aparecer por encima de 1100 px. Con un umbral fijo de ventana, entre 768 y
 * 900 px (y a 1180 px) siete tablas se salían de la tarjeta y la PÁGINA
 * entera se desplazaba de lado; ningún umbral único sirve para todas.
 *
 * Mide el ancho mínimo real (min-content) de la tabla y lo compara con el de
 * su contenedor. Corre en `useLayoutEffect` y en el ResizeObserver, antes del
 * pintado: no hay un cuadro con la tabla desbordada ni salto de maquetación.
 */
export default function useTablaApilada(refContenedor, dependencia) {
  const [apilada, setApilada] = useState(false);

  const medir = useCallback(() => {
    const contenedor = refContenedor.current;
    const tabla = contenedor?.querySelector("table");
    if (!tabla) return;
    if (window.matchMedia?.(PANTALLA_ANGOSTA).matches) {
      setApilada(true);
      return;
    }
    // Se mide en modo TABLA: si ya estaba apilada, se quita la clase solo
    // durante la lectura (todo síncrono, el navegador no pinta en medio).
    const estaba = contenedor.classList.contains(CLASE);
    if (estaba) contenedor.classList.remove(CLASE);
    tabla.style.width = "min-content";
    const minimo = tabla.getBoundingClientRect().width;
    tabla.style.width = "";
    if (estaba) contenedor.classList.add(CLASE);
    setApilada(minimo > contenedor.clientWidth + 0.5);
  }, [refContenedor]);

  useLayoutEffect(() => {
    medir();
  }, [medir, dependencia]);

  useLayoutEffect(() => {
    const contenedor = refContenedor.current;
    if (!contenedor) return undefined;
    let ancho = contenedor.clientWidth;
    // Solo interesa el ANCHO: al apilar cambia la altura y eso no debe volver
    // a medir (evita un ciclo de observaciones).
    const observador =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => {
            if (contenedor.clientWidth === ancho) return;
            ancho = contenedor.clientWidth;
            medir();
          });
    observador?.observe(contenedor);
    const consulta = window.matchMedia?.(PANTALLA_ANGOSTA);
    consulta?.addEventListener?.("change", medir);
    // La fuente definitiva cambia el ancho del texto: se vuelve a medir.
    let vivo = true;
    document.fonts?.ready?.then(() => vivo && medir());
    return () => {
      vivo = false;
      observador?.disconnect();
      consulta?.removeEventListener?.("change", medir);
    };
  }, [refContenedor, medir]);

  return apilada;
}

export { CLASE as CLASE_TABLA_APILADA };
