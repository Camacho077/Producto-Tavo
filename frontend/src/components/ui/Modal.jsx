import { useRef } from "react";
import { X } from "lucide-react";

import Button from "@/components/ui/Button";
import { useCapaSuperpuesta } from "@/hooks/useCapaSuperpuesta";

/**
 * Diálogo centrado, sin animación: aparece y desaparece de una vez. Se usa
 * SOLO para confirmar eliminación y cambio de estado (ModalConfirmar); crear,
 * editar y ver detalle son pantallas con ruta propia.
 * El foco, Escape y el bloqueo de scroll los maneja useCapaSuperpuesta.
 */
export default function Modal({ abierto, onCerrar, titulo, pie, ancho = "34rem", children }) {
  const panelRef = useRef(null);
  useCapaSuperpuesta({ abierto, onCerrar, panelRef });

  if (!abierto) return null;

  return (
    <div
      className="modal__fondo"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCerrar?.();
      }}
    >
      <div className="modal__panel" style={{ maxWidth: ancho }} role="dialog" aria-modal="true" aria-label={titulo} ref={panelRef}>
        <header className="modal__encabezado">
          <h2 className="modal__titulo">{titulo}</h2>
          <Button variante="terciario" tamano="sm" soloIcono onClick={onCerrar} aria-label="Cerrar">
            <X size={15} />
          </Button>
        </header>
        <div className="modal__cuerpo">{children}</div>
        {pie && <footer className="modal__pie">{pie}</footer>}
      </div>
    </div>
  );
}
