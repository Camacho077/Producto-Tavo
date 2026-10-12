import { useId, useState } from "react";
import { Download, FileCheck2, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Seccion } from "@/components/FormularioPantalla";
import { Button, Card, ModalConfirmar, PageHeader, Select, Table } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { errorLegible, guardarBlob } from "@/lib/descargas";
import { mensajeDeError } from "@/lib/errores";
import { formatearNumero } from "@/lib/formato";
import { MIGAS } from "@/lib/migas";

/**
 * CARGA INICIAL (fase 3, 2026-10-12): el restaurante arranca de cero con la
 * plantilla que genera el sistema (Excel con hojas Insumos, Platos y
 * Recetas, o un CSV por hoja). Primero se REVISA el archivo fila por fila y
 * se muestra cada error con su hoja, fila y columna; nada se guarda hasta
 * que el archivo está limpio y se confirma. La aplicación es todo o nada
 * (backend: app/modules/inventario/carga.py).
 */
const URL_CARGA = "/inventario/carga-inicial";
const HOJAS = ["Insumos", "Platos", "Recetas"];
const TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

const esCsv = (archivo) => /\.csv$/i.test(archivo?.name ?? "");
const esPlantilla = (archivo) => /\.(xlsx|csv)$/i.test(archivo?.name ?? "");
const hojaPorNombre = (nombre) => HOJAS.find((h) => nombre.toLowerCase().includes(h.toLowerCase())) ?? "Insumos";

function enviarArchivo(accion, archivo, hoja) {
  const csv = esCsv(archivo);
  return api.post(`${URL_CARGA}/${accion}`, archivo, {
    params: csv ? { hoja } : undefined,
    headers: { "Content-Type": csv ? "text/csv" : TIPO_XLSX },
  });
}

function ResumenHojas({ hojas }) {
  return (
    <Table
      idFila={(h) => h.hoja}
      columnas={[
        { clave: "hoja", titulo: "Hoja", render: (h) => h.hoja },
        { clave: "filas", titulo: "Filas", cifra: true, render: (h) => formatearNumero(h.filas) },
        { clave: "nuevos", titulo: "Nuevos", cifra: true, render: (h) => (h.nuevos == null ? "—" : formatearNumero(h.nuevos)) },
        {
          clave: "actualizados",
          titulo: "Se actualizan",
          cifra: true,
          render: (h) => (h.platos != null ? `${formatearNumero(h.platos)} receta(s)` : h.actualizados == null ? "—" : formatearNumero(h.actualizados)),
        },
      ]}
      filas={hojas}
    />
  );
}

