import { createElement } from "react";

import Button from "@/components/ui/Button";

/**
 * Grupo de acciones de la última columna de una tabla. Todos los módulos lo
 * usan igual, así que entender uno es entender todos.
 */
export default function AccionesFila({ children }) {
  return <div className="acciones-fila">{children}</div>;
}

/**
 * Un botón de icono dentro de `AccionesFila`: terciario, pequeño, con su
 * etiqueta accesible y su tooltip. `titulo` cae en `etiqueta` si no se pasa
 * (es el caso normal: "Editar" en los dos).
 */
export function BotonAccion({ icono, etiqueta, titulo, onClick, disabled = false }) {
  return (
    <Button
      variante="terciario"
      tamano="sm"
      soloIcono
      onClick={onClick}
      disabled={disabled}
      aria-label={etiqueta}
      title={titulo ?? etiqueta}
    >
      {createElement(icono, { size: 14 })}
    </Button>
  );
}
