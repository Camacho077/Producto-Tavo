import { useEffect, useMemo, useState } from "react";
import { Eye, Pencil, Plus, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import { AccionesFila, BotonAccion, Button, Card, Checkbox, Detalle, Input, ModalConfirmar, PageHeader, Select, TablaRecurso } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { MEDIOS_PAGO, etiquetaMedioPago } from "@/config/restaurante";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFecha, formatearFechaHora, formatearMoneda } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";

/**
 * GASTOS DEL NEGOCIO (fase 6, 2026-10-12): arriendo, servicios, nómina, gas,
 * aseo… Con ellos el dashboard responde "¿cuánto gané?" (utilidad real). Un
 * gasto en efectivo puede salir de la caja abierta y entonces cuenta en su
 * cuadre; si esa caja ya se cerró, el gasto no se toca.
 */
const RUTA = "/gastos";

const CATEGORIAS_GASTO = [
  { valor: "arriendo", etiqueta: "Arriendo" },
  { valor: "servicios", etiqueta: "Servicios públicos" },
  { valor: "nomina", etiqueta: "Nómina" },
  { valor: "gas", etiqueta: "Gas" },
  { valor: "aseo", etiqueta: "Insumos de aseo" },
  { valor: "mantenimiento", etiqueta: "Mantenimiento" },
  { valor: "impuestos", etiqueta: "Impuestos y trámites" },
  { valor: "otros", etiqueta: "Otros" },
];

function ModalEliminar({ gasto, abierto, onCerrar, onConfirmar }) {
  return (
    <ModalConfirmar
      abierto={abierto}
      onCerrar={onCerrar}
      destructivo
      titulo="Eliminar gasto"
      textoConfirmar="Eliminar"
      mensaje={`Se elimina «${gasto?.descripcion ?? ""}» por ${formatearMoneda(gasto?.valor)}. Si salió de una caja ya cerrada, el sistema no lo permitirá.`}
      accion="eliminar el gasto"
      mensajeExito="Gasto eliminado"
      onConfirmar={onConfirmar}
    />
  );
}