export function CargaInicial() {
  const navigate = useNavigate();
  const aviso = useAviso();
  const idArchivo = useId();
  const [archivo, setArchivo] = useState(null);
  const [hoja, setHoja] = useState("Insumos");
  const [informe, setInforme] = useState(null);
  const [revisando, setRevisando] = useState(false);
  const [descargando, setDescargando] = useState(null);
  const [confirmar, setConfirmar] = useState(false);

  const descargar = async (formato, hojaCsv) => {
    setDescargando(hojaCsv ?? formato);
    try {
      const res = await api.get(`${URL_CARGA}/plantilla`, { params: { formato, hoja: hojaCsv }, responseType: "blob" });
      guardarBlob(res.data, formato === "csv" ? `plantilla-${hojaCsv.toLowerCase()}.csv` : "plantilla-carga-inicial.xlsx");
    } catch (err) {
      aviso.error(mensajeDeError(await errorLegible(err), "descargar la plantilla"));
    } finally {
      setDescargando(null);
    }
  };

  const elegir = (e) => {
    const elegido = e.target.files?.[0] ?? null;
    setArchivo(elegido);
    setInforme(null);
    if (elegido && esCsv(elegido)) setHoja(hojaPorNombre(elegido.name));
  };

  const revisar = async () => {
    setRevisando(true);
    setInforme(null);
    try {
      const { data } = await enviarArchivo("validar", archivo, hoja);
      setInforme(data);
    } catch (err) {
      aviso.error(mensajeDeError(err, "revisar el archivo"));
    } finally {
      setRevisando(false);
    }
  };

  const total = informe ? informe.hojas.reduce((s, h) => s + h.filas, 0) : 0;

  return (
    <div className="pantalla-estrecha">
      <PageHeader
        volver="/inventario/insumos"
        titulo="Carga inicial"
        descripcion="Sube de una vez los insumos con su existencia, los platos y sus recetas."
        migas={MIGAS.cargaInicial}
      />
      <div className="space-y-4">
        <Card titulo="1. Descarga la plantilla" descripcion="El Excel trae las tres hojas con ejemplos y listas de unidades. Si prefieres CSV, hay uno por hoja.">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => descargar("xlsx")} cargando={descargando === "xlsx"}>
              <Download size={14} aria-hidden="true" /> Plantilla Excel
            </Button>
            {HOJAS.map((h) => (
              <Button key={h} variante="secundario" onClick={() => descargar("csv", h)} cargando={descargando === h}>
                <Download size={14} aria-hidden="true" /> CSV {h}
              </Button>
            ))}
          </div>
        </Card>

        <Card titulo="2. Sube el archivo lleno" descripcion="Primero se revisa fila por fila: no se guarda nada hasta que no tenga ningún error y confirmes.">
          <Seccion>
            <div className="campo">
              <label className="campo__etiqueta" htmlFor={idArchivo}>
                Archivo (.xlsx o .csv, máximo 5 MB)
              </label>
              <input id={idArchivo} type="file" accept=".xlsx,.csv" onChange={elegir} className="input" />
            </div>
            {esCsv(archivo) && (
              <Select etiqueta="¿Qué hoja es este CSV?" value={hoja} onChange={(e) => {
                  setHoja(e.target.value);
                  setInforme(null);
                }}>
                {HOJAS.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </Select>
            )}
            {archivo && !esPlantilla(archivo) && (
              <p className="estado estado--error" role="alert">
                «{archivo.name}» no es un Excel (.xlsx) ni un CSV: sube la plantilla del sistema.
              </p>
            )}
          </Seccion>
          <div className="formulario-pantalla__pie">
            <Button onClick={revisar} cargando={revisando} disabled={!esPlantilla(archivo)}>
              <FileCheck2 size={14} aria-hidden="true" /> Revisar archivo
            </Button>
          </div>
        </Card>

        {informe && (
          <Card
            titulo="3. Informe de la revisión"
            descripcion={
              informe.valido
                ? `Sin errores: ${formatearNumero(total)} fila(s) listas para guardar.`
                : `${formatearNumero(informe.total_errores)} error(es). Corrígelos en el archivo y vuelve a revisarlo: no se guardó nada.`
            }
          >
            <div className="space-y-4" aria-live="polite">
              <ResumenHojas hojas={informe.hojas} />
              {!informe.valido && (
                <Table
                  idFila={(e) => `${e.hoja}-${e.fila}-${e.columna}-${e.mensaje}`}
                  columnas={[
                    { clave: "hoja", titulo: "Hoja", ajustar: true, render: (e) => e.hoja },
                    { clave: "fila", titulo: "Fila", cifra: true, render: (e) => e.fila },
                    { clave: "columna", titulo: "Columna", render: (e) => e.columna },
                    { clave: "mensaje", titulo: "Qué corregir", render: (e) => e.mensaje },
                  ]}
                  filas={informe.errores}
                />
              )}
              {informe.total_errores > informe.errores.length && (
                <p className="text-[13px] text-[var(--texto-terciario)]">Se muestran los primeros {formatearNumero(informe.errores.length)} errores.</p>
              )}
              {informe.valido && (
                <div className="formulario-pantalla__pie">
                  <Button onClick={() => setConfirmar(true)} disabled={total === 0}>
                    <Upload size={14} aria-hidden="true" /> Guardar carga
                  </Button>
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
      <ModalConfirmar
        abierto={confirmar}
        onCerrar={() => setConfirmar(false)}
        titulo="Guardar la carga inicial"
        textoConfirmar="Guardar"
        mensaje="Se crean o actualizan los insumos y platos del archivo, la existencia entra como movimiento «Carga inicial» y las recetas de los platos del archivo se reemplazan. Todo o nada."
        accion="guardar la carga inicial"
        mensajeExito="Carga inicial guardada"
        onConfirmar={async () => {
          await enviarArchivo("aplicar", archivo, hoja);
          navigate("/inventario/insumos");
        }}
      />
    </div>
  );
}
