import { useEffect, useMemo, useState } from "react";
import { ClipboardCheck, Eye, Plus } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import { AccionesFila, Badge, BotonAccion, Buscador, Button, Card, Detalle, Input, PageHeader, Select, Table, TablaRecurso, Textarea } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFechaHora, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { convertir, legible, unidadesDe } from "@/lib/unidades";
import { esquemas } from "@/lib/validaciones";
import { TIPOS_MOVIMIENTO, enlaceDeDocumento } from "@/modules/inventario/movimientos";

/**
 * MOVIMIENTOS DE INVENTARIO (fase 3, 2026-10-12): el historial general de la
 * bodega (quién, cuándo, cuánto y por qué), las mermas con motivo y el
 * ajuste por conteo físico. La existencia nunca se escribe a mano: una merma
 * es un movimiento de salida y un conteo deja un "ajuste" por la diferencia.
 */
const RUTA_CONTEOS = "/inventario/conteos";

const MOTIVOS_MERMA = [
  { valor: "vencido", etiqueta: "Vencido" },
  { valor: "danado", etiqueta: "Dañado" },
  { valor: "derramado", etiqueta: "Se cayó o se derramó" },
  { valor: "preparacion", etiqueta: "Error de preparación" },
  { valor: "otro", etiqueta: "Otro (cuenta qué pasó)" },
];

const cantidadConSigno = (m) => `${Number(m.cantidad) > 0 ? "+" : "−"}${legible(Math.abs(Number(m.cantidad)), m.unidad)}`;

function BadgeTipo({ tipo }) {
  const t = TIPOS_MOVIMIENTO[tipo] ?? { etiqueta: tipo, variante: "neutro" };
  return <Badge variante={t.variante}>{t.etiqueta}</Badge>;
}

function Documento({ m }) {
  if (!m.documento_codigo) return m.motivo ?? "—";
  const ruta = enlaceDeDocumento(m);
  return ruta ? (
    <Link to={ruta} className="enlace cifra">
      {m.documento_codigo}
    </Link>
  ) : (
    <span className="cifra">{m.documento_codigo}</span>
  );
}

