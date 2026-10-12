import { useEffect, useMemo, useState } from "react";
import { Ban, Check, Eye, Plus } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import ItemsEditor, { ITEM_VACIO, totalDeItems } from "@/components/ItemsEditor";
import BotonPdf from "@/components/BotonPdf";
import PantallaDetalle from "@/components/PantallaDetalle";
import SelectorBusqueda from "@/components/SelectorBusqueda";
import { api } from "@/lib/api";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { useAuth } from "@/context/AuthContext";
import { fechaLocalAhora, formatearFecha, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemaItems, esquemas } from "@/lib/validaciones";
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

const RUTA = "/compras";
const URL = "/compras/compras";
const ESTADOS = ["pendiente", "confirmada", "cancelada", "anulada"];

const ESQUEMA = z.object({
  proveedor: z.object({ id: z.string(), nombre: z.string() }).loose().nullable().refine((p) => p !== null, "Selecciona un proveedor"),
  fecha: esquemas.obligatorio().pipe(esquemas.fechaNoFutura()),
  notas: esquemas.descripcion(500),
  confirmar: z.boolean(),
  items: esquemaItems,
});

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
        mensaje="Al confirmar, el stock de cada producto sube según las cantidades de la compra."
        accion={`confirmar la compra ${compra?.codigo ?? ""}`.trim()}
        mensajeExito={`Compra ${compra?.codigo} confirmada: el stock ya subió`}
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
            ? "La compra estaba confirmada: el stock que ingresó se revertirá. Esta acción no se puede deshacer."
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
          {puede("compras", "cambiar_estado") && r.estado === "pendiente" && (
            <BotonAccion
              icono={Check}
              etiqueta="Confirmar"
              titulo="Confirmar (sube el stock)"
              onClick={() => setDialogo({ tipo: "confirmar", registro: r })}
            />
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
        descripcion="Órdenes de compra a proveedores. Al confirmar, el stock de cada producto sube."
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

      <DialogosCompra
        compra={registro}
        dialogo={dialogo?.tipo}
        onCerrar={() => setDialogo(null)}
        alTerminar={listado.recargar}
      />
    </div>
  );
}

/**
 * Registrar compra: primero el proveedor (búsqueda en vivo); el selector de
 * productos se limita a los que ese proveedor surte, con la opción de ver
 * todos. Líneas con subtotal y total en vivo.
 */
export function CompraNueva() {
  const [parametros] = useSearchParams();
  const proveedorInicial = parametros.get("proveedor");
  const esquema = useMemo(() => ESQUEMA, []);
  const formVacio = useMemo(() => ({ proveedor: null, fecha: fechaLocalAhora(), notas: "", confirmar: true, items: [ITEM_VACIO] }), []);
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
  const proveedorSurte = proveedor?.productos?.length ?? 0;
  const urlProductos = useMemo(() => {
    const base = "/compras/productos?por_pagina=100&activo=true";
    return proveedor && !verTodos && proveedorSurte > 0 ? `${base}&proveedor_id=${proveedor.id}` : base;
  }, [proveedor, verTodos, proveedorSurte]);
  const { data: productosData } = useApiResource(urlProductos);
  const productos = productosData?.items ?? [];

  function cambiarProveedor(nuevo) {
    // Al cambiar de proveedor, las líneas vuelven a empezar: los productos
    // ofrecidos cambian.
    f.setForm((prev) => ({ ...prev, proveedor: nuevo, items: [ITEM_VACIO] }));
    setVerTodos(false);
  }

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Registrar compra" descripcion="Elige el proveedor, agrega los productos comprados y confirma para que el stock suba." migas={migas({ etiqueta: "Registrar compra" })} />
      <FormularioPantalla
        id="form-compra"
        onSubmit={(e) =>
          guardar(e, (d) =>
            api.post(URL, {
              proveedor_id: d.proveedor.id,
              fecha: new Date(d.fecha).toISOString(),
              notas: d.notas || null,
              confirmar: d.confirmar,
              items: d.items.map((it) => ({ producto_id: it.producto_id, cantidad: Number(it.cantidad), precio_unitario: it.precio_unitario })),
            })
          )
        }
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar={`Registrar compra · ${formatearMoneda(totalDeItems(f.form.items))}`}
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
              ayuda={proveedor ? `Surte ${proveedorSurte} producto(s)` : undefined}
            />
            <Input etiqueta="Fecha de la compra" type="datetime-local" {...f.props("fecha")} max={fechaLocalAhora()} ayuda="No puede ser futura" />
          </div>
        </Seccion>

        <Seccion
          titulo="2. Productos"
          descripcion={
            !proveedor
              ? "Primero elige el proveedor."
              : proveedorSurte > 0 && !verTodos
                ? `Se muestran solo los ${proveedorSurte} producto(s) que surte ${proveedor.nombre}.`
                : "Se muestran todos los productos activos."
          }
        >
          {proveedor && proveedorSurte > 0 && (
            <Checkbox checked={verTodos} onChange={(e) => setVerTodos(e.target.checked)} etiqueta="Mostrar todos los productos, no solo los de este proveedor" />
          )}
          <div className={proveedor ? "" : "opacity-50 pointer-events-none"} aria-disabled={!proveedor}>
            <ItemsEditor
              items={f.form.items}
              onCambiar={(items) => f.setForm((prev) => ({ ...prev, items }))}
              productos={productos}
              precioSugerido={(p) => p.precio_compra ?? p.precio}
              etiquetaPrecio="Costo unitario"
              mostrarStock
              errorDe={(i, campo) => f.errorVisible(`items.${i}.${campo}`)}
              alSalir={(i, campo) => f.tocar(`items.${i}.${campo}`)}
            />
          </div>
        </Seccion>

        <Seccion titulo="3. Cierre">
          <Textarea etiqueta="Notas" {...f.props("notas", { requerido: false })} maxLength={500} ayuda="Opcional: número de factura del proveedor, condiciones, etc." />
          <Checkbox checked={f.form.confirmar} onChange={(e) => f.setCampo("confirmar", e.target.checked)} etiqueta="Confirmar de inmediato (el stock sube ahora mismo)" />
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
                      <Link to={`/compras/proveedores/${data.proveedor_id}`} className="enlace">
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
                { clave: "precio_unitario", titulo: "Costo unit.", cifra: true, render: (i) => formatearMoneda(i.precio_unitario) },
                { clave: "subtotal", titulo: "Subtotal", cifra: true, render: (i) => formatearMoneda(i.subtotal) },
              ]}
              filas={data.items}
            />
          </Card>
        </div>
      )}

      <DialogosCompra
        compra={data}
        dialogo={dialogo}
        onCerrar={() => setDialogo(null)}
        alTerminar={recargar}
      />
    </PantallaDetalle>
  );
}
