import { useMemo, useState } from "react";
import { Download, FileText } from "lucide-react";

import Dona from "@/components/charts/Dona";
import { Button, Card, Input, PageHeader, Pildoras, Table } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { api } from "@/lib/api";
import { errorLegible, guardarBlob } from "@/lib/descargas";
import { mensajeDeError } from "@/lib/errores";
import { formatearMoneda, formatearNumero } from "@/lib/formato";
import { abrirPdf } from "@/lib/pdf";
import { MIGAS } from "@/lib/migas";
import { legible } from "@/lib/unidades";

import "./reportes.css";

/**
 * REPORTES (fase 8, 2026-10-12): las tres preguntas del dueño —¿cuánto
 * entró?, ¿cuánto costó?, ¿cuánto gané?— y el detalle que las explica. Cada
 * sección se exporta a CSV y el reporte completo a PDF. Las cifras de costo
 * solo aparecen con el permiso de costos (el backend no las manda sin él).
 */
const PERIODOS = [
  { clave: "hoy", etiqueta: "Hoy" },
  { clave: "semana", etiqueta: "Semana" },
  { clave: "mes", etiqueta: "Mes" },
  { clave: "anio", etiqueta: "Año" },
  { clave: "personalizado", etiqueta: "Fechas", titulo: "Periodo personalizado" },
];
const hoyColombia = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota" }).format(new Date());
const pct = (v) => (v === null || v === undefined ? "—" : `${formatearNumero(v)} %`);
const pesos = (v) => (v === null || v === undefined ? "—" : formatearMoneda(v));

function Cifra({ etiqueta, valor, detalle, fuerte = false }) {
  return (
    <div className={`reporte-cifra ${fuerte ? "reporte-cifra--fuerte" : ""}`}>
      <p className="reporte-cifra__etiqueta">{etiqueta}</p>
      <p className="reporte-cifra__valor cifra">{valor}</p>
      {detalle && <p className="reporte-cifra__detalle">{detalle}</p>}
    </div>
  );
}

function BotonCsv({ seccion, parametros }) {
  const aviso = useAviso();
  const [bajando, setBajando] = useState(false);
  const bajar = async () => {
    setBajando(true);
    try {
      const res = await api.get("/reportes/csv", { params: { seccion, ...parametros }, responseType: "blob" });
      guardarBlob(res.data, `reporte-${seccion}.csv`);
    } catch (err) {
      aviso.error(mensajeDeError(await errorLegible(err), "exportar la sección"));
    } finally {
      setBajando(false);
    }
  };
  return (
    <Button variante="terciario" tamano="sm" onClick={bajar} cargando={bajando} aria-label={`Exportar ${seccion} a CSV`}>
      <Download size={14} aria-hidden="true" /> CSV
    </Button>
  );
}

/** Barras horizontales con scaleX (regla 2b: solo transform). */
function Barras({ filas, etiqueta, valor, formato = formatearMoneda }) {
  const maximo = Math.max(1, ...filas.map((f) => Number(valor(f))));
  return (
    <ul className="reporte-barras">
      {filas.map((f) => (
        <li key={etiqueta(f)}>
          <span className="reporte-barras__etiqueta">{etiqueta(f)}</span>
          <span className="reporte-barras__pista" aria-hidden="true">
            <span className="reporte-barras__barra" style={{ transform: `scaleX(${Number(valor(f)) / maximo})` }} />
          </span>
          <span className="reporte-barras__valor cifra">{formato(valor(f))}</span>
        </li>
      ))}
    </ul>
  );
}

