import { useEffect, useMemo, useState } from "react";
import { Ban, Check, Eye, Plus } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import BotonPdf from "@/components/BotonPdf";
import EditorLineas from "@/components/EditorLineas";
import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import SelectorBusqueda from "@/components/SelectorBusqueda";
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
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { fechaLocalAhora, formatearFecha, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { legible, unidadesDe } from "@/lib/unidades";
import { esquemas } from "@/lib/validaciones";

/**
 * COMPRAS DE INSUMOS (2026-10-12). Primero el proveedor; luego sus insumos,
 * cada uno en la unidad en que se compró (kg aunque el insumo se lleve en g)
 * con su precio POR ESA unidad, subtotal y total en vivo. Al confirmar suben
 * las existencias y el costo de cada insumo se actualiza por promedio
 * ponderado; anular revierte lo que sumó.
 */
const RUTA = "/inventario/compras";
const URL = "/compras/compras";
const ESTADOS = ["pendiente", "confirmada", "cancelada", "anulada"];

const LINEA = z
  .object({
    insumo_id: z.string().min(1, "Elige el insumo"),
    cantidad: esquemas.cantidad(),
    unidad: z.string().min(1, "Elige la unidad"),
    precio_unitario: esquemas.precio({ permitirCero: true }),
  })
  .loose();

const ESQUEMA = z.object({
  proveedor: z.object({ id: z.string(), nombre: z.string() }).loose().nullable().refine((p) => p !== null, "Selecciona un proveedor"),
  fecha: esquemas.obligatorio().pipe(esquemas.fechaNoFutura()),
  notas: esquemas.descripcion(500),
  confirmar: z.boolean(),
  items: z.array(LINEA).min(1, "Agrega al menos un insumo"),
});

const LINEA_VACIA = { insumo_id: "", cantidad: "", unidad: "", precio_unitario: "" };
const subtotalDe = (l) => (Number(l.cantidad) || 0) * (Number(l.precio_unitario) || 0);
const totalDe = (items) => items.reduce((acc, l) => acc + subtotalDe(l), 0);

const migas = (...resto) => migasDe(MIGAS.compras, ...resto);

/**
 * Diálogos de estado de una compra. Las alertas (verde con el resultado,
 * roja con la causa que devuelve el backend) las emite ModalConfirmar;
 * aquí solo se dice qué se está haciendo y qué recargar al terminar.
 */
function DialogosCompra({ compra, dialogo, onCerrar, alTerminar }) {
  return (
    <>
      <ModalConfirmar
        abierto={dialogo === "confirmar"}
        onCerrar={onCerrar}
        titulo={`Confirmar compra ${compra?.codigo ?? ""}`}
        textoConfirmar="Confirmar"
        mensaje="Al confirmar, la existencia de cada insumo sube y su costo se actualiza con el promedio ponderado."
        accion={`confirmar la compra ${compra?.codigo ?? ""}`.trim()}
        mensajeExito={`Compra ${compra?.codigo} confirmada: las existencias ya subieron`}
        onConfirmar={async () => {
          await api.post(`${URL}/${compra.id}/confirmar`);
          alTerminar();
        }}
      />
      <ModalConfirmar
        abierto={dialogo === "anular"}
        onCerrar={onCerrar}
        destructivo
        titulo={`Anular compra ${compra?.codigo ?? ""}`}
        textoConfirmar="Anular compra"
        mensaje={
          compra?.estado === "confirmada"
            ? "La compra estaba confirmada: lo que ingresó sale de la bodega y su costo se retira del promedio. Esta acción no se puede deshacer."
            : "La compra pendiente quedará anulada. Esta acción no se puede deshacer."
        }
        accion={`anular la compra ${compra?.codigo ?? ""}`.trim()}
        mensajeExito={`Compra ${compra?.codigo} anulada`}
        onConfirmar={async () => {
          await api.post(`${URL}/${compra.id}/anular`);
          alTerminar();
        }}
      />
    </>
  );
}

export function ComprasLista() {
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
    { clave: "proveedor_nombre", titulo: "Proveedor", render: (r) => r.proveedor_nombre || "—" },
    { clave: "items", titulo: "Insumos", cifra: true, render: (r) => formatearNumero(r.items?.length ?? 0) },
    { clave: "total", titulo: "Total", cifra: true, render: (r) => formatearMoneda(r.total) },
    { clave: "estado", ajustar: true, titulo: "Estado", render: (r) => <Badge variante={varianteDeEstado(r.estado)}>{etiquetaDeEstado(r.estado)}</Badge> },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (r) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${RUTA}/${r.id}`)} />
          <BotonPdf url={`${URL}/${r.id}/pdf`} nombreArchivo={`${r.codigo}.pdf`} />
          {puede("compras", "cambiar_estado") && r.estado === "pendiente" && (
            <BotonAccion icono={Check} etiqueta="Confirmar" titulo="Confirmar (suben las existencias)" onClick={() => setDialogo({ tipo: "confirmar", registro: r })} />
          )}
          {puede("compras", "anular") && (r.estado === "pendiente" || r.estado === "confirmada") && (
            <BotonAccion icono={Ban} etiqueta="Anular" onClick={() => setDialogo({ tipo: "anular", registro: r })} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Compras"
        descripcion="Compras de insumos a proveedores. Al confirmar, suben las existencias y se actualiza el costo de cada insumo."
        migas={migas()}
        acciones={
          puede("compras", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Registrar compra
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar="compras"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por número, proveedor o notas..."
        vacio="Todavía no hay compras registradas."
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

      <DialogosCompra compra={registro} dialogo={dialogo?.tipo} onCerrar={() => setDialogo(null)} alTerminar={listado.recargar} />
    </div>
  );
}

export function CompraNueva() {
  const [parametros] = useSearchParams();
  const proveedorInicial = parametros.get("proveedor");
  const esquema = useMemo(() => ESQUEMA, []);
  const formVacio = useMemo(() => ({ proveedor: null, fecha: fechaLocalAhora(), notas: "", confirmar: true, items: [{ ...LINEA_VACIA, _id: "inicial" }] }), []);
  const f = useFormulario(esquema, formVacio);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Compra registrada", accion: "registrar la compra" });
  const [verTodos, setVerTodos] = useState(false);

  // Si se llega desde el detalle de un proveedor (?proveedor=id), se precarga.
  const { data: proveedorPrecargado } = useApiResource(proveedorInicial ? `/compras/proveedores/${proveedorInicial}` : null);
  useEffect(() => {
    if (proveedorPrecargado) f.setForm((prev) => ({ ...prev, proveedor: proveedorPrecargado }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proveedorPrecargado]);

  const proveedor = f.form.proveedor;
  const proveedorSurte = proveedor?.insumos?.length ?? 0;
  const urlInsumos = useMemo(() => {
    const base = "/inventario/insumos?por_pagina=100&activo=true";
    return proveedor && !verTodos && proveedorSurte > 0 ? `${base}&proveedor_id=${proveedor.id}` : base;
  }, [proveedor, verTodos, proveedorSurte]);
  const { data: insumosData } = useApiResource(urlInsumos);
  const insumos = useMemo(() => insumosData?.items ?? [], [insumosData]);
  const porId = useMemo(() => Object.fromEntries(insumos.map((i) => [i.id, i])), [insumos]);

  function cambiarProveedor(nuevo) {
    // Al cambiar de proveedor, las líneas vuelven a empezar: los insumos ofrecidos cambian.
    f.setForm((prev) => ({ ...prev, proveedor: nuevo, items: [{ ...LINEA_VACIA, _id: `p-${Date.now()}` }] }));
    setVerTodos(false);
  }

  const items = f.form.items;
  return (
    <div className="pantalla-estrecha">
      <PageHeader
        volver={RUTA}
        titulo="Registrar compra"
        descripcion="Elige el proveedor, agrega los insumos comprados y confirma para que suban las existencias."
        migas={migas({ etiqueta: "Registrar compra" })}
      />
      <FormularioPantalla
        id="form-compra"
        onSubmit={(e) =>
          guardar(e, (d) =>
            api.post(URL, {
              proveedor_id: d.proveedor.id,
              fecha: new Date(d.fecha).toISOString(),
              notas: d.notas || null,
              confirmar: d.confirmar,
              items: d.items.map((it) => ({ insumo_id: it.insumo_id, cantidad: it.cantidad, unidad: it.unidad, precio_unitario: it.precio_unitario })),
            })
          )
        }
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar={`Registrar compra · ${formatearMoneda(totalDe(items))}`}
        errorGeneral={errorGeneral}
      >
        <Seccion titulo="1. Proveedor" descripcion="Busca por nombre, NIT o documento.">
          <div className="fila-campos">
            <SelectorBusqueda
              url="/compras/proveedores"
              filtros={{ activo: true }}
              etiqueta="Proveedor"
              required
              valor={proveedor}
              onCambiar={cambiarProveedor}
              placeholder="Buscar proveedor..."
              etiquetaDe={(p) => p.nombre}
              detalleDe={(p) => p.nit ?? p.numero_documento ?? null}
              nombreCampo="proveedor"
              error={f.errorVisible("proveedor")}
              ayuda={proveedor ? `Surte ${proveedorSurte} insumo(s)` : undefined}
            />
            <Input etiqueta="Fecha de la compra" type="datetime-local" {...f.props("fecha")} max={fechaLocalAhora()} ayuda="No puede ser futura" />
          </div>
        </Seccion>

        <Seccion
          titulo="2. Insumos"
          descripcion={
            !proveedor
              ? "Primero elige el proveedor."
              : proveedorSurte > 0 && !verTodos
                ? `Se muestran solo los ${proveedorSurte} insumo(s) que surte ${proveedor.nombre}.`
                : "Se muestran todos los insumos activos."
          }
        >
          {proveedor && proveedorSurte > 0 && (
            <Checkbox checked={verTodos} onChange={(e) => setVerTodos(e.target.checked)} etiqueta="Mostrar todos los insumos, no solo los de este proveedor" />
          )}
          <div className={proveedor ? "" : "opacity-50 pointer-events-none"} aria-disabled={!proveedor}>
            <EditorLineas
              filas={items}
              onCambiar={(filas) => f.setForm((prev) => ({ ...prev, items: filas }))}
              nueva={() => LINEA_VACIA}
              minimo={1}
              maximo={60}
              textoAgregar="Agregar insumo"
              quitarEtiqueta="Quitar insumo de la línea"
              columnas={[
                {
                  clave: "insumo",
                  etiqueta: "Insumo",
                  render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                    <Select
                      etiqueta={etiqueta}
                      aria-label={ariaLabel}
                      required
                      value={fila.insumo_id}
                      onChange={(e) => cambiar({ insumo_id: e.target.value, unidad: porId[e.target.value]?.unidad ?? "" })}
                      onBlur={() => f.tocar(`items.${i}.insumo_id`)}
                      error={f.errorVisible(`items.${i}.insumo_id`)}
                      data-campo={`items.${i}.insumo_id`}
                    >
                      <option value="">Insumo…</option>
                      {insumos.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.nombre} (hay {legible(x.existencia, x.unidad)})
                        </option>
                      ))}
                    </Select>
                  ),
                },
                {
                  clave: "cantidad",
                  etiqueta: "Cantidad",
                  ancho: "6.5rem",
                  render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                    <Input
                      etiqueta={etiqueta}
                      aria-label={ariaLabel}
                      required
                      cifra
                      permitir="cantidad"
                      value={fila.cantidad}
                      onChange={(e) => cambiar("cantidad", e.target.value)}
                      onBlur={() => f.tocar(`items.${i}.cantidad`)}
                      error={f.errorVisible(`items.${i}.cantidad`)}
                      data-campo={`items.${i}.cantidad`}
                    />
                  ),
                },
                {
                  clave: "unidad",
                  etiqueta: "Unidad",
                  ancho: "6rem",
                  render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                    <Select
                      etiqueta={etiqueta}
                      aria-label={ariaLabel}
                      required
                      disabled={!porId[fila.insumo_id]}
                      value={fila.unidad}
                      onChange={(e) => cambiar("unidad", e.target.value)}
                      onBlur={() => f.tocar(`items.${i}.unidad`)}
                      error={f.errorVisible(`items.${i}.unidad`)}
                      data-campo={`items.${i}.unidad`}
                    >
                      <option value="">Unidad</option>
                      {(porId[fila.insumo_id] ? unidadesDe(porId[fila.insumo_id].unidad) : []).map((u) => (
                        <option key={u.valor} value={u.valor}>
                          {u.valor}
                        </option>
                      ))}
                    </Select>
                  ),
                },
                {
                  clave: "precio",
                  etiqueta: "Precio por unidad",
                  ancho: "8rem",
                  render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                    <Input
                      etiqueta={etiqueta}
                      aria-label={ariaLabel}
                      required
                      cifra
                      permitir="decimal"
                      value={fila.precio_unitario}
                      onChange={(e) => cambiar("precio_unitario", e.target.value)}
                      onBlur={() => f.tocar(`items.${i}.precio_unitario`)}
                      error={f.errorVisible(`items.${i}.precio_unitario`)}
                      data-campo={`items.${i}.precio_unitario`}
                    />
                  ),
                },
              ]}
              debajo={(fila) => (
                <>
                  Subtotal: <span className="cifra">{formatearMoneda(subtotalDe(fila))}</span>
                </>
              )}
              pie={
                <>
                  <span>
                    {items.length} {items.length === 1 ? "línea" : "líneas"}
                  </span>
                  <span>
                    Total: <strong className="cifra">{formatearMoneda(totalDe(items))}</strong>
                  </span>
                </>
              }
            />
          </div>
        </Seccion>

        <Seccion titulo="3. Cierre">
          <Textarea etiqueta="Notas" {...f.props("notas", { requerido: false })} maxLength={500} ayuda="Opcional: número de factura del proveedor, condiciones, etc." />
          <Checkbox checked={f.form.confirmar} onChange={(e) => f.setCampo("confirmar", e.target.checked)} etiqueta="Confirmar de inmediato (las existencias suben ahora mismo)" />
        </Seccion>
      </FormularioPantalla>
    </div>
  );
}

export function CompraDetalle() {
  const { id } = useParams();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogo, setDialogo] = useState(null);

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data ? `Compra ${data.codigo}` : "Compra"}
      descripcion={data ? `${formatearFecha(data.fecha)} · ${data.proveedor_nombre ?? "sin proveedor"}` : undefined}
      migas={migas({ etiqueta: data?.codigo ?? "…" })}
      error={error}
      datos={data}
      acciones={
        data && (
          <>
            <BotonPdf url={`${URL}/${data.id}/pdf`} nombreArchivo={`${data.codigo}.pdf`} texto="Ver PDF" />
            {puede("compras", "anular") && (data.estado === "pendiente" || data.estado === "confirmada") && (
              <Button variante="terciario" onClick={() => setDialogo("anular")}>
                <Ban size={14} /> Anular
              </Button>
            )}
            {puede("compras", "cambiar_estado") && data.estado === "pendiente" && (
              <Button onClick={() => setDialogo("confirmar")}>
                <Check size={14} /> Confirmar compra
              </Button>
            )}
          </>
        )
      }
    >
      {data && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Datos de la compra">
              <Detalle
                campos={[
                  {
                    etiqueta: "Proveedor",
                    valor: data.proveedor_id ? (
                      <Link to={`/inventario/proveedores/${data.proveedor_id}`} className="enlace">
                        {data.proveedor_nombre}
                      </Link>
                    ) : (
                      data.proveedor_nombre
                    ),
                  },
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
                {data.items?.length ?? 0} {data.items?.length === 1 ? "insumo" : "insumos"}
              </p>
            </Card>
          </div>

          <Card titulo="Insumos">
            <Table
              columnas={[
                {
                  clave: "insumo_nombre",
                  titulo: "Insumo",
                  render: (i) => (
                    <Link to={`/inventario/insumos/${i.insumo_id}`} className="enlace">
                      {i.insumo_nombre ?? "—"}
                    </Link>
                  ),
                },
                { clave: "cantidad", titulo: "Cantidad", cifra: true, render: (i) => legible(i.cantidad, i.unidad) },
                { clave: "precio_unitario", titulo: "Precio", cifra: true, render: (i) => `${formatearMoneda(i.precio_unitario)} por ${i.unidad}` },
                { clave: "subtotal", titulo: "Subtotal", cifra: true, render: (i) => formatearMoneda(i.subtotal) },
              ]}
              filas={data.items}
            />
          </Card>
        </div>
      )}

      <DialogosCompra compra={data} dialogo={dialogo} onCerrar={() => setDialogo(null)} alTerminar={recargar} />
    </PantallaDetalle>
  );
}
