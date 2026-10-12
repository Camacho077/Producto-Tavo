import { useState } from "react";
import { FileText } from "lucide-react";

import { Button } from "@/components/ui";
import { abrirPdf } from "@/lib/pdf";

/**
 * Descarga el PDF de un documento (compra, venta o pedido) y lo abre.
 * Mientras se genera en el backend, el botón muestra el spinner.
 *
 * Con `texto` es un botón normal con su etiqueta (encabezado del detalle);
 * sin él, un botón de icono para la fila de la tabla.
 */
export default function BotonPdf({ url, nombreArchivo, texto }) {
  const [cargando, setCargando] = useState(false);

  async function descargar() {
    setCargando(true);
    try {
      await abrirPdf(url, nombreArchivo);
    } finally {
      setCargando(false);
    }
  }

  return (
    <Button
      variante="terciario"
      tamano={texto ? undefined : "sm"}
      soloIcono={!texto}
      cargando={cargando}
      onClick={descargar}
      // Con texto visible, el nombre accesible ES ese texto (WCAG 2.5.3: quien
      // dice "Ver PDF" por voz debe encontrarlo); solo el botón de icono
      // necesita aria-label.
      aria-label={texto ? undefined : "Descargar PDF"}
      title={texto ? undefined : "Descargar PDF"}
    >
      {!cargando && <FileText size={14} aria-hidden="true" />}
      {texto && ` ${texto}`}
    </Button>
  );
}
