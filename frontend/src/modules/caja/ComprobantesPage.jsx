import { useState } from "react";
import { Ban, Eye, Printer } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import BotonPdf from "@/components/BotonPdf";
import DialogoMotivo from "@/components/DialogoMotivo";
import PantallaDetalle from "@/components/PantallaDetalle";
import { AccionesFila, Badge, BotonAccion, Button, Card, Detalle, Input, PageHeader, Select, Table, TablaRecurso } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { useAuth } from "@/context/AuthContext";
import { MEDIOS_PAGO, etiquetaMedioPago } from "@/config/restaurante";
import { useApiResource } from "@/hooks/useApiResource";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFechaHora, formatearMoneda, formatearNumero } from "@/lib/formato";
import { LEYENDA_COMPROBANTE, imprimirComprobante } from "@/lib/impresion";
import { MIGAS, migasDe } from "@/lib/migas";
import { ResumenCaja } from "@/modules/caja/CajaPage";

/**
 * Comprobantes (cobros) y cierres de caja (fase 6, 2026-10-12).
 */
const RUTA = "/caja/ventas";

function BadgeVenta({ venta }) {
  return venta.estado === "anulada" ? <Badge variante="negativo">Anulado</Badge> : <Badge variante="positivo">Pagado</Badge>;
}

