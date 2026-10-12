import { useRef } from "react";
import { CheckCircle2, X, XCircle } from "lucide-react";

import Button from "@/components/ui/Button";
import { useAviso } from "@/context/AvisoContext";
import { useDeslizarHermanos } from "@/hooks/useDeslizarHermanos";

/**
 * Pila de alertas arriba a la derecha. Éxito (role="status", el lector de
 * pantalla la anuncia al terminar lo que esté diciendo) y error
 * (role="alert", lo anuncia de inmediato porque trae la causa de algo que no
 * se pudo hacer). Se distinguen por icono, rol, duración y texto.
 *
 * Movimiento: fade simple de entrada y de salida (solo opacity, en CSS). Al
 * quitarse una, las de abajo suben deslizándose (useDeslizarHermanos) en vez
 * de saltar. Se apilan en orden de llegada, la más nueva abajo.
 *
 * El contenedor está SIEMPRE montado (vacío no ocupa ni captura clics): el
 * deslizamiento necesita medir a los hijos antes y después de cada cambio.
 */
export default function Aviso() {
  const { alertas, cerrar } = useAviso();
  const pila = useRef(null);
  useDeslizarHermanos(pila);

  return (
    <div className="alertas" ref={pila}>
      {alertas.map(({ id, texto, tipo, saliendo }) => {
        const Icono = tipo === "error" ? XCircle : CheckCircle2;
        return (
          <div
            key={id}
            className={`alerta alerta--${tipo}${saliendo ? " alerta--saliendo" : ""}`}
            role={tipo === "error" ? "alert" : "status"}
          >
            <Icono size={16} className="alerta__icono" aria-hidden="true" />
            <span className="alerta__texto">{texto}</span>
            <Button variante="terciario" tamano="sm" soloIcono onClick={() => cerrar(id)} aria-label="Cerrar alerta">
              <X size={13} />
            </Button>
          </div>
        );
      })}
    </div>
  );
}