export function GastosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [categoria, setCategoria] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const filtros = { ...(categoria ? { categoria } : {}), ...(desde ? { desde } : {}), ...(hasta ? { hasta } : {}) };
  const listado = useListadoPaginado(RUTA, { filtros, porPagina: 20 });
  const [eliminar, setEliminar] = useState(null);
  const columnas = [
    {
      clave: "fecha",
      titulo: "Fecha",
      ajustar: true,
      render: (g) => (
        <Link to={`${RUTA}/${g.id}`} className="enlace">
          {formatearFecha(`${g.fecha}T12:00:00`)}
        </Link>
      ),
    },
    { clave: "categoria", titulo: "Categoría", render: (g) => g.categoria_nombre },
    { clave: "descripcion", titulo: "Descripción", render: (g) => g.descripcion },
    { clave: "valor", titulo: "Valor", cifra: true, render: (g) => formatearMoneda(g.valor) },
    { clave: "medio_pago", titulo: "Pago", render: (g) => `${etiquetaMedioPago(g.medio_pago)}${g.caja_numero ? ` · caja ${g.caja_numero}` : ""}` },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (g) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver ${g.descripcion}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA}/${g.id}`)} />
          {puede("gastos", "editar") && !g.caja_cerrada && (
            <BotonAccion icono={Pencil} etiqueta={`Editar ${g.descripcion}`} titulo="Editar" onClick={() => navigate(`${RUTA}/${g.id}/editar`)} />
          )}
          {puede("gastos", "eliminar") && !g.caja_cerrada && <BotonAccion icono={Trash2} etiqueta={`Eliminar ${g.descripcion}`} titulo="Eliminar" onClick={() => setEliminar(g)} />}
        </AccionesFila>
      ),
    },
  ];
  return (
    <div>
      <PageHeader
        titulo="Gastos"
        descripcion={listado.cargaInicial ? "Lo que cuesta mantener el negocio abierto." : `Suma de lo filtrado: ${formatearMoneda(listado.datos?.suma ?? 0)}`}
        migas={MIGAS.gastos}
        acciones={
          puede("gastos", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} aria-hidden="true" /> Nuevo gasto
            </Button>
          )
        }
      />
      <TablaRecurso
        exportar="gastos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por descripción o persona…"
        vacio="Todavía no hay gastos: registra el arriendo, los servicios y la nómina para ver tu utilidad real."
        filtros={
          <>
            <Select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="w-44" aria-label="Filtrar por categoría">
              <option value="">Todas las categorías</option>
              {CATEGORIAS_GASTO.map((c) => (
                <option key={c.valor} value={c.valor}>
                  {c.etiqueta}
                </option>
              ))}
            </Select>
            <Input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} cifra aria-label="Desde el día" className="w-40" />
            <Input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} cifra aria-label="Hasta el día" className="w-40" />
          </>
        }
      />
      <ModalEliminar
        gasto={eliminar}
        abierto={Boolean(eliminar)}
        onCerrar={() => setEliminar(null)}
        onConfirmar={async () => {
          await api.delete(`${RUTA}/${eliminar.id}`);
          listado.recargar();
        }}
      />
    </div>
  );
}

const hoyColombia = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota" }).format(new Date());

const esquema = z
  .object({
    fecha: z.string().min(1, "Elige la fecha").refine((f) => f <= hoyColombia(), "La fecha del gasto no puede ser futura"),
    categoria: z.string().min(1, "Elige la categoría"),
    descripcion: z.string().refine((s) => s.trim().length >= 3 && s.trim().length <= 150, "Describe el gasto (entre 3 y 150 caracteres)"),
    valor: esquemas.precio(),
    medio_pago: z.string(),
    de_caja: z.boolean(),
  })
  .superRefine((d, ctx) => {
    if (d.de_caja && d.medio_pago !== "efectivo") ctx.addIssue({ code: "custom", path: ["de_caja"], message: "Solo un gasto en efectivo puede salir de la caja" });
  });

const VACIO = { fecha: "", categoria: "", descripcion: "", valor: "", medio_pago: "efectivo", de_caja: false };

function Campos({ f }) {
  return (
    <>
      <Seccion titulo="Gasto" descripcion="Los campos marcados con * son obligatorios.">
        <div className="fila-campos">
          <Input etiqueta="Fecha" type="date" {...f.props("fecha")} max={hoyColombia()} cifra />
          <Select etiqueta="Categoría" {...f.props("categoria")}>
            <option value="">Elige…</option>
            {CATEGORIAS_GASTO.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.etiqueta}
              </option>
            ))}
          </Select>
        </div>
        <Input etiqueta="Descripción" {...f.props("descripcion")} maxLength={150} ayuda="Arriendo de octubre, recibo de energía, pipeta de gas…" />
      </Seccion>
      <Seccion titulo="Pago">
        <div className="fila-campos">
          <Input etiqueta="Valor" {...f.props("valor")} permitir="decimal" cifra autoComplete="off" />
          <Select etiqueta="Medio de pago" {...f.props("medio_pago")}>
            {MEDIOS_PAGO.map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.etiqueta}
              </option>
            ))}
          </Select>
        </div>
        <Checkbox
          etiqueta="Pagado con efectivo de la caja abierta (se descuenta de su cuadre)"
          checked={f.form.de_caja}
          onChange={(e) => f.setCampo("de_caja", e.target.checked)}
          disabled={f.form.medio_pago !== "efectivo"}
        />
        {f.errorVisible?.("de_caja") && <span className="campo__error">{f.errorVisible("de_caja")}</span>}
      </Seccion>
    </>
  );
}

const cuerpo = (d) => ({ ...d, descripcion: d.descripcion.trim(), de_caja: d.medio_pago === "efectivo" && d.de_caja });

export function GastoNuevo() {
  const inicial = useMemo(() => ({ ...VACIO, fecha: hoyColombia() }), []);
  const f = useFormulario(esquema, inicial);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Gasto registrado", accion: "registrar el gasto" });
  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo gasto" migas={migasDe(MIGAS.gastos, { etiqueta: "Nuevo gasto" })} />
      <FormularioPantalla id="form-gasto" onSubmit={(e) => guardar(e, (d) => api.post(RUTA, cuerpo(d)))} volver={RUTA} refRaiz={f.raiz} hayErrores={f.hayErrores} guardando={guardando} errorGeneral={errorGeneral}>
        <Campos f={f} />
      </FormularioPantalla>
    </div>
  );
}

export function GastoEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${RUTA}/${id}`);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el gasto" });
  useEffect(() => {
    if (data) f.reiniciar({ fecha: data.fecha, categoria: data.categoria, descripcion: data.descripcion, valor: String(Number(data.valor)), medio_pago: data.medio_pago, de_caja: Boolean(data.caja_id) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <PantallaDetalle estrecha volver={`${RUTA}/${id}`} titulo="Editar gasto" migas={migasDe(MIGAS.gastos, { etiqueta: data?.descripcion ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })} error={error} datos={data}>
      <FormularioPantalla id="form-gasto" onSubmit={(e) => guardar(e, (d) => api.put(`${RUTA}/${id}`, cuerpo(d)))} volver={`${RUTA}/${id}`} refRaiz={f.raiz} hayErrores={f.hayErrores} guardando={guardando} textoGuardar="Guardar cambios" errorGeneral={errorGeneral}>
        <Campos f={f} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function GastoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data: g, error } = useApiResource(`${RUTA}/${id}`);
  const [eliminar, setEliminar] = useState(false);
  return (
    <PantallaDetalle estrecha
      volver={RUTA}
      titulo={g?.descripcion ?? "Gasto"}
      descripcion={g ? `${g.categoria_nombre} · ${formatearMoneda(g.valor)}` : undefined}
      migas={migasDe(MIGAS.gastos, { etiqueta: g?.descripcion ?? "…" })}
      error={error}
      datos={g}
      acciones={
        g &&
        !g.caja_cerrada && (
          <>
            {puede("gastos", "eliminar") && (
              <Button variante="terciario" onClick={() => setEliminar(true)}>
                <Trash2 size={14} aria-hidden="true" /> Eliminar
              </Button>
            )}
            {puede("gastos", "editar") && (
              <Button onClick={() => navigate(`${RUTA}/${id}/editar`)}>
                <Pencil size={14} aria-hidden="true" /> Editar
              </Button>
            )}
          </>
        )
      }
    >
      {g && (
        <Card titulo="Datos del gasto">
          <Detalle
            campos={[
              { etiqueta: "Fecha", valor: formatearFecha(`${g.fecha}T12:00:00`) },
              { etiqueta: "Categoría", valor: g.categoria_nombre },
              { etiqueta: "Descripción", valor: g.descripcion },
              { etiqueta: "Valor", valor: formatearMoneda(g.valor), cifra: true },
              { etiqueta: "Medio de pago", valor: etiquetaMedioPago(g.medio_pago) },
              { etiqueta: "Desde la caja", valor: g.caja_numero ? `Sí, caja ${g.caja_numero}${g.caja_cerrada ? " (cerrada: ya no se edita)" : ""}` : "No" },
              { etiqueta: "Registró", valor: g.usuario_nombre },
              { etiqueta: "Registrado", valor: formatearFechaHora(g.created_at) },
            ]}
          />
        </Card>
      )}
      <ModalEliminar
        gasto={g}
        abierto={eliminar}
        onCerrar={() => setEliminar(false)}
        onConfirmar={async () => {
          await api.delete(`${RUTA}/${id}`);
          navigate(RUTA);
        }}
      />
    </PantallaDetalle>
  );
}
