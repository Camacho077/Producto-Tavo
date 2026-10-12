import { useState } from "react";
import { Download } from "lucide-react";

import Button from "@/components/ui/Button";
import { useAviso } from "@/context/AvisoContext";
import { errorLegible } from "@/lib/descargas";
import { mensajeDeError } from "@/lib/errores";

/**
 * "Exportar CSV" de los listados (lo pinta TablaRecurso). Descarga TODAS las
 * filas que cumplen la búsqueda y los filtros activos, con el mismo permiso
 * que la tabla (backend: `?formato=csv`, app/core/exportar.py).
 */
export default function BotonExportar({ listado, nombre }) {
  const [exportando, setExportando] = useState(false);
  const aviso = useAviso();

  const exportar = async () => {
    setExportando(true);
    try {
      await listado.exportar(nombre);
    } catch (err) {
      aviso.error(mensajeDeError(await errorLegible(err), "exportar el listado"));
    } finally {
      setExportando(false);
    }
  };

  return (
    <Button
      variante="secundario"
      onClick={exportar}
      cargando={exportando}
      disabled={listado.cargaInicial || listado.total === 0}
      title={listado.total === 0 ? "No hay filas para exportar" : "Descarga todas las filas de la búsqueda actual"}
    >
      <Download size={14} aria-hidden="true" />
      Exportar CSV
    </Button>
  );
}
