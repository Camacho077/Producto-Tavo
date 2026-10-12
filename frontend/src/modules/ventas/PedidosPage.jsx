import { useCallback, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { ArrowRight, Eye, Pencil, Plus } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

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
import { formatearFecha, formatearFechaHora, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemaItems, esquemas } from "@/lib/validaciones";
import {
  AccionesFila,
  Badge,
  BotonAccion,
  Button,
  Card,
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

const RUTA = "/ventas/pedidos";
const URL = "/ventas/pedidos";
const ESTADOS = ["pendiente", "en_proceso", "listo", "entregado", "cancelado"];
const PRIORIDADES = ["urgente", "alta", "media", "baja"];
// Mismas transiciones que el backend (ventas/services.py) para ofrecer solo
// los botones válidos; el backend sigue validando.
const TRANSICIONES = {
  pendiente: ["en_proceso", "cancelado"],
  en_proceso: ["listo", "cancelado"],
  listo: ["entregado", "en_proceso", "cancelado"],
  entregado: [],
  cancelado: [],
};
const ABIERTO = (estado) => !["entregado", "cancelado"].includes(estado);
const REFRESCO_SEGUIMIENTO_MS = 8000;

const FORM_VACIO = {
  cliente_nombre: "",
  cliente_telefono: "",
  cliente_direccion: "",
  fecha_entrega: "",
  prioridad: "media",
  notas: "",
  items: [ITEM_VACIO],
};

const ESQUEMA = z.object({
  cliente_nombre: esquemas.nombreItem(80),
  cliente_telefono: esquemas.telefono(),
  cliente_direccion: esquemas.descripcion(255),
  fecha_entrega: esquemas.fechaNoPasada(),
  prioridad: z.enum(["baja", "media", "alta", "urgente"]),
  notas: esquemas.descripcion(500),
  items: esquemaItems,
});

const migas = (...resto) => migasDe(MIGAS.pedidos, ...resto);

function fechaLocalHoy() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T00:00`;
}

function variantePrioridad(prioridad) {
  return { urgente: "negativo", alta: "advertencia", media: "acento", baja: "neutro" }[prioridad] ?? "neutro";
}

function aFechaLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function cuerpoDe(d) {
  return {
    cliente_nombre: d.cliente_nombre,
    cliente_telefono: d.cliente_telefono || null,
    cliente_direccion: d.cliente_direccion || null,
    fecha_entrega: d.fecha_entrega ? new Date(d.fecha_entrega).toISOString() : null,
    prioridad: d.prioridad,
    notas: d.notas || null,
    items: d.items.map((it) => ({ producto_id: it.producto_id, cantidad: Number(it.cantidad), precio_unitario: it.precio_unitario })),
  };
}

export function PedidosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroPrioridad, setFiltroPrioridad] = useState("");
  const listado = useListadoPaginado(URL, {
    filtros: { ...(filtroEstado ? { estado: filtroEstado } : {}), ...(filtroPrioridad ? { prioridad: filtroPrioridad } : {}) },
  });

  const columnas = [
    {
      clave: "codigo",
      titulo: "N.º",
      cifra: true,
      render: (p) => (
        <Link to={`${RUTA}/${p.id}`} className="enlace">
          {p.codigo}
        </Link>
      ),
    },
    {
      clave: "prioridad", ajustar: true,
      titulo: "Prioridad",
      render: (p) => <Badge variante={variantePrioridad(p.prioridad)}>{etiquetaDeEstado(p.prioridad)}</Badge>,
    },
    { clave: "cliente_nombre", titulo: "Cliente" },
    { clave: "fecha_entrega", ajustar: true, titulo: "Entrega", render: (p) => (p.fecha_entrega ? formatearFechaHora(p.fecha_entrega) : "—") },
    { clave: "total", titulo: "Total", cifra: true, render: (p) => formatearMoneda(p.total) },
    {
      clave: "estado", ajustar: true,
      titulo: "Estado",
      render: (p) => <Badge variante={varianteDeEstado(p.estado)}>{etiquetaDeEstado(p.estado)}</Badge>,
    },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (p) => (
        <AccionesFila>
          <BotonAccion
            icono={Eye}
            etiqueta="Ver detalle y seguimiento"
            titulo="Detalle y seguimiento"
            onClick={() => navigate(`${RUTA}/${p.id}`)}
          />
          {puede("pedidos", "editar") && ABIERTO(p.estado) && (
            <BotonAccion icono={Pencil} etiqueta="Editar" onClick={() => navigate(`${RUTA}/${p.id}/editar`)} />
          )}
          <BotonPdf url={`${URL}/${p.id}/pdf`} nombreArchivo={`${p.codigo}.pdf`} />
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Pedidos"
        descripcion="Compromisos con clientes, ordenados por prioridad. No mueven stock hasta que se registra la venta."
        migas={migas()}
        acciones={
          puede("pedidos", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Nuevo pedido
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar="pedidos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por número, cliente, teléfono o notas..."
        vacio="Todavía no hay pedidos registrados."
        filtros={
          <>
            <Select value={filtroPrioridad} onChange={(e) => setFiltroPrioridad(e.target.value)} className="w-40" aria-label="Filtrar por prioridad">
              <option value="">Toda prioridad</option>
              {PRIORIDADES.map((p) => (
                <option key={p} value={p}>
                  {etiquetaDeEstado(p)}
                </option>
              ))}
            </Select>
            <Select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
              <option value="">Todos los estados</option>
              {ESTADOS.map((e) => (
                <option key={e} value={e}>
                  {etiquetaDeEstado(e)}
                </option>
              ))}
            </Select>
          </>
        }
      />
    </div>
  );
}

function CamposPedido({ f, productos }) {
  return (
    <>
      <Seccion titulo="1. Cliente y entrega" descripcion="Los campos marcados con * son obligatorios.">
        <div className="fila-campos">
          <Input etiqueta="Cliente" {...f.props("cliente_nombre")} permitir="nombre" maxLength={80} autoComplete="off" />
          <Input etiqueta="Teléfono" {...f.props("cliente_telefono", { requerido: false })} cifra permitir="telefono" placeholder="300 123 4567" ayuda="Celular (3…) o fijo (60…)" />
        </div>
        <Input etiqueta="Dirección de entrega" {...f.props("cliente_direccion", { requerido: false })} maxLength={255} ayuda="Opcional" />
        <div className="fila-campos">
          <Select etiqueta="Prioridad" {...f.props("prioridad")}>
            {PRIORIDADES.map((p) => (
              <option key={p} value={p}>
                {etiquetaDeEstado(p)}
              </option>
            ))}
          </Select>
          <Input etiqueta="Fecha de entrega" type="datetime-local" {...f.props("fecha_entrega", { requerido: false })} min={fechaLocalHoy()} ayuda="Hoy o después" />
        </div>
      </Seccion>

      <Seccion titulo="2. Productos" descripcion="El pedido no mueve stock; se muestra el disponible como referencia.">
        <ItemsEditor
          items={f.form.items}
          onCambiar={(items) => f.setForm((prev) => ({ ...prev, items }))}
          productos={productos}
          mostrarStock
          errorDe={(i, campo) => f.errorVisible(`items.${i}.${campo}`)}
          alSalir={(i, campo) => f.tocar(`items.${i}.${campo}`)}
        />
      </Seccion>

      <Seccion titulo="3. Notas">
        <Textarea etiqueta="Notas" {...f.props("notas", { requerido: false })} maxLength={500} ayuda="Opcional" />
      </Seccion>
    </>
  );
}

export function PedidoNuevo() {
  const { items: productos } = useCatalogo("/compras/productos");
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Pedido registrado", accion: "registrar el pedido" });

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo pedido" descripcion="Cliente, prioridad, fecha de entrega y productos." migas={migas({ etiqueta: "Nuevo pedido" })} />
      <FormularioPantalla
        id="form-pedido"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, { ...cuerpoDe(d), fecha: new Date().toISOString() }))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar={`Registrar pedido · ${formatearMoneda(totalDeItems(f.form.items))}`}
        errorGeneral={errorGeneral}
      >
        <CamposPedido f={f} productos={productos} />
      </FormularioPantalla>
    </div>
  );
}

export function PedidoEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const { items: productos } = useCatalogo("/compras/productos");
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el pedido" });

  useEffect(() => {
    if (!data) return;
    f.reiniciar({
      cliente_nombre: data.cliente_nombre,
      cliente_telefono: data.cliente_telefono ?? "",
      cliente_direccion: data.cliente_direccion ?? "",
      fecha_entrega: aFechaLocalInput(data.fecha_entrega),
      prioridad: data.prioridad,
      notas: data.notas ?? "",
      items: data.items.map((it) => ({ _id: it.id, producto_id: it.producto_id, cantidad: String(it.cantidad), precio_unitario: String(it.precio_unitario) })),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar pedido ${data.codigo}` : "Editar pedido"}
      migas={migas({ etiqueta: data?.codigo ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      {data && !ABIERTO(data.estado) ? (
        <p className="estado">Este pedido está {etiquetaDeEstado(data.estado).toLowerCase()} y ya no se puede editar.</p>
      ) : (
        <FormularioPantalla
          id="form-pedido"
          onSubmit={(e) => guardar(e, (d) => api.put(`${URL}/${id}`, cuerpoDe(d)))}
          volver={`${RUTA}/${id}`}
          refRaiz={f.raiz}
          hayErrores={f.hayErrores}
          guardando={guardando}
          textoGuardar={`Guardar cambios · ${formatearMoneda(totalDeItems(f.form.items))}`}
          errorGeneral={errorGeneral}
        >
          <CamposPedido f={f} productos={productos} />
        </FormularioPantalla>
      )}
    </PantallaDetalle>
  );
}

/**
 * Seguimiento del pedido: estado actual, botones con las transiciones válidas
 * (cada una confirma en un diálogo con nota opcional) y línea de tiempo.
 * Mientras el pedido siga abierto se refresca solo.
 */
function SeguimientoPedido({ pedido, onActualizado }) {
  const [destino, setDestino] = useState(null);
  const [nota, setNota] = useState("");

  useEffect(() => {
    if (!ABIERTO(pedido.estado)) return undefined;
    const id = setInterval(() => {
      api
        .get(`${URL}/${pedido.id}`)
        .then((res) => onActualizado(res.data))
        .catch(() => {});
    }, REFRESCO_SEGUIMIENTO_MS);
    return () => clearInterval(id);
  }, [pedido.id, pedido.estado, onActualizado]);

  const { puede } = useAuth();
  // Sin permiso de cambiar el estado se ve el seguimiento, no los botones.
  const siguientes = puede("pedidos", "cambiar_estado") ? (TRANSICIONES[pedido.estado] ?? []) : [];
  const eventos = [...(pedido.eventos ?? [])].reverse();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] text-[var(--texto-secundario)]">Estado actual:</span>
        <Badge variante={varianteDeEstado(pedido.estado)}>{etiquetaDeEstado(pedido.estado)}</Badge>
        {ABIERTO(pedido.estado) && <span className="text-[12px] text-[var(--texto-terciario)]">· se actualiza en vivo</span>}
      </div>

      {siguientes.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {siguientes.map((estado) => (
            <Button
              key={estado}
              tamano="sm"
              variante={estado === "cancelado" ? "destructivo" : "primario"}
              onClick={() => {
                setNota("");
                setDestino(estado);
              }}
            >
              {estado !== "cancelado" && <ArrowRight size={14} />} {etiquetaDeEstado(estado)}
            </Button>
          ))}
        </div>
      )}

      <ol className="linea-tiempo" aria-label="Historial del pedido">
        {eventos.map((ev, i) => (
          <li key={ev.id} className={`linea-tiempo__evento ${i === 0 ? "linea-tiempo__evento--actual" : ""}`}>
            <span className="linea-tiempo__punto" aria-hidden="true" />
            <div className="linea-tiempo__titulo">
              <Badge variante={varianteDeEstado(ev.estado)}>{etiquetaDeEstado(ev.estado)}</Badge>
              <span className="linea-tiempo__meta">
                {formatearFechaHora(ev.created_at)}
                {ev.usuario_nombre ? ` · ${ev.usuario_nombre}` : ""}
              </span>
            </div>
            {ev.nota && <p className="linea-tiempo__nota">{ev.nota}</p>}
          </li>
        ))}
      </ol>

      <ModalConfirmar
        abierto={destino !== null}
        onCerrar={() => setDestino(null)}
        destructivo={destino === "cancelado"}
        titulo={destino ? `Pasar a ${etiquetaDeEstado(destino).toLowerCase()}` : ""}
        textoConfirmar={destino ? etiquetaDeEstado(destino) : "Confirmar"}
        mensaje={`El pedido ${pedido.codigo} pasará de "${etiquetaDeEstado(pedido.estado)}" a "${destino ? etiquetaDeEstado(destino) : ""}".`}
        accion={`pasar el pedido ${pedido.codigo} a ${destino ? etiquetaDeEstado(destino).toLowerCase() : ""}`.trim()}
        mensajeExito={`Pedido ${pedido.codigo}: ${destino ? etiquetaDeEstado(destino).toLowerCase() : ""}`}
        onConfirmar={async () => {
          const { data } = await api.patch(`${URL}/${pedido.id}/estado`, { estado: destino, nota: nota || null });
          onActualizado(data);
        }}
      >
        <Input etiqueta="Nota del cambio" value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Opcional: qué pasó en este paso" maxLength={500} />
      </ModalConfirmar>
    </div>
  );
}

