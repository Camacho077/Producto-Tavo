import { useMemo, useState } from "react";
import { Ban, Check, Eye, Plus } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import ItemsEditor, { ITEM_VACIO, totalDeItems } from "@/components/ItemsEditor";
import BotonPdf from "@/components/BotonPdf";
import PantallaDetalle from "@/components/PantallaDetalle";
import { api } from "@/lib/api";
import { useApiResource } from "@/hooks/useApiResource";
import { useCatalogo } from "@/hooks/useCatalogo";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { useAuth } from "@/context/AuthContext";
import { fechaLocalAhora, formatearFecha, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { errorDocumento, errorNit, esquemaItems, esquemas } from "@/lib/validaciones";
import {
  AccionesFila,
  Badge,
  BotonAccion,
  Button,
  Card,
  Checkbox,
  Detalle,
  Input,
  ModalConfirmar,
  PageHeader,
  Select,
  TablaRecurso,
  Table,
  Textarea,
  etiquetaDeEstado,
  varianteDeEstado,
} from "@/components/ui";

const RUTA = "/ventas";
const URL = "/ventas/ventas";
const ESTADOS = ["pendiente", "completada", "cancelada", "anulada"];

// Documento del cliente: cédula (solo dígitos) o NIT con dígito de verificación.
const documentoCliente = z.string().superRefine((s, ctx) => {
  const t = s.trim();
  if (t === "") return;
  const err = t.includes("-") ? errorNit(t) : errorDocumento("CC", t);
  if (err) ctx.addIssue({ code: "custom", message: err });
});

const ESQUEMA = z.object({
  cliente_nombre: esquemas.nombreItem(80),
  cliente_documento: documentoCliente,
  fecha: esquemas.obligatorio().pipe(esquemas.fechaNoFutura()),
  notas: esquemas.descripcion(500),
  confirmar: z.boolean(),
  items: esquemaItems,
});

const migas = (...resto) => migasDe(MIGAS.ventas, ...resto);

/**
 * Diálogos de estado de una venta. Las alertas las emite ModalConfirmar: la
 * roja lleva tal cual la causa del backend (por ejemplo, qué producto no
 * tenía existencias y cuántas faltaban).
 */
function DialogosVenta({ venta, dialogo, onCerrar, alTerminar }) {
  return (
    <>
      <ModalConfirmar
        abierto={dialogo === "confirmar"}
        onCerrar={onCerrar}
        titulo={`Completar venta ${venta?.codigo ?? ""}`}
        textoConfirmar="Completar"
        mensaje="Se descontará el stock de cada producto. Si algún producto no tiene existencias suficientes, la operación se rechaza."
        accion={`completar la venta ${venta?.codigo ?? ""}`.trim()}
        mensajeExito={`Venta ${venta?.codigo} completada: el stock ya bajó`}
        onConfirmar={async () => {
          await api.post(`${URL}/${venta.id}/confirmar`);
          alTerminar();
        }}
      />
      <ModalConfirmar
        abierto={dialogo === "anular"}
        onCerrar={onCerrar}
        destructivo
        titulo={`Anular venta ${venta?.codigo ?? ""}`}
        textoConfirmar="Anular venta"
        mensaje={
          venta?.estado === "completada"
            ? "La venta estaba completada: el stock descontado volverá al inventario. Esta acción no se puede deshacer."
            : "La venta pendiente quedará anulada. Esta acción no se puede deshacer."
        }
        accion={`anular la venta ${venta?.codigo ?? ""}`.trim()}
        mensajeExito={`Venta ${venta?.codigo} anulada`}
        onConfirmar={async () => {
          await api.post(`${URL}/${venta.id}/anular`);
          alTerminar();
        }}
      />
    </>
  );
}

export function VentasLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [filtroEstado, setFiltroEstado] = useState("");
  const listado = useListadoPaginado(URL, { filtros: filtroEstado ? { estado: filtroEstado } : {} });
  const [dialogo, setDialogo] = useState(null);
  const registro = dialogo?.registro;

  const columnas = [
    {
      clave: "codigo",
      titulo: "N.º",
      cifra: true,
      render: (r) => (
        <Link to={`${RUTA}/${r.id}`} className="enlace">
          {r.codigo}
        </Link>
      ),
    },
    { clave: "fecha", ajustar: true, titulo: "Fecha", render: (r) => formatearFecha(r.fecha) },
    { clave: "cliente_nombre", titulo: "Cliente" },
    { clave: "items", titulo: "Ítems", cifra: true, render: (r) => formatearNumero(r.items?.length ?? 0) },
    { clave: "total", titulo: "Total", cifra: true, render: (r) => formatearMoneda(r.total) },
    { clave: "estado", ajustar: true, titulo: "Estado", render: (r) => <Badge variante={varianteDeEstado(r.estado)}>{etiquetaDeEstado(r.estado)}</Badge> },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (r) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${RUTA}/${r.id}`)} />
          <BotonPdf url={`${URL}/${r.id}/pdf`} nombreArchivo={`${r.codigo}.pdf`} />
          {puede("ventas", "cambiar_estado") && r.estado === "pendiente" && (
            <BotonAccion
              icono={Check}
              etiqueta="Completar"
              titulo="Completar (descuenta stock)"
              onClick={() => setDialogo({ tipo: "confirmar", registro: r })}
            />
          )}
          {puede("ventas", "anular") && (r.estado === "pendiente" || r.estado === "completada") && (
            <BotonAccion icono={Ban} etiqueta="Anular" onClick={() => setDialogo({ tipo: "anular", registro: r })} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Ventas"
        descripcion="Registro de ventas. Al completar una venta se descuenta el stock."
        migas={migas()}
        acciones={
          puede("ventas", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Registrar venta
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar="ventas"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por número, cliente, documento o notas..."
        vacio="Todavía no hay ventas registradas."
        filtros={
          <Select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} className="w-44" aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {etiquetaDeEstado(e)}
              </option>
            ))}
          </Select>
        }
      />

      <DialogosVenta
        venta={registro}
        dialogo={dialogo?.tipo}
        onCerrar={() => setDialogo(null)}
        alTerminar={listado.recargar}
      />
    </div>
  );
}

export function VentaNueva() {
  const { items: productos } = useCatalogo("/compras/productos");
  const esquema = useMemo(() => ESQUEMA, []);
  const formVacio = useMemo(
    () => ({ cliente_nombre: "", cliente_documento: "", fecha: fechaLocalAhora(), notas: "", confirmar: true, items: [ITEM_VACIO] }),
    []
  );
  const f = useFormulario(esquema, formVacio);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Venta registrada", accion: "registrar la venta" });
  const [errorStock, setErrorStock] = useState(null);

  // Aviso de stock antes de enviar (el backend vuelve a validarlo y nunca
  // deja el stock en negativo).
  function faltaStock() {
    if (!f.form.confirmar) return null;
    const porProducto = {};
    for (const it of f.form.items) porProducto[it.producto_id] = (porProducto[it.producto_id] ?? 0) + Number(it.cantidad);
    for (const [id, cant] of Object.entries(porProducto)) {
      const p = productos.find((x) => x.id === id);
      if (p && p.stock < cant) return `Stock insuficiente para "${p.nombre}": disponible ${p.stock}, solicitado ${cant}.`;
    }
    return null;
  }

  function enviar(e) {
    e.preventDefault();
    const falta = faltaStock();
    setErrorStock(falta);
    if (falta) return;
    guardar(e, (d) =>
      api.post(URL, {
        cliente_nombre: d.cliente_nombre,
        cliente_documento: d.cliente_documento.trim() || null,
        fecha: new Date(d.fecha).toISOString(),
        notas: d.notas || null,
        confirmar: d.confirmar,
        items: d.items.map((it) => ({ producto_id: it.producto_id, cantidad: Number(it.cantidad), precio_unitario: it.precio_unitario })),
      })
    );
  }

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Registrar venta" descripcion="Al completar la venta se descuenta el stock; nunca queda en negativo." migas={migas({ etiqueta: "Registrar venta" })} />
      <FormularioPantalla
        id="form-venta"
        onSubmit={enviar}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar={`Registrar venta · ${formatearMoneda(totalDeItems(f.form.items))}`}
        errorGeneral={errorStock ?? errorGeneral}
      >
        <Seccion titulo="1. Cliente" descripcion="Los campos marcados con * son obligatorios.">
          <Input etiqueta="Nombre del cliente" {...f.props("cliente_nombre")} permitir="nombre" maxLength={80} autoComplete="off" />
          <div className="fila-campos">
            <Input etiqueta="Documento" {...f.props("cliente_documento", { requerido: false })} cifra permitir="documento_nit" maxLength={12} ayuda="Cédula o NIT con dígito (opcional)" />
            <Input etiqueta="Fecha de la venta" type="datetime-local" {...f.props("fecha")} max={fechaLocalAhora()} ayuda="No puede ser futura" />
          </div>
        </Seccion>

        <Seccion titulo="2. Productos" descripcion="Se muestra el stock disponible de cada producto.">
          <ItemsEditor
            items={f.form.items}
            onCambiar={(items) => f.setForm((prev) => ({ ...prev, items }))}
            productos={productos}
            mostrarStock
            errorDe={(i, campo) => f.errorVisible(`items.${i}.${campo}`)}
            alSalir={(i, campo) => f.tocar(`items.${i}.${campo}`)}
          />
        </Seccion>

        <Seccion titulo="3. Cierre">
          <Textarea etiqueta="Notas" {...f.props("notas", { requerido: false })} maxLength={500} ayuda="Opcional" />
          <Checkbox checked={f.form.confirmar} onChange={(e) => f.setCampo("confirmar", e.target.checked)} etiqueta="Completar de inmediato (descuenta el stock ahora mismo)" />
        </Seccion>
      </FormularioPantalla>
    </div>
  );
}

export function VentaDetalle() {
  const { id } = useParams();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogo, setDialogo] = useState(null);

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data ? `Venta ${data.codigo}` : "Venta"}
      descripcion={data ? `${formatearFecha(data.fecha)} · ${data.cliente_nombre}` : undefined}
      migas={migas({ etiqueta: data?.codigo ?? "…" })}
      error={error}
      datos={data}
      acciones={
        data && (
          <>
            <BotonPdf url={`${URL}/${data.id}/pdf`} nombreArchivo={`${data.codigo}.pdf`} texto="Ver factura PDF" />
            {puede("ventas", "anular") && (data.estado === "pendiente" || data.estado === "completada") && (
              <Button variante="terciario" onClick={() => setDialogo("anular")}>
                <Ban size={14} /> Anular
              </Button>
            )}
            {puede("ventas", "cambiar_estado") && data.estado === "pendiente" && (
              <Button onClick={() => setDialogo("confirmar")}>
                <Check size={14} /> Completar venta
              </Button>
            )}
          </>
        )
      }
    >
      {data && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Datos de la venta">
              <Detalle
                campos={[
                  { etiqueta: "Cliente", valor: data.cliente_nombre },
                  { etiqueta: "Documento", valor: data.cliente_documento, cifra: true },
                  { etiqueta: "Fecha", valor: formatearFecha(data.fecha) },
                  { etiqueta: "Estado", valor: <Badge variante={varianteDeEstado(data.estado)}>{etiquetaDeEstado(data.estado)}</Badge> },
                  { etiqueta: "Registrada", valor: formatearFecha(data.created_at) },
                  { etiqueta: "Notas", valor: data.notas },
                ]}
              />
            </Card>
            <Card titulo="Total">
              <p className="dato-grande cifra">{formatearMoneda(data.total)}</p>
              <p className="text-[12px] text-[var(--texto-terciario)] mt-1">
                {data.items?.length ?? 0} línea(s) · {formatearNumero(data.items?.reduce((a, i) => a + i.cantidad, 0) ?? 0)} unidades
              </p>
            </Card>
          </div>

          <Card titulo="Productos">
            <Table
              columnas={[
                {
                  clave: "producto_nombre",
                  titulo: "Producto",
                  render: (i) =>
                    i.producto_id ? (
                      <Link to={`/compras/productos/${i.producto_id}`} className="enlace">
                        {i.producto_nombre ?? "—"}
                      </Link>
                    ) : (
                      i.producto_nombre ?? "—"
                    ),
                },
                { clave: "producto_sku", ajustar: true, titulo: "SKU", render: (i) => <span className="cifra">{i.producto_sku ?? "—"}</span> },
                { clave: "cantidad", titulo: "Cant.", cifra: true, render: (i) => formatearNumero(i.cantidad) },
                { clave: "precio_unitario", titulo: "Precio unit.", cifra: true, render: (i) => formatearMoneda(i.precio_unitario) },
                { clave: "subtotal", titulo: "Subtotal", cifra: true, render: (i) => formatearMoneda(i.subtotal) },
              ]}
              filas={data.items}
            />
          </Card>
        </div>
      )}

      <DialogosVenta
        venta={data}
        dialogo={dialogo}
        onCerrar={() => setDialogo(null)}
        alTerminar={recargar}
      />
    </PantallaDetalle>
  );
}