export function VentasLista() {
  const navigate = useNavigate();
  const [medio, setMedio] = useState("");
  const [estado, setEstado] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const filtros = { ...(medio ? { medio } : {}), ...(estado ? { estado } : {}), ...(desde ? { desde } : {}), ...(hasta ? { hasta } : {}) };
  const listado = useListadoPaginado(RUTA, { filtros, porPagina: 20 });
  const columnas = [
    {
      clave: "codigo",
      titulo: "Comprobante",
      ajustar: true,
      render: (v) => (
        <Link to={`${RUTA}/${v.id}`} className="enlace cifra">
          {v.codigo}
        </Link>
      ),
    },
    { clave: "fecha", titulo: "Fecha", ajustar: true, render: (v) => formatearFechaHora(v.fecha) },
    { clave: "orden", titulo: "Orden", cifra: true, render: (v) => `#${v.orden_numero}` },
    { clave: "cliente_nombre", titulo: "Cliente", render: (v) => v.cliente_nombre ?? "—" },
    { clave: "medios", titulo: "Pago", render: (v) => v.medios.map(etiquetaMedioPago).join(", ") },
    { clave: "total", titulo: "Total", cifra: true, render: (v) => formatearMoneda(v.total) },
    { clave: "propina", titulo: "Propina", cifra: true, render: (v) => (Number(v.propina) ? formatearMoneda(v.propina) : "—") },
    { clave: "estado", titulo: "Estado", ajustar: true, render: (v) => <BadgeVenta venta={v} /> },
    { clave: "cajero_nombre", titulo: "Cajero", render: (v) => v.cajero_nombre ?? "—" },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (v) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver ${v.codigo}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA}/${v.id}`)} />
        </AccionesFila>
      ),
    },
  ];
  return (
    <div>
      <PageHeader titulo="Comprobantes" descripcion="Cada cobro con su comprobante interno, sus medios de pago y quién lo hizo." migas={MIGAS.comprobantes} />
      <TablaRecurso
        exportar="comprobantes"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por número, cliente o cajero…"
        vacio="Todavía no hay cobros."
        filtros={
          <>
            <Select value={medio} onChange={(e) => setMedio(e.target.value)} className="w-40" aria-label="Filtrar por medio de pago">
              <option value="">Todos los medios</option>
              {MEDIOS_PAGO.map((m) => (
                <option key={m.valor} value={m.valor}>
                  {m.etiqueta}
                </option>
              ))}
            </Select>
            <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="w-36" aria-label="Filtrar por estado">
              <option value="">Todos</option>
              <option value="completada">Pagados</option>
              <option value="anulada">Anulados</option>
            </Select>
            <Input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} cifra aria-label="Desde el día" className="w-40" />
            <Input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} cifra aria-label="Hasta el día" className="w-40" />
          </>
        }
      />
    </div>
  );
}

export function VentaDetalle() {
  const { id } = useParams();
  const aviso = useAviso();
  const { puede, tenant } = useAuth();
  const { data: v, error, recargar } = useApiResource(`${RUTA}/${id}`);
  const [anulando, setAnulando] = useState(false);
  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={v ? `Comprobante ${v.codigo}` : "Comprobante"}
      descripcion={v ? formatearFechaHora(v.fecha) : undefined}
      migas={migasDe(MIGAS.comprobantes, { etiqueta: v?.codigo ?? "…" })}
      error={error}
      datos={v}
      acciones={
        v && (
          <>
            {v.estado === "completada" && puede("ventas", "anular") && (
              <Button variante="terciario" onClick={() => setAnulando(true)}>
                <Ban size={14} aria-hidden="true" /> Anular cobro
              </Button>
            )}
            <BotonPdf url={`${RUTA}/${id}/pdf`} nombreArchivo={`${v.codigo}.pdf`} />
            <Button onClick={() => imprimirComprobante(v, tenant).catch((err) => aviso.error(err.message))}>
              <Printer size={14} aria-hidden="true" /> Imprimir
            </Button>
          </>
        )
      }
    >
      {v && (
        <div className="space-y-4">
          <p className="caja-leyenda">{LEYENDA_COMPROBANTE}</p>
          <div className="detalle-rejilla">
            <Card titulo="Cobro">
              <Detalle
                campos={[
                  { etiqueta: "Estado", valor: <BadgeVenta venta={v} /> },
                  { etiqueta: "Orden", valor: <Link to={`/ordenes/${v.orden_id}`} className="enlace cifra">#{v.orden_numero}</Link> },
                  ...(v.mesa_nombre ? [{ etiqueta: "Mesa", valor: v.mesa_nombre }] : []),
                  { etiqueta: "Cliente", valor: v.cliente_nombre },
                  ...(v.cliente_documento ? [{ etiqueta: "Documento", valor: `${v.cliente_documento_tipo} ${v.cliente_documento}`, cifra: true }] : []),
                  ...(v.cliente_correo ? [{ etiqueta: "Correo", valor: v.cliente_correo }] : []),
                  { etiqueta: "Cajero", valor: v.cajero_nombre },
                  ...(v.anulada_motivo ? [{ etiqueta: "Motivo de anulación", valor: v.anulada_motivo }] : []),
                ]}
              />
            </Card>
            <Card titulo="Montos">
              <Detalle
                campos={[
                  { etiqueta: "Base", valor: formatearMoneda(v.subtotal), cifra: true },
                  ...(Number(v.impuesto) ? [{ etiqueta: `Impuesto al consumo ${Number(v.impuesto_tasa)} %`, valor: formatearMoneda(v.impuesto), cifra: true }] : []),
                  { etiqueta: "Total", valor: formatearMoneda(v.total), cifra: true },
                  { etiqueta: "Propina", valor: Number(v.propina) ? formatearMoneda(v.propina) : "Sin propina", cifra: true },
                  ...v.pagos.map((p) => ({
                    etiqueta: etiquetaMedioPago(p.medio),
                    valor: `${formatearMoneda(p.monto)}${p.cambio ? ` · recibido ${formatearMoneda(p.recibido)}, devueltas ${formatearMoneda(p.cambio)}` : ""}`,
                    cifra: true,
                  })),
                ]}
              />
            </Card>
          </div>
          <Card titulo="Platos">
            <Table
              columnas={[
                { clave: "nombre", titulo: "Plato", render: (i) => i.nombre },
                { clave: "cantidad", titulo: "Cantidad", cifra: true, render: (i) => i.cantidad },
                { clave: "precio_unitario", titulo: "Precio", cifra: true, render: (i) => formatearMoneda(i.precio_unitario) },
                { clave: "subtotal", titulo: "Subtotal", cifra: true, render: (i) => formatearMoneda(i.subtotal) },
              ]}
              filas={v.items}
            />
          </Card>
        </div>
      )}
      <DialogoMotivo
        key={`anular-${anulando}`}
        abierto={anulando}
        onCerrar={() => setAnulando(false)}
        titulo={v ? `Anular el cobro ${v.codigo}` : "Anular cobro"}
        mensaje="Los platos vuelven a quedar por cobrar en la orden. Solo se puede mientras la caja de ese cobro siga abierta."
        textoConfirmar="Anular cobro"
        mensajeExito={v ? `Cobro ${v.codigo} anulado` : "Cobro anulado"}
        accion="anular el cobro"
        onConfirmar={async (motivo) => {
          await api.post(`${RUTA}/${id}/anular`, { motivo });
          recargar();
        }}
      />
    </PantallaDetalle>
  );
}

export function CierresLista() {
  const navigate = useNavigate();
  const listado = useListadoPaginado("/caja/cierres", { porPagina: 20 });
  const columnas = [
    {
      clave: "numero",
      titulo: "Caja",
      ajustar: true,
      render: (c) => (
        <Link to={`/caja/cierres/${c.id}`} className="enlace cifra">
          {c.numero}
        </Link>
      ),
    },
    { clave: "abierta_en", titulo: "Apertura", ajustar: true, render: (c) => formatearFechaHora(c.abierta_en) },
    { clave: "cerrada_en", titulo: "Cierre", ajustar: true, render: (c) => formatearFechaHora(c.cerrada_en) },
    { clave: "ventas", titulo: "Cobros", cifra: true, render: (c) => formatearNumero(c.resumen.ventas) },
    { clave: "total", titulo: "Vendido", cifra: true, render: (c) => formatearMoneda(c.resumen.total_ventas) },
    {
      clave: "diferencia",
      titulo: "Diferencia",
      cifra: true,
      render: (c) => (Number(c.diferencia) === 0 ? "Cuadró" : `${Number(c.diferencia) > 0 ? "▲ +" : "▼ −"}${formatearMoneda(Math.abs(Number(c.diferencia)))}`),
    },
    { clave: "cerrada_por", titulo: "Cerró", render: (c) => c.cerrada_por ?? "—" },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (c) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver el cierre de la caja ${c.numero}`} titulo="Ver reporte" onClick={() => navigate(`/caja/cierres/${c.id}`)} />
        </AccionesFila>
      ),
    },
  ];
  return (
    <div>
      <PageHeader titulo="Cierres de caja" descripcion="El reporte de cada día: lo esperado, lo contado y las diferencias con su motivo." migas={MIGAS.cierres} />
      <TablaRecurso exportar="cierres-de-caja" listado={listado} columnas={columnas} placeholderBusqueda="Buscar por cajero o motivo…" vacio="Todavía no se ha cerrado ninguna caja." />
    </div>
  );
}