export function Reportes() {
  const aviso = useAviso();
  const { puede } = useAuth();
  const verCostos = puede("costos", "ver");
  const [periodo, setPeriodo] = useState("mes");
  const [desde, setDesde] = useState(() => hoyColombia().slice(0, 8) + "01");
  const [hasta, setHasta] = useState(hoyColombia);
  const [bajandoPdf, setBajandoPdf] = useState(false);

  const parametros = useMemo(() => (periodo === "personalizado" ? { desde, hasta } : { periodo }), [periodo, desde, hasta]);
  const consulta = new URLSearchParams(parametros).toString();
  const listo = periodo !== "personalizado" || (desde && hasta && desde <= hasta);
  const { data: d, error } = useApiResource(listo ? `/reportes?${consulta}` : null);
  const r = d?.resumen;

  const pdf = async () => {
    setBajandoPdf(true);
    try {
      await abrirPdf(`/reportes/pdf?${consulta}`, "reporte.pdf");
    } catch (err) {
      aviso.error(mensajeDeError(await errorLegible(err), "generar el PDF"));
    } finally {
      setBajandoPdf(false);
    }
  };

  const masVendidos = d?.platos.slice(0, 10) ?? [];
  const menosVendidos = d ? [...d.platos].reverse().slice(0, 5) : [];
  const horas = d?.horas.filter((h) => h.cobros > 0) ?? [];

  return (
    <div className="reportes">
      <PageHeader
        titulo="Reportes"
        descripcion={d ? `${d.periodo}: cuánto entró, cuánto costó y cuánto ganaste.` : "Cuánto entró, cuánto costó y cuánto ganaste."}
        migas={MIGAS.reportes}
        acciones={
          <Button variante="secundario" onClick={pdf} cargando={bajandoPdf} disabled={!listo}>
            <FileText size={14} aria-hidden="true" /> PDF
          </Button>
        }
      />
      <div className="reportes__periodo">
        <Pildoras opciones={PERIODOS} valor={periodo} onCambiar={setPeriodo} etiqueta="Periodo del reporte" />
        {periodo === "personalizado" && (
          <div className="reportes__fechas">
            <Input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} cifra aria-label="Desde el día" />
            <Input type="date" value={hasta} min={desde || undefined} max={hoyColombia()} onChange={(e) => setHasta(e.target.value)} cifra aria-label="Hasta el día" />
          </div>
        )}
      </div>
      {error && <p className="estado estado--error">{error}</p>}
      {!d && !error && <p className="text-[13px] text-[var(--texto-terciario)]">Calculando…</p>}
      {d && (
        <div className="space-y-4">
          <Card titulo="Resumen">
            <div className="reporte-cifras">
              <Cifra etiqueta="Vendido" valor={pesos(r.total)} detalle={`${formatearNumero(r.ordenes)} órdenes · ticket ${pesos(r.ticket_promedio)}`} />
              <Cifra etiqueta="Ingresos" valor={pesos(r.ingresos)} detalle={`Sin impuesto al consumo (${pesos(r.impuesto)})`} />
              {verCostos && <Cifra etiqueta="Costo de lo vendido" valor={pesos(r.costo)} detalle={`${pct(r.costo_pct)} de los ingresos`} />}
              {verCostos && <Cifra etiqueta="Utilidad bruta" valor={pesos(r.utilidad_bruta)} detalle={`Margen ${pct(r.margen_bruto_pct)}`} />}
              {verCostos && <Cifra etiqueta="Gastos" valor={pesos(r.gastos)} />}
              {verCostos && <Cifra etiqueta="Utilidad real" valor={pesos(r.utilidad_real)} detalle="Ingresos − costo − gastos" fuerte />}
              <Cifra etiqueta="Propinas" valor={pesos(r.propinas)} detalle="No son ingreso del restaurante" />
            </div>
          </Card>

          <div className="reportes__donas">
            <Card>
              <Dona titulo="Por categoría" partes={d.categorias.map((c) => ({ nombre: c.nombre, valor: c.total }))} />
            </Card>
            <Card>
              <Dona titulo="Por medio de pago" partes={d.medios.map((m) => ({ nombre: m.nombre, valor: m.total }))} />
            </Card>
            <Card>
              <Dona titulo="Por tipo de orden" partes={d.tipos.map((t) => ({ nombre: t.nombre, valor: t.total }))} />
            </Card>
          </div>

          <Card titulo="Platos más vendidos" acciones={<BotonCsv seccion="platos" parametros={parametros} />}>
            <Table
              idFila={(p) => p.producto_id}
              columnas={[
                { clave: "nombre", titulo: "Plato", render: (p) => p.nombre },
                { clave: "unidades", titulo: "Unidades", cifra: true, render: (p) => formatearNumero(p.unidades) },
                { clave: "vendido", titulo: "Vendido", cifra: true, render: (p) => pesos(p.vendido) },
                ...(verCostos
                  ? [
                      { clave: "costo", titulo: "Costo", cifra: true, render: (p) => pesos(p.costo) },
                      { clave: "margen", titulo: "Margen", cifra: true, render: (p) => pesos(p.margen) },
                      { clave: "costo_pct", titulo: "% costo", cifra: true, render: (p) => pct(p.costo_pct) },
                    ]
                  : []),
              ]}
              filas={masVendidos}
              vacio="Sin ventas en el periodo."
            />
          </Card>
          {d.platos.length > 5 && (
            <Card titulo="Los que menos se venden" descripcion="Candidatos a revisar o a salir de la carta.">
              <Table
                idFila={(p) => p.producto_id}
                columnas={[
                  { clave: "nombre", titulo: "Plato", render: (p) => p.nombre },
                  { clave: "unidades", titulo: "Unidades", cifra: true, render: (p) => formatearNumero(p.unidades) },
                  { clave: "vendido", titulo: "Vendido", cifra: true, render: (p) => pesos(p.vendido) },
                  ...(verCostos ? [{ clave: "margen", titulo: "Margen", cifra: true, render: (p) => pesos(p.margen) }] : []),
                ]}
                filas={menosVendidos}
              />
            </Card>
          )}

          <div className="reportes__pares">
            <Card titulo="Horas de más venta" acciones={<BotonCsv seccion="horas" parametros={parametros} />}>
              {horas.length ? <Barras filas={horas} etiqueta={(h) => `${String(h.hora).padStart(2, "0")}:00`} valor={(h) => h.total} /> : <p className="estado">Sin ventas en el periodo.</p>}
            </Card>
            <Card titulo="Por día de la semana" acciones={<BotonCsv seccion="dias" parametros={parametros} />}>
              <Barras filas={d.dias} etiqueta={(x) => x.dia} valor={(x) => x.total} />
            </Card>
          </div>

          <div className="reportes__pares">
            <Card titulo="Por tipo de orden" acciones={<BotonCsv seccion="tipos" parametros={parametros} />}>
              <Table
                idFila={(t) => t.clave}
                columnas={[
                  { clave: "nombre", titulo: "Tipo", render: (t) => t.nombre },
                  { clave: "ordenes", titulo: "Órdenes", cifra: true, render: (t) => formatearNumero(t.ordenes) },
                  { clave: "total", titulo: "Vendido", cifra: true, render: (t) => pesos(t.total) },
                  { clave: "ticket", titulo: "Ticket", cifra: true, render: (t) => pesos(t.ticket) },
                ]}
                filas={d.tipos}
                vacio="Sin ventas en el periodo."
              />
            </Card>
            <Card titulo="Por mesero" acciones={<BotonCsv seccion="meseros" parametros={parametros} />}>
              <Table
                idFila={(m) => m.clave}
                columnas={[
                  { clave: "nombre", titulo: "Mesero", render: (m) => m.nombre },
                  { clave: "ordenes", titulo: "Órdenes", cifra: true, render: (m) => formatearNumero(m.ordenes) },
                  { clave: "total", titulo: "Vendido", cifra: true, render: (m) => pesos(m.total) },
                  { clave: "ticket", titulo: "Ticket", cifra: true, render: (m) => pesos(m.ticket) },
                ]}
                filas={d.meseros}
                vacio="Sin ventas en el periodo."
              />
            </Card>
          </div>

          <Card titulo="Insumos: consumo y mermas" descripcion="Lo que salió por ventas y lo que se perdió." acciones={<BotonCsv seccion="insumos" parametros={parametros} />}>
            <Table
              idFila={(i) => i.insumo_id}
              columnas={[
                { clave: "nombre", titulo: "Insumo", render: (i) => i.nombre },
                { clave: "consumo", titulo: "Consumo", cifra: true, render: (i) => legible(i.consumo, i.unidad) },
                ...(verCostos ? [{ clave: "costo_consumo", titulo: "Costo", cifra: true, render: (i) => pesos(i.costo_consumo) }] : []),
                { clave: "merma", titulo: "Merma", cifra: true, render: (i) => (i.merma ? legible(i.merma, i.unidad) : "—") },
                ...(verCostos ? [{ clave: "costo_merma", titulo: "Costo de la merma", cifra: true, render: (i) => (i.merma ? pesos(i.costo_merma) : "—") }] : []),
                { clave: "merma_pct", titulo: "% merma", cifra: true, render: (i) => (i.merma ? pct(i.merma_pct) : "—") },
              ]}
              filas={d.insumos}
              vacio="Sin consumo en el periodo."
            />
          </Card>

          <Card titulo="Gastos" acciones={<BotonCsv seccion="gastos" parametros={parametros} />}>
            <Table
              idFila={(g) => g.clave}
              columnas={[
                { clave: "nombre", titulo: "Categoría", render: (g) => g.nombre },
                { clave: "registros", titulo: "Registros", cifra: true, render: (g) => formatearNumero(g.registros) },
                { clave: "total", titulo: "Total", cifra: true, render: (g) => pesos(g.total) },
              ]}
              filas={d.gastos}
              vacio="Sin gastos registrados en el periodo."
            />
          </Card>
        </div>
      )}
    </div>
  );
}
