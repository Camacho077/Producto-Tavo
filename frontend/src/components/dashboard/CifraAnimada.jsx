import { useMemo } from "react";

import { useContadoresAnimados } from "@/hooks/useContadoresAnimados";

/**
 * Una cifra suelta que CUENTA hasta su valor al montar y, al cambiar de
 * periodo, pasa del valor que muestra al nuevo sin saltos. Es el mismo motor
 * que las cifras grandes del dashboard (useContadoresAnimados): escribe el
 * texto del nodo, nunca estado de React por cuadro.
 *
 * `formato` debe ser estable (una función de módulo, p. ej. formatearMoneda).
 */
export default function CifraAnimada({ valor, formato, className = "", como: Como = "span" }) {
  const formatos = useMemo(() => ({ v: formato }), [formato]);
  const valores = useMemo(() => ({ v: valor }), [valor]);
  const { v: ref } = useContadoresAnimados(formatos, valores);
  return (
    <Como className={className} ref={ref}>
      {formato(0)}
    </Como>
  );
}
