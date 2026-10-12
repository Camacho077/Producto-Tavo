import { useState } from "react";
import { AlertTriangle } from "lucide-react";

import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { useAviso } from "@/context/AvisoContext";
import { mensajeDeError } from "@/lib/errores";

/**
 * Confirmación de acciones sensibles (eliminar, anular, cambiar estado).
 * `onConfirmar` puede devolver una promesa: mientras resuelve, el botón
 * muestra el spinner.
 *
 * Es el embudo único de estas acciones, así que las alertas se emiten aquí
 * y ningún módulo tiene que acordarse de hacerlo:
 *  - si sale bien → alerta verde con `mensajeExito` y se cierra el diálogo;
 *  - si falla → alerta roja con la causa que devolvió el backend y el
 *    diálogo se queda abierto para reintentar o cancelar.
 *
 * `accion` ("eliminar la categoría Bebidas") solo se usa si el error no
 * trae mensaje propio; cuando el backend explica la causa, manda ese texto.
 */
export default function ModalConfirmar({
  abierto,
  onCerrar,
  onConfirmar,
  titulo = "¿Confirmar?",
  mensaje,
  mensajeExito,
  accion,
  textoConfirmar = "Confirmar",
  destructivo = false,
  // Deja el botón de confirmar apagado (p. ej. mientras falta el motivo).
  deshabilitado = false,
  children,
}) {
  const { exito, error } = useAviso();
  const [enviando, setEnviando] = useState(false);

  async function confirmar() {
    setEnviando(true);
    try {
      const resultado = await onConfirmar();
      const texto = typeof mensajeExito === "function" ? mensajeExito(resultado) : mensajeExito;
      if (texto) exito(texto);
      onCerrar?.();
    } catch (err) {
      error(mensajeDeError(err, accion));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={enviando ? undefined : onCerrar}
      titulo={titulo}
      pie={
        <>
          <Button variante="terciario" onClick={onCerrar} disabled={enviando}>
            Cancelar
          </Button>
          <Button variante={destructivo ? "destructivo" : "primario"} onClick={confirmar} cargando={enviando} disabled={deshabilitado}>
            {textoConfirmar}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        {destructivo && (
          <span className="confirmar__icono" aria-hidden="true">
            <AlertTriangle size={18} />
          </span>
        )}
        <div className="space-y-2 text-[13px] text-[var(--texto-secundario)]">
          {mensaje && <p>{mensaje}</p>}
          {children}
        </div>
      </div>
    </Modal>
  );
}
