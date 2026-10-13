import { useState } from "react";

import { ModalConfirmar, Textarea } from "@/components/ui";

/**
 * Confirmación de una acción que exige MOTIVO (anular una orden, quitar un
 * plato, anular un cobro): el botón se enciende con 3 caracteres o más.
 * Quien lo usa le pone `key` por diálogo, así cada apertura empieza vacía.
 */
export default function DialogoMotivo({ abierto, onCerrar, titulo, mensaje, textoConfirmar, mensajeExito, accion, ayuda = "Queda en el historial", onConfirmar }) {
  const [motivo, setMotivo] = useState("");
  return (
    <ModalConfirmar
      abierto={abierto}
      onCerrar={onCerrar}
      destructivo
      titulo={titulo}
      mensaje={mensaje}
      textoConfirmar={textoConfirmar}
      mensajeExito={mensajeExito}
      accion={accion}
      deshabilitado={motivo.trim().length < 3}
      onConfirmar={() => onConfirmar(motivo.trim())}
    >
      <Textarea etiqueta="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={200} required ayuda={ayuda} />
    </ModalConfirmar>
  );
}