export function PedidoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error } = useApiResource(`${URL}/${id}`);
  // Copia local que el seguimiento actualiza (cambio de estado, refresco).
  const [pedido, setPedido] = useState(null);
  const actualizar = useCallback((p) => setPedido(p), []);
  const actual = pedido ?? data;
  const { puede } = useAuth();

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={actual ? `Pedido ${actual.codigo}` : "Pedido"}
      descripcion={actual ? `${actual.cliente_nombre} · ${etiquetaDeEstado(actual.estado)}` : undefined}
      migas={migas({ etiqueta: actual?.codigo ?? "…" })}
      error={error}
      datos={actual}
      acciones={
        actual && (
          <>
            <BotonPdf url={`${URL}/${actual.id}/pdf`} nombreArchivo={`${actual.codigo}.pdf`} texto="Factura PDF" />
            {puede("pedidos", "editar") && ABIERTO(actual.estado) && (
              <Button onClick={() => navigate(`${RUTA}/${id}/editar`)}>
                <Pencil size={14} /> Editar
              </Button>
            )}
          </>
        )
      }
    >
      {actual && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Datos del pedido">
              <Detalle
                campos={[
                  { etiqueta: "Cliente", valor: actual.cliente_nombre },
                  { etiqueta: "Teléfono", valor: actual.cliente_telefono, cifra: true },
                  { etiqueta: "Dirección", valor: actual.cliente_direccion },
                  { etiqueta: "Registrado", valor: formatearFecha(actual.fecha) },
                  { etiqueta: "Entrega", valor: actual.fecha_entrega ? formatearFechaHora(actual.fecha_entrega) : null },
                  { etiqueta: "Prioridad", valor: <Badge variante={variantePrioridad(actual.prioridad)}>{etiquetaDeEstado(actual.prioridad)}</Badge> },
                  { etiqueta: "Total", valor: formatearMoneda(actual.total), cifra: true },
                  { etiqueta: "Notas", valor: actual.notas },
                ]}
              />
            </Card>
            <Card titulo="Seguimiento">
              <SeguimientoPedido pedido={actual} onActualizado={actualizar} />
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
                { clave: "cantidad", titulo: "Cant.", cifra: true, render: (i) => formatearNumero(i.cantidad) },
                { clave: "precio_unitario", titulo: "Precio unit.", cifra: true, render: (i) => formatearMoneda(i.precio_unitario) },
                { clave: "subtotal", titulo: "Subtotal", cifra: true, render: (i) => formatearMoneda(i.subtotal) },
              ]}
              filas={actual.items}
            />
          </Card>
        </div>
      )}
    </PantallaDetalle>
  );
}