// =====================================================================
// Historial general
// =====================================================================
export function MovimientosLista() {
  const { puede } = useAuth();
  const [tipo, setTipo] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const filtros = { ...(tipo ? { tipo } : {}), ...(desde ? { desde } : {}), ...(hasta ? { hasta } : {}) };
  const listado = useListadoPaginado("/inventario/movimientos", { filtros, porPagina: 20 });

  const columnas = [
    { clave: "created_at", titulo: "Fecha", ajustar: true, render: (m) => formatearFechaHora(m.created_at) },
    {
      clave: "insumo_nombre",
      titulo: "Insumo",
      render: (m) => (
        <Link to={`/inventario/insumos/${m.insumo_id}`} className="enlace">
          {m.insumo_nombre}
        </Link>
      ),
    },
    { clave: "tipo", titulo: "Movimiento", ajustar: true, render: (m) => <BadgeTipo tipo={m.tipo} /> },
    { clave: "cantidad", titulo: "Cantidad", cifra: true, render: cantidadConSigno },
    { clave: "existencia_resultante", titulo: "Queda", cifra: true, render: (m) => legible(m.existencia_resultante, m.unidad) },
    ...(puede("costos", "ver") ? [{ clave: "valor", titulo: "Valor a costo", cifra: true, render: (m) => formatearMoneda(m.valor) }] : []),
    { clave: "documento_codigo", titulo: "Documento o motivo", render: (m) => <Documento m={m} /> },
    { clave: "usuario_nombre", titulo: "Quién", render: (m) => m.usuario_nombre || "—" },
  ];

  return (
    <div>
      <PageHeader
        titulo="Movimientos"
        descripcion="Cada entrada y salida de la bodega: compras, ventas por receta, mermas, conteos y anulaciones."
        migas={MIGAS.movimientos}
      />
      <TablaRecurso
        exportar="movimientos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar insumo, documento, motivo o persona…"
        vacio="Todavía no hay movimientos: la existencia entra con compras, la carga inicial o la existencia inicial de cada insumo."
        filtros={
          <>
            <Select value={tipo} onChange={(e) => setTipo(e.target.value)} className="w-48" aria-label="Filtrar por tipo de movimiento">
              <option value="">Todos los movimientos</option>
              {Object.entries(TIPOS_MOVIMIENTO).map(([valor, t]) => (
                <option key={valor} value={valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} cifra aria-label="Desde el día" className="w-40" />
            <Input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} cifra aria-label="Hasta el día" className="w-40" />
          </>
        }
      />
    </div>
  );
}

// =====================================================================
// Merma de un insumo
// =====================================================================
const esquemaMerma = z
  .object({
    cantidad: esquemas.cantidad(),
    unidad: z.string().min(1, "Elige la unidad"),
    motivo: z.string().min(1, "Elige el motivo de la merma"),
    detalle: z.string().max(200, "Máximo 200 caracteres"),
  })
  .superRefine((d, ctx) => {
    if (d.motivo === "otro" && !d.detalle.trim()) {
      ctx.addIssue({ code: "custom", path: ["detalle"], message: "Cuenta qué pasó: con el motivo «Otro» el detalle es obligatorio" });
    }
  });

export function MermaNueva() {
  const { id } = useParams();
  const volver = `/inventario/insumos/${id}`;
  const { data: insumo, error } = useApiResource(`/inventario/insumos/${id}`);
  const f = useFormulario(esquemaMerma, { cantidad: "", unidad: "", motivo: "", detalle: "" });
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver,
    mensaje: insumo ? `Merma de ${insumo.nombre} registrada` : "Merma registrada",
    accion: "registrar la merma",
  });
  useEffect(() => {
    if (insumo) f.reiniciar({ cantidad: "", unidad: insumo.unidad, motivo: "", detalle: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insumo]);

  const enUnidadDelInsumo = insumo && f.form.cantidad ? convertir(f.form.cantidad, f.form.unidad, insumo.unidad) : null;
  const quedaria = enUnidadDelInsumo == null ? null : Number(insumo.existencia) - enUnidadDelInsumo;

  return (
    <PantallaDetalle
      estrecha
      volver={volver}
      titulo={insumo ? `Merma de ${insumo.nombre}` : "Registrar merma"}
      descripcion="Lo que sale de la bodega sin venderse: vencido, dañado, derramado o mal preparado."
      migas={migasDe(MIGAS.insumos, { etiqueta: insumo?.nombre ?? "…", a: volver }, { etiqueta: "Merma" })}
      error={error}
      datos={insumo}
    >
      {insumo && (
        <FormularioPantalla
          id="form-merma"
          onSubmit={(e) =>
            guardar(e, (d) =>
              api.post(`/inventario/insumos/${id}/merma`, { cantidad: d.cantidad, unidad: d.unidad, motivo: d.motivo, detalle: d.detalle.trim() || null })
            )
          }
          volver={volver}
          refRaiz={f.raiz}
          hayErrores={f.hayErrores}
          guardando={guardando}
          textoGuardar="Registrar merma"
          errorGeneral={errorGeneral}
        >
          <Seccion titulo="Cuánto se perdió" descripcion={`Hay ${legible(insumo.existencia, insumo.unidad)} en el sistema.`}>
            <div className="fila-campos">
              <Input etiqueta="Cantidad" {...f.props("cantidad")} permitir="cantidad" cifra autoComplete="off" />
              <Select etiqueta="Unidad" {...f.props("unidad")}>
                {unidadesDe(insumo.unidad).map((u) => (
                  <option key={u.valor} value={u.valor}>
                    {u.etiqueta}
                  </option>
                ))}
              </Select>
            </div>
            {quedaria != null && (
              <p className={`text-[13px] cifra ${quedaria < 0 ? "text-[var(--texto)] font-semibold" : "text-[var(--texto-secundario)]"}`} aria-live="polite">
                {quedaria < 0
                  ? `▼ Es más de lo que hay (${legible(insumo.existencia, insumo.unidad)}). Si en la bodega hay menos de lo que dice el sistema, haz un conteo físico.`
                  : `Quedarían ${legible(quedaria, insumo.unidad)}.`}
              </p>
            )}
          </Seccion>
          <Seccion titulo="Por qué">
            <Select etiqueta="Motivo" {...f.props("motivo")}>
              <option value="">Elige el motivo…</option>
              {MOTIVOS_MERMA.map((m) => (
                <option key={m.valor} value={m.valor}>
                  {m.etiqueta}
                </option>
              ))}
            </Select>
            <Textarea
              etiqueta="Detalle"
              {...f.props("detalle", { requerido: f.form.motivo === "otro" })}
              maxLength={200}
              ayuda={f.form.motivo === "otro" ? "Obligatorio con el motivo «Otro»" : "Opcional: qué pasó, en qué turno…"}
            />
          </Seccion>
        </FormularioPantalla>
      )}
    </PantallaDetalle>
  );
}

// =====================================================================
// Conteos físicos
// =====================================================================
export function ConteosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const listado = useListadoPaginado("/inventario/conteos", { porPagina: 20 });
  const columnas = [
    {
      clave: "codigo",
      titulo: "Conteo",
      ajustar: true,
      render: (c) => (
        <Link to={`${RUTA_CONTEOS}/${c.id}`} className="enlace cifra">
          {c.codigo}
        </Link>
      ),
    },
    { clave: "created_at", titulo: "Fecha", ajustar: true, render: (c) => formatearFechaHora(c.created_at) },
    { clave: "lineas", titulo: "Insumos contados", cifra: true, render: (c) => formatearNumero(c.lineas) },
    { clave: "con_diferencia", titulo: "Con diferencia", cifra: true, render: (c) => formatearNumero(c.con_diferencia) },
    ...(puede("costos", "ver") ? [{ clave: "valor_diferencia", titulo: "Valor de la diferencia", cifra: true, render: (c) => conSigno(c.valor_diferencia) }] : []),
    { clave: "motivo", titulo: "Motivo", render: (c) => c.motivo ?? "—" },
    { clave: "usuario_nombre", titulo: "Quién", render: (c) => c.usuario_nombre || "—" },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (c) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver ${c.codigo}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA_CONTEOS}/${c.id}`)} />
        </AccionesFila>
      ),
    },
  ];
  return (
    <div>
      <PageHeader
        titulo="Conteos físicos"
        descripcion="Se cuenta lo que de verdad hay en la bodega y la diferencia con el sistema queda como ajuste, con su valor."
        migas={MIGAS.conteos}
        acciones={
          puede("movimientos", "crear") && (
            <Button onClick={() => navigate(`${RUTA_CONTEOS}/nuevo`)}>
              <Plus size={14} aria-hidden="true" /> Nuevo conteo
            </Button>
          )
        }
      />
      <TablaRecurso
        exportar="conteos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por motivo o persona…"
        vacio="Todavía no hay conteos. Conviene hacer uno al cierre de cada semana o de cada mes."
      />
    </div>
  );
}

function conSigno(valor) {
  const n = Number(valor);
  if (!Number.isFinite(n)) return "—";
  if (n === 0) return formatearMoneda(0);
  return `${n > 0 ? "▲ +" : "▼ −"}${formatearMoneda(Math.abs(n))}`;
}

const CANTIDAD_RE = /^\d{1,7}(\.\d{1,3})?$/;

/** Todas las páginas de insumos activos (el máximo por página es 100). */
async function cargarInsumosActivos() {
  const pedir = (pagina) => api.get("/inventario/insumos", { params: { activo: true, por_pagina: 100, pagina } }).then((r) => r.data);
  const primera = await pedir(1);
  const resto = await Promise.all(Array.from({ length: primera.paginas - 1 }, (_, i) => pedir(i + 2)));
  return [primera, ...resto].flatMap((p) => p.items);
}

export function ConteoNuevo() {
  const navigate = useNavigate();
  const [insumos, setInsumos] = useState(null);
  const [errorCarga, setErrorCarga] = useState(null);
  const [contados, setContados] = useState({});
  const [tocados, setTocados] = useState({});
  const [motivo, setMotivo] = useState("");
  const [grupo, setGrupo] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [sinLineas, setSinLineas] = useState(false);
  // useGuardarPantalla necesita un "formulario": aquí la validación es por
  // fila, así que se le entrega uno mínimo que solo envía.
  const f = useMemo(() => ({ enviar: async (fn) => (await fn(), true) }), []);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA_CONTEOS, mensaje: "Conteo registrado: la existencia quedó igual a lo contado", accion: "registrar el conteo" });

  useEffect(() => {
    let vivo = true;
    cargarInsumosActivos()
      .then((lista) => vivo && setInsumos(lista))
      .catch((err) => vivo && setErrorCarga(err?.response?.data?.detail ?? "No se pudieron cargar los insumos."));
    return () => {
      vivo = false;
    };
  }, []);

  const errores = Object.fromEntries(
    Object.entries(contados)
      .filter(([, v]) => v.trim() !== "" && (!CANTIDAD_RE.test(v.trim()) || Number(v) > 1_000_000))
      .map(([idInsumo]) => [idInsumo, "Cantidad de 0 o más con máximo 3 decimales (hasta 1.000.000)"])
  );
  const lineas = Object.entries(contados).filter(([, v]) => v.trim() !== "");
  const hayErrores = Object.keys(errores).some((i) => enviado || tocados[i]);
  const grupos = [...new Set((insumos ?? []).map((i) => i.grupo).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
  const texto = busqueda.trim().toLowerCase();
  const visibles = (insumos ?? []).filter((i) => (!grupo || i.grupo === grupo) && (!texto || i.nombre.toLowerCase().includes(texto)));

  const enviar = (e) => {
    e.preventDefault();
    setEnviado(true);
    setSinLineas(!lineas.length);
    if (Object.keys(errores).length || !lineas.length) return;
    guardar(null, () =>
      api.post("/inventario/conteos", { motivo: motivo.trim() || null, lineas: lineas.map(([insumo_id, contado]) => ({ insumo_id, contado: contado.trim() })) })
    );
  };

  const columnas = [
    { clave: "nombre", titulo: "Insumo", render: (i) => i.nombre },
    { clave: "existencia", titulo: "Sistema", cifra: true, render: (i) => legible(i.existencia, i.unidad) },
    {
      clave: "contado",
      titulo: "Contado",
      render: (i) => (
        <Input
          value={contados[i.id] ?? ""}
          onChange={(e) => setContados((prev) => ({ ...prev, [i.id]: e.target.value }))}
          onBlur={() => setTocados((prev) => ({ ...prev, [i.id]: true }))}
          error={enviado || tocados[i.id] ? errores[i.id] : undefined}
          permitir="cantidad"
          cifra
          autoComplete="off"
          aria-label={`Contado de ${i.nombre} en ${i.unidad}`}
          placeholder={i.unidad}
          className="w-28"
        />
      ),
    },
    {
      clave: "diferencia",
      titulo: "Diferencia",
      cifra: true,
      render: (i) => {
        const v = contados[i.id]?.trim();
        if (!v || errores[i.id]) return "—";
        const d = Number(v) - Number(i.existencia);
        if (d === 0) return "Cuadra";
        return `${d > 0 ? "▲ +" : "▼ −"}${legible(Math.abs(d), i.unidad)}`;
      },
    },
  ];

  return (
    <div className="pantalla-estrecha">
      <PageHeader
        volver={RUTA_CONTEOS}
        titulo="Nuevo conteo físico"
        descripcion="Escribe lo que hay en la bodega, en la unidad de cada insumo. Los que dejes vacíos no se tocan."
        migas={migasDe(MIGAS.conteos, { etiqueta: "Nuevo conteo" })}
      />
      <form className="card formulario-pantalla" onSubmit={enviar} noValidate>
        <Seccion titulo="Conteo">
          <Input etiqueta="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={200} ayuda="Opcional: Cierre de mes, Revisión semanal…" />
        </Seccion>
        <Seccion titulo="Insumos" descripcion={insumos ? `${lineas.length} de ${insumos.length} contados.` : undefined}>
          <div className="flex flex-wrap items-center gap-3">
            <Buscador valor={busqueda} onCambiar={setBusqueda} placeholder="Buscar insumo…" className="flex-1 min-w-[180px]" />
            <Select value={grupo} onChange={(e) => setGrupo(e.target.value)} aria-label="Filtrar por grupo" className="w-44">
              <option value="">Todos los grupos</option>
              {grupos.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
          </div>
          {errorCarga && (
            <p className="estado estado--error" role="alert">
              {errorCarga}
            </p>
          )}
          {!insumos && !errorCarga && <p className="text-[13px] text-[var(--texto-terciario)]">Cargando insumos…</p>}
          {insumos && <Table columnas={columnas} filas={visibles} vacio={insumos.length ? "Ningún insumo coincide con el filtro." : "No hay insumos activos para contar."} />}
        </Seccion>
        {(errorGeneral || (sinLineas && !lineas.length)) && (
          <p className="estado estado--error" role="alert">
            {errorGeneral ?? "Escribe lo que contaste en al menos un insumo."}
          </p>
        )}
        <div className="formulario-pantalla__pie">
          {hayErrores && <span className="formulario-pantalla__aviso">Hay cantidades con errores</span>}
          <Button variante="terciario" onClick={() => navigate(RUTA_CONTEOS)} disabled={guardando}>
            Cancelar
          </Button>
          <Button type="submit" cargando={guardando} disabled={hayErrores}>
            <ClipboardCheck size={14} aria-hidden="true" /> Registrar conteo
          </Button>
        </div>
      </form>
    </div>
  );
}

export function ConteoDetalle() {
  const { id } = useParams();
  const { puede } = useAuth();
  const verCostos = puede("costos", "ver");
  const { data, error } = useApiResource(`${RUTA_CONTEOS}/${id}`);
  return (
    <PantallaDetalle
      volver={RUTA_CONTEOS}
      titulo={data ? `Conteo ${data.codigo}` : "Conteo"}
      descripcion={data ? formatearFechaHora(data.created_at) : undefined}
      migas={migasDe(MIGAS.conteos, { etiqueta: data?.codigo ?? "…" })}
      error={error}
      datos={data}
    >
      {data && (
        <div className="space-y-4">
          <Card titulo="Resumen">
            <Detalle
              campos={[
                { etiqueta: "Conteo", valor: data.codigo, cifra: true },
                { etiqueta: "Fecha", valor: formatearFechaHora(data.created_at) },
                { etiqueta: "Motivo", valor: data.motivo },
                { etiqueta: "Quién", valor: data.usuario_nombre },
                { etiqueta: "Insumos contados", valor: formatearNumero(data.lineas), cifra: true },
                { etiqueta: "Con diferencia", valor: formatearNumero(data.con_diferencia), cifra: true },
                ...(verCostos ? [{ etiqueta: "Valor de la diferencia", valor: conSigno(data.valor_diferencia), cifra: true }] : []),
              ]}
            />
          </Card>
          <Card titulo="Insumos" descripcion="Cada diferencia quedó como un movimiento «Ajuste» en el historial del insumo.">
            <Table
              idFila={(i) => i.insumo_id}
              columnas={[
                {
                  clave: "insumo_nombre",
                  titulo: "Insumo",
                  render: (i) => (
                    <Link to={`/inventario/insumos/${i.insumo_id}`} className="enlace">
                      {i.insumo_nombre}
                    </Link>
                  ),
                },
                { clave: "sistema", titulo: "Sistema", cifra: true, render: (i) => legible(i.sistema, i.unidad) },
                { clave: "contado", titulo: "Contado", cifra: true, render: (i) => legible(i.contado, i.unidad) },
                {
                  clave: "diferencia",
                  titulo: "Diferencia",
                  cifra: true,
                  render: (i) => (Number(i.diferencia) === 0 ? "Cuadra" : `${Number(i.diferencia) > 0 ? "▲ +" : "▼ −"}${legible(Math.abs(Number(i.diferencia)), i.unidad)}`),
                },
                ...(verCostos ? [{ clave: "valor", titulo: "Valor", cifra: true, render: (i) => conSigno(i.valor) }] : []),
              ]}
              filas={data.items}
            />
          </Card>
        </div>
      )}
    </PantallaDetalle>
  );
}
