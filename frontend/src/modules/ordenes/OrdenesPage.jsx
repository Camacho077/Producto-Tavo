import { useEffect, useMemo, useState } from "react";
import { Ban, CheckCheck, Eye, Pencil, Plus, Printer, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import DialogoMotivo from "@/components/DialogoMotivo";
import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import {
  AccionesFila,
  Badge,
  BotonAccion,
  Button,
  Card,
  Detalle,
  Input,
  PageHeader,
  Pildoras,
  Select,
  Table,
  TablaRecurso,
  Textarea,
} from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { useAuth } from "@/context/AuthContext";
import { ORIGENES, TIPOS_ORDEN, etiquetaCortaTipoOrden, etiquetaOrigen, etiquetaTipoOrden } from "@/config/restaurante";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearHora, formatearMoneda, formatearNumero } from "@/lib/formato";
import { htmlComanda, impresoraPara, imprimir } from "@/lib/impresion";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";
import { ESTADOS, ETIQUETA_MESA, destinoDeOrden, estadoDeOrden, nombreJornada } from "@/modules/ordenes/estados";

import "./ordenes.css";

/**
 * ÓRDENES (fase 4, 2026-10-12): tablero de la jornada (Activas, Entregadas,
 * Anuladas), detalle con sus comandas y su línea de tiempo, edición de los
 * datos, y el estado de las mesas. Agregar platos y tomar el pedido viven en
 * TomarPedidoPage.
 */
const RUTA = "/ordenes";
const REFRESCO_MS = 20_000;

export function BadgeEstado({ orden }) {
  const e = ESTADOS[estadoDeOrden(orden)] ?? { etiqueta: orden.estado, variante: "neutro" };
  return <Badge variante={e.variante}>{e.etiqueta}</Badge>;
}

/** Repite `recargar` cada tanto mientras la pantalla está visible. */
function useRefresco(recargar, ms = REFRESCO_MS) {
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === "visible") recargar();
    }, ms);
    return () => clearInterval(id);
  }, [recargar, ms]);
}

function imprimirComanda(orden, numero, tenant, aviso) {
  const impresora = impresoraPara(tenant?.configuracion, "comanda") ?? { conexion: "navegador", ancho_mm: 80 };
  imprimir(htmlComanda(orden, numero, { tipo: etiquetaTipoOrden(orden.tipo), destino: destinoDeOrden(orden), empresa: tenant?.nombre_empresa }), impresora).catch((err) =>
    aviso.error(err.message)
  );
}

// =====================================================================
// Tablero
// =====================================================================
const VISTAS = [
  { clave: "activas", etiqueta: "Activas" },
  { clave: "entregadas", etiqueta: "Entregadas" },
  { clave: "anuladas", etiqueta: "Anuladas" },
];

