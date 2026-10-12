import { useEffect, useRef } from "react";

const FOCUSABLES =
  'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';
const CAMPOS = 'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])';

/**
 * Comportamiento común de modales y paneles laterales:
 *  - Escape cierra.
 *  - Al abrir, enfoca el primer CAMPO de formulario (no el botón de cerrar);
 *    si no hay campos, el primer focusable.
 *  - Atrapa el foco dentro (Tab / Shift+Tab ciclan).
 *  - Bloquea el scroll del fondo.
 *  - Al cerrar, devuelve el foco a donde estaba.
 *
 * IMPORTANTE (bug real que hubo): el efecto depende SOLO de `abierto`. Si
 * dependiera de `onCerrar`, como cada página pasa una función inline nueva en
 * cada render, cada tecla escrita re-ejecutaba el efecto y el foco saltaba al
 * botón "Cerrar". Por eso `onCerrar` se lee desde un ref.
 */
export function useCapaSuperpuesta({ abierto, onCerrar, panelRef }) {
  const onCerrarRef = useRef(onCerrar);
  useEffect(() => {
    onCerrarRef.current = onCerrar;
  });

  useEffect(() => {
    if (!abierto) return undefined;

    const previo = document.activeElement;
    const scrollPrevio = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function alPresionar(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCerrarRef.current?.();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusables = Array.from(panelRef.current.querySelectorAll(FOCUSABLES));
      if (!focusables.length) return;
      const primero = focusables[0];
      const ultimo = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === primero) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primero.focus();
      } else if (!panelRef.current.contains(document.activeElement)) {
        e.preventDefault();
        primero.focus();
      }
    }
    document.addEventListener("keydown", alPresionar);

    // El panel entra animado: se enfoca en el siguiente frame para que el
    // navegador no haga scroll hacia un elemento aún transformado.
    const frame = requestAnimationFrame(() => {
      const panel = panelRef.current;
      if (!panel) return;
      const objetivo = panel.querySelector(CAMPOS) ?? panel.querySelector(FOCUSABLES);
      objetivo?.focus({ preventScroll: true });
    });

    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", alPresionar);
      document.body.style.overflow = scrollPrevio;
      if (previo instanceof HTMLElement && document.contains(previo)) previo.focus({ preventScroll: true });
    };
  }, [abierto, panelRef]);
}
