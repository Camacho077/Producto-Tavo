import { useLayoutEffect, useRef } from "react";

import { RESORTE, RESORTE_DURACION, puedeAnimar, trasladoVisual } from "@/lib/movimiento";

/**
 * HERMANOS QUE SE DESLIZAN (FLIP a mano, sin librería).
 *
 * Cuando algo aparece o desaparece dentro de una lista (el panel de un grupo
 * del sidebar, una alerta que se cierra), los de abajo cambian de sitio de
 * golpe. Animar el ALTO del que cambia sería animar layout. Este hook hace lo
 * contrario: deja que el layout salte, y a cada hermano que se movió le pone
 * un `translateY` con la distancia que saltó y lo lleva a 0 con el resorte.
 * Solo transform, lo mueve el compositor.
 *
 * Cómo se entera: un ResizeObserver sobre el contenedor. Su callback corre
 * después del layout y ANTES del pintado, así que el salto nunca se llega a
 * ver. Compara el `offsetTop` de cada hijo con el que tenía (offsetTop es
 * layout puro, ignora transforms) y, si había una animación a medias, parte
 * desde donde iba de verdad: es interrumpible.
 *
 * @param alMover callback opcional tras reacomodar (el sidebar recoloca su
 *                indicador con la misma curva, así viajan juntos).
 */
export function useDeslizarHermanos(refContenedor, alMover) {
  const callback = useRef(alMover);
  useLayoutEffect(() => {
    callback.current = alMover;
  });

  useLayoutEffect(() => {
    const contenedor = refContenedor.current;
    if (!contenedor || typeof ResizeObserver !== "function") return undefined;

    const posiciones = new WeakMap();
    const hijos = () => [...contenedor.children].filter((hijo) => !hijo.hasAttribute("data-sin-deslizar"));

    const reacomodar = () => {
      for (const hijo of hijos()) {
        const antes = posiciones.get(hijo);
        const ahora = hijo.offsetTop;
        posiciones.set(hijo, ahora);
        if (antes === undefined || antes === ahora || !puedeAnimar(hijo)) continue;

        // Si ya se estaba deslizando, la posición visual incluye su translate.
        const enCurso = hijo.getAnimations?.().find((a) => a.id === "deslizar");
        const desplazamiento = enCurso ? trasladoVisual(hijo).y : 0;
        enCurso?.cancel();

        const animacion = hijo.animate(
          [{ transform: `translate3d(0, ${antes + desplazamiento - ahora}px, 0)` }, { transform: "translate3d(0, 0, 0)" }],
          { duration: RESORTE_DURACION, easing: RESORTE }
        );
        animacion.id = "deslizar";
      }
      callback.current?.();
    };

    // Primera medida sin animar: es la foto de partida.
    for (const hijo of hijos()) posiciones.set(hijo, hijo.offsetTop);
    const observador = new ResizeObserver(reacomodar);
    observador.observe(contenedor);
    return () => observador.disconnect();
  }, [refContenedor]);
}

export default useDeslizarHermanos;