export function CierreDetalle() {
  const { id } = useParams();
  const { data: c, error } = useApiResource(`/caja/cierres/${id}`);
  const ventas = useListadoPaginado("/caja/ventas", { filtros: { caja_id: id }, porPagina: 20 });
  const medios = c ? Object.keys({ ...c.resumen.esperado, ...(c.contado ?? {}) }) : [];
  return (
    <PantallaDetalle
      volver="/caja/cierres"
      titulo={c ? `Cierre de la caja ${c.numero}` : "Cierre de caja"}
      descripcion={c?.cerrada_en ? formatearFechaHora(c.cerrada_en) : undefined}
      migas={migasDe(MIGAS.cierres, { etiqueta: c ? `Caja ${c.numero}` : "…" })}
      error={error}
      datos={c}
    >
      {c && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Resumen">
              <ResumenCaja caja={c} />
            </Card>
            <Card titulo="Cuadre por medio de pago">
              <Table
                idFila={(f) => f.medio}
                columnas={[
                  { clave: "medio", titulo: "Medio", render: (f) => etiquetaMedioPago(f.medio) },
                  { clave: "esperado", titulo: "Esperado", cifra: true, render: (f) => formatearMoneda(f.esperado) },
                  { clave: "contado", titulo: "Contado", cifra: true, render: (f) => (f.contado === null ? "—" : formatearMoneda(f.contado)) },
                  {
                    clave: "diferencia",
                    titulo: "Diferencia",
                    cifra: true,
                    render: (f) => (f.contado === null ? "—" : Number(f.contado) - Number(f.esperado) === 0 ? "Cuadra" : `${Number(f.contado) > Number(f.esperado) ? "▲ +" : "▼ −"}${formatearMoneda(Math.abs(Number(f.contado) - Number(f.esperado)))}`),
                  },
                ]}
                filas={medios.map((m) => ({ medio: m, esperado: c.resumen.esperado[m] ?? 0, contado: c.contado?.[m] ?? null }))}
              />
            </Card>
          </div>
          <TablaRecurso
            titulo="Cobros de esta caja"
            listado={ventas}
            columnas={[
              { clave: "codigo", titulo: "Comprobante", render: (v) => <Link to={`${RUTA}/${v.id}`} className="enlace cifra">{v.codigo}</Link> },
              { clave: "fecha", titulo: "Hora", render: (v) => formatearFechaHora(v.fecha) },
              { clave: "medios", titulo: "Pago", render: (v) => v.medios.map(etiquetaMedioPago).join(", ") },
              { clave: "total", titulo: "Total", cifra: true, render: (v) => formatearMoneda(v.total) },
              { clave: "estado", titulo: "Estado", render: (v) => <BadgeVenta venta={v} /> },
            ]}
            placeholderBusqueda="Buscar por número o cliente…"
            vacio="Esta caja no tuvo cobros."
          />
        </div>
      )}
    </PantallaDetalle>
  );
}
