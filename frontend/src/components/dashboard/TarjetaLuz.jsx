import { useEffect, useRef } from "react";

/**
 * Tarjeta del dashboard con la luz que sigue al cursor (la `.card` de la
 * maqueta, docs/dashboard-referencia.html).
 *
 * Rendimiento:
 * - `pointermove` dispara muchas veces por cuadro. Aquí el evento solo guarda
 *   la última posición y el cálculo se hace UNA vez por cuadro con
 *   requestAnimationFrame (regla 2f).
 * - La luz es un disco YA PINTADO (`.tarjeta__luz`) que se mueve con
 *   translate3d: lo compone la GPU, no se repinta nada. Antes se movía el
 *   centro de un radial-gradient con variables CSS, y eso repintaba la
 *   tarjeta completa en cada cuadro.
 * - Sin estado de React: mover el ratón sobre una tarjeta no re-renderiza.
 *
 * La luz se activa solo donde hay cursor de verdad y sin movimiento reducido:
 * en táctil sobra y con `prefers-reduced-motion` no se pinta.
 */
const RADIO_LUZ = 240;

export default function TarjetaLuz({
  children,
  className = "",
  estilo,
  etiqueta,
  como: Como = "article",
}) {
  const nodo = useRef(null);
  const luz = useRef(null);

  useEffect(() => {
    const elemento = nodo.current;
    if (!elemento || typeof window.matchMedia !== "function") return undefined;
    const hayCursor = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!hayCursor || movimientoReducido) return undefined;

    let cuadro = 0;
    let x = 0;
    let y = 0;
    const alMover = (evento) => {
      x = evento.clientX;
      y = evento.clientY;
      if (cuadro) return;
      cuadro = requestAnimationFrame(() => {
        cuadro = 0;
        if (!luz.current) return;
        const caja = elemento.getBoundingClientRect();
        luz.current.style.transform = `translate3d(${x - caja.left - RADIO_LUZ}px, ${y - caja.top - RADIO_LUZ}px, 0)`;
      });
    };

    elemento.addEventListener("pointermove", alMover);
    return () => {
      cancelAnimationFrame(cuadro);
      elemento.removeEventListener("pointermove", alMover);
    };
  }, []);

  return (
    <Como ref={nodo} className={`tarjeta ${className}`} style={estilo} aria-label={etiqueta}>
      <span className="tarjeta__luz" ref={luz} aria-hidden="true" />
      {children}
    </Como>
  );
}