export function OrdenesLista() {
  const navigate = useNavigate();
  const aviso = useAviso();
  const { puede } = useAuth();
  const [vista, setVista] = useState("activas");
  const [tipo, setTipo] = useState("");
  const [mias, setMias] = useState(false);
  const filtros = { vista, ...(tipo ? { tipo } : {}), ...(mias ? { mias: true } : {}) };
  const listado = useListadoPaginado(RUTA, { filtros, porPagina: 30 });
  const { data: jornada, recargar: recargarJornada } = useApiResource(`${RUTA}/jornada`);
  const { recargar } = listado;
  useRefresco(recargar);
  useRefresco(recargarJornada);

  const entregar = async (o) => {
    try {
      await api.post(`${RUTA}/${o.id}/entregar`);
      aviso.exito(`Orden #${o.numero} entregada`);
      recargar();
      recargarJornada();
    } catch (err) {
      aviso.error(err?.response?.data?.detail ?? "No se pudo entregar la orden.");
    }
  };

  const columnas = [
    {
      clave: "numero",
      titulo: "Orden",
      ajustar: true,
      render: (o) => (
        <Link to={`${RUTA}/${o.id}`} className="enlace cifra ordenes-numero">
          #{o.numero}
        </Link>
      ),
    },
    { clave: "tipo", titulo: "Tipo", ajustar: true, render: (o) => etiquetaCortaTipoOrden(o.tipo) },
    { clave: "destino", titulo: "Mesa o cliente", render: (o) => destinoDeOrden(o) },
    { clave: "estado", titulo: "Estado", ajustar: true, render: (o) => <BadgeEstado orden={o} /> },
    { clave: "resumen", titulo: "Platos", render: (o) => o.resumen || "—" },
    { clave: "total", titulo: "Total", cifra: true, render: (o) => formatearMoneda(o.total) },
    { clave: "created_at", titulo: "Hora", cifra: true, render: (o) => formatearHora(o.created_at) },
    { clave: "mesero_nombre", titulo: "Tomó", render: (o) => o.mesero_nombre ?? "—" },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (o) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver la orden #${o.numero}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA}/${o.id}`)} />
          {o.estado === "abierta" && puede("ordenes", "editar") && (
            <BotonAccion icono={Plus} etiqueta={`Agregar platos a la orden #${o.numero}`} titulo="Agregar platos" onClick={() => navigate(`${RUTA}/${o.id}/agregar`)} />
          )}
          {o.estado === "abierta" && o.estado_cocina === "lista" && puede("ordenes", "cambiar_estado") && (
            <BotonAccion icono={CheckCheck} etiqueta={`Entregar la orden #${o.numero}`} titulo="Entregar" onClick={() => entregar(o)} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Órdenes"
        descripcion={jornada ? `${nombreJornada(jornada.jornada)} · ${formatearNumero(jornada.en_curso)} en curso · ${formatearNumero(jornada.ordenes)} en el día` : "Jornada actual"}
        migas={MIGAS.ordenes}
        acciones={
          puede("ordenes", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nueva`)}>
              <Plus size={14} aria-hidden="true" /> Tomar pedido
            </Button>
          )
        }
      />
      <div className="mb-3">
        <Pildoras opciones={VISTAS.map((v) => ({ clave: v.clave, etiqueta: v.etiqueta }))} valor={vista} onCambiar={setVista} etiqueta="Vista del tablero" />
      </div>
      <TablaRecurso
        exportar="ordenes"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por número, cliente o mesero…"
        vacio={vista === "activas" ? "No hay órdenes en curso." : vista === "entregadas" ? "Todavía no se ha entregado ninguna orden hoy." : "Ninguna orden anulada hoy."}
        filtros={
          <>
            <Select value={tipo} onChange={(e) => setTipo(e.target.value)} className="w-40" aria-label="Filtrar por tipo">
              <option value="">Todos los tipos</option>
              {TIPOS_ORDEN.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Select value={mias ? "mias" : ""} onChange={(e) => setMias(e.target.value === "mias")} className="w-40" aria-label="Filtrar por quién la tomó">
              <option value="">De todos</option>
              <option value="mias">Solo las mías</option>
            </Select>
          </>
        }
      />
    </div>
  );
}

// =====================================================================
// Detalle
// =====================================================================
const NOMBRE_EVENTO = {
  creada: "Orden creada",
  agregado: "Platos agregados",
  item_anulado: "Plato anulado",
  editada: "Datos editados",
  anulada: "Orden anulada",
  entregada: "Entregada",
  tomada: "Cocina la tomó",
  lista: "Lista en cocina",
  cobrada: "Cobrada",
};
const ESTADO_COMANDA = { ...ESTADOS, anulada: { etiqueta: "Anulada", variante: "negativo" } };

export function OrdenDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const aviso = useAviso();
  const { puede, tenant } = useAuth();
  const { data: o, error, recargar } = useApiResource(`${RUTA}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  const [entregando, setEntregando] = useState(false);
  useRefresco(recargar);

  const abierta = o?.estado === "abierta";
  const hayLista = o?.comandas.some((c) => c.estado === "lista");
  const activos = o ? o.items.filter((i) => !i.anulado) : [];

  const entregar = async () => {
    setEntregando(true);
    try {
      await api.post(`${RUTA}/${id}/entregar`);
      aviso.exito(`Orden #${o.numero} entregada`);
      recargar();
    } catch (err) {
      aviso.error(err?.response?.data?.detail ?? "No se pudo entregar la orden.");
    } finally {
      setEntregando(false);
    }
  };

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={o ? `Orden #${o.numero}` : "Orden"}
      descripcion={o ? `${destinoDeOrden(o)} · ${etiquetaTipoOrden(o.tipo)} · ${formatearHora(o.created_at)}` : undefined}
      migas={migasDe(MIGAS.ordenes, { etiqueta: o ? `#${o.numero}` : "…" })}
      error={error}
      datos={o}
      acciones={
        o && (
          <>
            {abierta && puede("ordenes", "anular") && (
              <Button variante="terciario" onClick={() => setDialogo({ tipo: "orden" })}>
                <Ban size={14} aria-hidden="true" /> Anular
              </Button>
            )}
            {abierta && puede("ordenes", "editar") && (
              <Button variante="terciario" onClick={() => navigate(`${RUTA}/${id}/editar`)}>
                <Pencil size={14} aria-hidden="true" /> Editar datos
              </Button>
            )}
            {abierta && puede("ordenes", "editar") && (
              <Button variante="secundario" onClick={() => navigate(`${RUTA}/${id}/agregar`)}>
                <Plus size={14} aria-hidden="true" /> Agregar platos
              </Button>
            )}
            {abierta && hayLista && puede("ordenes", "cambiar_estado") && (
              <Button onClick={entregar} cargando={entregando}>
                <CheckCheck size={14} aria-hidden="true" /> Entregar
              </Button>
            )}
          </>
        )
      }
    >
      {o && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Orden">
              <Detalle
                campos={[
                  { etiqueta: "Estado", valor: <BadgeEstado orden={o} /> },
                  { etiqueta: "Tipo", valor: etiquetaTipoOrden(o.tipo) },
                  { etiqueta: "Origen", valor: etiquetaOrigen(o.origen) },
                  ...(o.mesa_nombre ? [{ etiqueta: "Mesa", valor: o.mesa_nombre }] : []),
                  { etiqueta: "Cliente", valor: o.cliente_nombre },
                  ...(o.tipo !== "local" ? [{ etiqueta: "Teléfono", valor: o.cliente_telefono }] : []),
                  ...(o.tipo === "domicilio" ? [{ etiqueta: "Dirección", valor: o.cliente_direccion }] : []),
                  { etiqueta: "Nota", valor: o.nota },
                  { etiqueta: "Tomó", valor: o.mesero_nombre },
                  ...(o.anulada_motivo ? [{ etiqueta: "Motivo de anulación", valor: o.anulada_motivo }] : []),
                  { etiqueta: "Total", valor: formatearMoneda(o.total), cifra: true },
                ]}
              />
            </Card>
            <Card titulo="Comandas" descripcion="Cada envío a cocina. Agregar platos saca una comanda con solo lo nuevo.">
              <ul className="ordenes-comandas">
                {o.comandas.map((c) => {
                  const e = ESTADO_COMANDA[c.estado] ?? { etiqueta: c.estado, variante: "neutro" };
                  return (
                    <li key={c.id} className="ordenes-comanda">
                      <div>
                        <p className="ordenes-comanda__titulo">
                          Comanda {c.numero} <Badge variante={e.variante}>{e.etiqueta}</Badge>
                        </p>
                        <p className="ordenes-comanda__tiempos cifra">
                          Entró {formatearHora(c.created_at)}
                          {c.tomada_en && ` · tomada ${formatearHora(c.tomada_en)}${c.tomada_por ? ` (${c.tomada_por})` : ""}`}
                          {c.lista_en && c.va_a_cocina && ` · lista ${formatearHora(c.lista_en)}`}
                          {c.entregada_en && ` · entregada ${formatearHora(c.entregada_en)}`}
                          {!c.va_a_cocina && " · venta directa, no pasa por cocina"}
                        </p>
                      </div>
                      {c.va_a_cocina && c.estado !== "anulada" && (
                        <Button variante="terciario" tamano="sm" onClick={() => imprimirComanda(o, c.numero, tenant, aviso)}>
                          <Printer size={14} aria-hidden="true" /> Imprimir
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            </Card>
          </div>
          <Card titulo="Platos">
            <Table
              columnas={[
                {
                  clave: "nombre",
                  titulo: "Plato",
                  render: (i) => (
                    <span className={i.anulado ? "ordenes-anulado" : ""}>
                      <strong>
                        {i.cantidad}× {i.nombre}
                      </strong>
                      {i.modificadores.map((m) => (
                        <span key={m.id} className="ordenes-mod">
                          {m.tipo === "sin" ? "– " : "+ "}
                          {m.nombre}
                        </span>
                      ))}
                      {i.nota && <span className="ordenes-nota">» {i.nota}</span>}
                      {i.anulado && <span className="ordenes-nota">Anulado: {i.anulado_motivo}</span>}
                    </span>
                  ),
                },
                { clave: "comanda_numero", titulo: "Comanda", cifra: true, render: (i) => i.comanda_numero },
                { clave: "precio_unitario", titulo: "Precio", cifra: true, render: (i) => formatearMoneda(i.precio_unitario) },
                { clave: "subtotal", titulo: "Subtotal", cifra: true, render: (i) => (i.anulado ? "—" : formatearMoneda(i.subtotal)) },
                {
                  clave: "acciones",
                  titulo: "Acciones",
                  render: (i) =>
                    abierta && !i.anulado && activos.length > 1 && puede("ordenes", "editar") ? (
                      <AccionesFila>
                        <BotonAccion icono={X} etiqueta={`Quitar ${i.nombre} de la orden`} titulo="Quitar plato" onClick={() => setDialogo({ tipo: "item", item: i })} />
                      </AccionesFila>
                    ) : (
                      "—"
                    ),
                },
              ]}
              filas={o.items}
            />
          </Card>
          <Card titulo="Línea de tiempo">
            <ol className="ordenes-tiempo">
              {o.eventos.map((e) => (
                <li key={e.id}>
                  <span className="cifra">{formatearHora(e.created_at)}</span>
                  <span>
                    <strong>{NOMBRE_EVENTO[e.tipo] ?? e.tipo}</strong>
                    {e.nota && ` · ${e.nota}`}
                    {e.usuario_nombre && <span className="ordenes-tiempo__quien"> — {e.usuario_nombre}</span>}
                  </span>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      )}
      <DialogoMotivo
        key={`orden-${dialogo?.tipo === "orden"}`}
        abierto={dialogo?.tipo === "orden"}
        onCerrar={() => setDialogo(null)}
        titulo={o ? `Anular la orden #${o.numero}` : "Anular la orden"}
        mensaje="Los insumos de lo que seguía en pie vuelven a la bodega y sus comandas salen de la cocina. No se puede deshacer."
        textoConfirmar="Anular orden"
        mensajeExito={o ? `Orden #${o.numero} anulada` : "Orden anulada"}
        accion="anular la orden"
        ayuda="Queda en el historial y le llega a cocina"
        onConfirmar={async (motivo) => {
          await api.post(`${RUTA}/${id}/anular`, { motivo });
          recargar();
        }}
      />
      <DialogoMotivo
        key={`item-${dialogo?.item?.id ?? ""}`}
        abierto={dialogo?.tipo === "item"}
        onCerrar={() => setDialogo(null)}
        titulo={dialogo?.item ? `Quitar ${dialogo.item.cantidad}× ${dialogo.item.nombre}` : "Quitar plato"}
        mensaje="Sus insumos vuelven a la bodega y cocina ve el plato tachado con el motivo."
        textoConfirmar="Quitar plato"
        mensajeExito={dialogo?.item ? `${dialogo.item.nombre} quitado de la orden` : "Plato quitado"}
        accion="quitar el plato"
        ayuda="Queda en el historial y le llega a cocina"
        onConfirmar={async (motivo) => {
          await api.post(`${RUTA}/${id}/items/${dialogo.item.id}/anular`, { motivo });
          recargar();
        }}
      />
    </PantallaDetalle>
  );
}

// =====================================================================
// Editar datos
// =====================================================================
const esquemaDatos = z
  .object({
    tipo: z.string(),
    origen: z.string(),
    mesa_id: z.string(),
    cliente_nombre: z.string().refine((s) => s.trim() === "" || /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]{2,80}$/.test(s.trim()), "Solo letras, espacios, tildes y apóstrofes (entre 2 y 80 caracteres)"),
    cliente_telefono: z.string(),
    cliente_direccion: z.string().max(150),
    nota: z.string().max(200),
  })
  .superRefine((d, ctx) => {
    if (d.tipo === "local" && !d.mesa_id) ctx.addIssue({ code: "custom", path: ["mesa_id"], message: "Una orden en el local va con mesa" });
    if (d.tipo === "domicilio" && !d.cliente_direccion.trim()) ctx.addIssue({ code: "custom", path: ["cliente_direccion"], message: "Un domicilio necesita la dirección" });
    const tel = d.cliente_telefono.replace(/\s/g, "");
    if (d.tipo === "domicilio" && !tel) ctx.addIssue({ code: "custom", path: ["cliente_telefono"], message: "Un domicilio necesita el teléfono" });
    if (tel && !esquemas.telefono().safeParse(tel).success) ctx.addIssue({ code: "custom", path: ["cliente_telefono"], message: "Celular de 10 dígitos (3…) o fijo con indicativo (60…)" });
  });

export function OrdenEditar() {
  const { id } = useParams();
  const { data: o, error } = useApiResource(`${RUTA}/${id}`);
  const { data: mesas } = useApiResource(`${RUTA}/mesas`);
  const inicial = useMemo(() => ({ tipo: "local", origen: "local", mesa_id: "", cliente_nombre: "", cliente_telefono: "", cliente_direccion: "", nota: "" }), []);
  const f = useFormulario(esquemaDatos, inicial);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Datos de la orden actualizados", accion: "guardar la orden" });
  useEffect(() => {
    if (o) {
      f.reiniciar({
        tipo: o.tipo, origen: o.origen, mesa_id: o.mesa_id ?? "", cliente_nombre: o.cliente_nombre ?? "",
        cliente_telefono: o.cliente_telefono ?? "", cliente_direccion: o.cliente_direccion ?? "", nota: o.nota ?? "",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [o]);
  const tipo = f.form.tipo;
  return (
    <PantallaDetalle
      estrecha
      volver={`${RUTA}/${id}`}
      titulo={o ? `Editar la orden #${o.numero}` : "Editar orden"}
      migas={migasDe(MIGAS.ordenes, { etiqueta: o ? `#${o.numero}` : "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={o}
    >
      <FormularioPantalla
        id="form-orden"
        onSubmit={(e) =>
          guardar(e, (d) =>
            api.put(`${RUTA}/${id}`, {
              ...d,
              mesa_id: d.tipo === "local" ? d.mesa_id : null,
              cliente_nombre: d.cliente_nombre.trim() || null,
              cliente_telefono: d.cliente_telefono.replace(/\s/g, "") || null,
              cliente_direccion: d.cliente_direccion.trim() || null,
              nota: d.nota.trim() || null,
            })
          )
        }
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <Seccion titulo="Orden" descripcion="Los platos no se editan aquí: se agregan o se quitan desde el detalle.">
          <div className="fila-campos">
            <Select etiqueta="Tipo" {...f.props("tipo")}>
              {TIPOS_ORDEN.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Select etiqueta="Origen" {...f.props("origen")}>
              {ORIGENES.map((x) => (
                <option key={x.valor} value={x.valor}>
                  {x.etiqueta}
                </option>
              ))}
            </Select>
          </div>
          {tipo === "local" && (
            <Select etiqueta="Mesa" {...f.props("mesa_id")}>
              <option value="">Elige la mesa…</option>
              {(mesas ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nombre} · {ETIQUETA_MESA[m.estado]}
                </option>
              ))}
            </Select>
          )}
        </Seccion>
        <Seccion titulo="Cliente">
          <div className="fila-campos">
            <Input etiqueta="Nombre" {...f.props("cliente_nombre", { requerido: false })} permitir="nombre" maxLength={80} />
            <Input etiqueta="Teléfono" {...f.props("cliente_telefono", { requerido: tipo === "domicilio" })} permitir="telefono" />
          </div>
          {tipo === "domicilio" && <Input etiqueta="Dirección" {...f.props("cliente_direccion")} maxLength={150} />}
          <Textarea etiqueta="Nota" {...f.props("nota", { requerido: false })} maxLength={200} />
        </Seccion>
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

// =====================================================================
// Mesas en servicio
// =====================================================================
export function MesasServicio() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data: mesas, error, recargar } = useApiResource(`${RUTA}/mesas`);
  useRefresco(recargar, 15_000);
  const zonas = mesas ? [...new Set(mesas.map((m) => m.zona_nombre ?? "Sin zona"))] : [];
  const cuenta = (estado) => (mesas ?? []).filter((m) => m.estado === estado).length;
  return (
    <div>
      <PageHeader
        titulo="Mesas"
        descripcion={mesas ? `${cuenta("libre")} libres · ${cuenta("ocupada")} ocupadas · ${cuenta("por_cobrar")} por cobrar` : "Estado de las mesas"}
        migas={MIGAS.mesasServicio}
      />
      {error && <p className="estado estado--error">{error}</p>}
      {!mesas && !error && <p className="text-[13px] text-[var(--texto-terciario)]">Cargando mesas…</p>}
      {mesas && !mesas.length && <p className="estado">No hay mesas habilitadas: créalas en Ajustes → Mesas.</p>}
      <div className="space-y-4">
        {zonas.map((z) => (
          <Card key={z} titulo={z}>
            <div className="mesas-rejilla mesas-rejilla--grande">
              {mesas
                .filter((m) => (m.zona_nombre ?? "Sin zona") === z)
                .map((m) => (
                  <div key={m.id} className={`mesas-tile mesas-tile--${m.estado}`}>
                    <span className="mesas-tile__nombre">{m.nombre}</span>
                    <span className="mesas-tile__estado">{ETIQUETA_MESA[m.estado]}</span>
                    {m.ordenes.map((o) => (
                      <Link key={o.id} to={`${RUTA}/${o.id}`} className="enlace cifra mesas-tile__orden">
                        #{o.numero} · {formatearMoneda(o.total)}
                      </Link>
                    ))}
                    {puede("ordenes", "crear") && (
                      <Button variante={m.estado === "libre" ? "secundario" : "terciario"} tamano="sm" onClick={() => navigate(`${RUTA}/nueva?mesa=${m.id}`)}>
                        <Plus size={14} aria-hidden="true" /> {m.estado === "libre" ? "Tomar pedido" : "Otra orden"}
                      </Button>
                    )}
                  </div>
                ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
