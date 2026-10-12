import { useEffect, useMemo, useRef } from "react";

import { curvaSuave, hayMovimientoReducido, lerp } from "@/lib/movimiento";

/**
 * CONTADORES ANIMADOS SIN RENDERS.
 *
 * Actualizar un número no debe re-renderizar la pantalla (regla de rendimiento
 * 2e de la maqueta). Un contador hecho con `useState` dispararía un render del
 * dashboard completo —tarjetas, lista de más vendidos, gráfica— en cada cuadro
 * de la animación. Este hook escribe `textContent` directamente en el nodo de
 * cada cifra: React monta el nodo una vez y no vuelve a tocarlo.
 *
 * Uso:
 *
 *   // FUERA del componente, para que las refs sean estables entre renders.
 *   const FORMATOS = { ventas: formatearMoneda, clientes: formatearNumero };
 *
 *   const cifras = useMemo(() => ({ ventas: t?.ventas ?? 0, clientes: t?.numero_clientes ?? 0 }), [t]);
 *   const ref = useContadoresAnimados(FORMATOS, cifras);
 *   ...
 *   <b className="cifra" ref={ref.ventas}>{FORMATOS.ventas(0)}</b>
 *
 * El hijo estático (`FORMATOS.ventas(0)`) es a propósito: React lo registra
 * una sola vez y, como en los siguientes renders el hijo es idéntico, nunca
 * vuelve a escribir el texto y no pelea con lo que escribe el hook.
 */

// Movimiento de dato (--dur-dato + un respiro): la cifra sube rápido y frena
// al final con la curva única del producto (lib/movimiento.js).
const DURACION = 900;

/**
 * @param formatos objeto {clave: (n) => string}. Debe ser ESTABLE (una
 *                 constante de módulo): de él salen las refs.
 * @param valores  objeto {clave: number} con el destino. Memorizarlo.
 * @param duracion milisegundos de la animación.
 * @returns {clave: refCallback} para poner en el nodo de cada cifra.
 */
export function useContadoresAnimados(formatos, valores, duracion = DURACION) {
  const nodos = useRef({});
  const mostrado = useRef({});
  const cuadro = useRef(0);

  const refs = useMemo(
    () =>
      Object.fromEntries(
        Object.keys(formatos).map((clave) => [
          clave,
          (nodo) => {
            nodos.current[clave] = nodo;
          },
        ])
      ),
    [formatos]
  );

  useEffect(() => {
    if (!valores) return undefined;
    const claves = Object.keys(formatos);
    const destino = Object.fromEntries(claves.map((k) => [k, Number(valores[k]) || 0]));

    const pintar = () => {
      for (const clave of claves) {
        const nodo = nodos.current[clave];
        if (nodo) nodo.textContent = formatos[clave](mostrado.current[clave] ?? 0);
      }
    };

    cancelAnimationFrame(cuadro.current);

    if (hayMovimientoReducido()) {
      mostrado.current = destino;
      pintar();
      return undefined;
    }

    const desde = { ...mostrado.current };
    let inicio;
    const paso = (marca) => {
      if (inicio === undefined) inicio = marca;
      const avance = Math.min(1, (marca - inicio) / duracion);
      const t = curvaSuave(avance);
      for (const clave of claves) {
        mostrado.current[clave] = lerp(desde[clave] ?? 0, destino[clave], t);
      }
      pintar();
      if (avance < 1) {
        cuadro.current = requestAnimationFrame(paso);
      } else {
        cuadro.current = 0;
        mostrado.current = destino;
        pintar();
      }
    };
    cuadro.current = requestAnimationFrame(paso);

    return () => cancelAnimationFrame(cuadro.current);
  }, [formatos, valores, duracion]);

  return refs;
}

export default useContadoresAnimados;
