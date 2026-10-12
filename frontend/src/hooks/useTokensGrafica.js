import { useCallback, useEffect, useState } from "react";
import { leerTokensGrafica } from "@/theme/tokens";

/**
 * Los tokens de color que la gráfica necesita como valores concretos, ya
 * resueltos desde el DOM. La lista y la lectura viven en `theme/tokens.js`
 * (único sitio con nombres de tokens); este hook solo se encarga de volver a
 * leerlos cuando el tema cambia.
 *
 * Se recalcula al cambiar el modo claro/oscuro (atributo `data-theme`) o
 * cuando el tenant inyecta su color de marca (un `style` en :root), así que
 * la gráfica sigue respetando las dos capas de theming.
 */
export function useTokensGrafica() {
  const [tokens, setTokens] = useState(leerTokensGrafica);

  const releer = useCallback(() => setTokens(leerTokensGrafica()), []);

  useEffect(() => {
    releer();
    const observador = new MutationObserver(releer);
    observador.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "style"],
    });
    return () => observador.disconnect();
  }, [releer]);

  return tokens;
}
