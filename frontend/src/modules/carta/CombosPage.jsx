import { useEffect, useMemo, useState } from "react";
import { Ban, CircleCheck, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import EditorLineas from "@/components/EditorLineas";
import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import FotoPlato from "@/components/FotoPlato";
import PantallaDetalle from "@/components/PantallaDetalle";
import SubirImagen from "@/components/SubirImagen";
import { Badge, Button, Card, Detalle, EstadoBadge, GrupoCasillas, Input, PageHeader, Select, Table, TablaRecurso, Textarea } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useCatalogo } from "@/hooks/useCatalogo";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFecha, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";
import { costeo } from "@/modules/carta/costeo";
import { BadgeDisponible, DialogosProducto, TarjetaCosteo, accionesProducto, columnasCosteo } from "@/modules/carta/PlatosPage";

import "./carta.css";

/**
 * COMBOS Y PROMOCIONES (2026-10-12): varios platos a un precio especial, con
 * vigencia (desde/hasta) y días de la semana: las promociones para
 * estudiantes. Al venderse, cada plato del combo descuenta su propia receta.
 */
const RUTA = "/carta/combos";
const URL = "/catalogo/productos";
const migas = (...resto) => migasDe(MIGAS.combos, ...resto);

export const DIAS = [
  { valor: "0", etiqueta: "Lun" },
  { valor: "1", etiqueta: "Mar" },
  { valor: "2", etiqueta: "Mié" },
  { valor: "3", etiqueta: "Jue" },
  { valor: "4", etiqueta: "Vie" },
  { valor: "5", etiqueta: "Sáb" },
  { valor: "6", etiqueta: "Dom" },
];

function textoVigencia(c) {
  const partes = [];
  if (c.vigente_desde || c.vigente_hasta) {
    partes.push(`${c.vigente_desde ? formatearFecha(`${c.vigente_desde}T12:00:00`) : "siempre"} → ${c.vigente_hasta ? formatearFecha(`${c.vigente_hasta}T12:00:00`) : "sin fin"}`);
  }
  if (c.dias_semana?.length) partes.push(c.dias_semana.map((d) => DIAS[d].etiqueta).join(" "));
  return partes.join(" · ") || "Todos los días";
}

export function CombosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [estado, setEstado] = useState("");
  const listado = useListadoPaginado(URL, { filtros: { tipo: "combo", ...(estado ? { activo: estado === "activo" } : {}) }, porPagina: 20 });
  const [dialogo, setDialogo] = useState(null);

  const columnas = [
    { clave: "foto", titulo: "Foto", ajustar: true, render: (c) => <FotoPlato producto={c} className="miniatura" /> },
    {
      clave: "nombre",
      titulo: "Combo",
      render: (c) => (
        <Link to={`${RUTA}/${c.id}`} className="enlace">
          {c.nombre}
        </Link>
      ),
    },
    { clave: "componentes", titulo: "Incluye", render: (c) => c.componentes.map((x) => `${x.cantidad > 1 ? `${x.cantidad} × ` : ""}${x.producto_nombre}`).join(" + ") },
    { clave: "precio", titulo: "Precio", cifra: true, render: (c) => formatearMoneda(c.precio) },
    ...columnasCosteo(puede("costos", "ver")),
    { clave: "vigencia", titulo: "Vigencia", render: textoVigencia },
    { clave: "disponible", titulo: "Hoy", ajustar: true, render: (c) => <BadgeDisponible producto={c} /> },
    { clave: "acciones", titulo: "Acciones", render: (c) => accionesProducto({ p: c, puede, navigate, ruta: RUTA, abrir: (tipo, producto) => setDialogo({ tipo, producto }) }) },
  ];

  return (
    <div>
      <PageHeader
        titulo="Combos y promociones"
        descripcion="Varios platos a un precio especial, con vigencia y días: las promociones para estudiantes."
        migas={migas()}
        acciones={
          puede("productos", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} aria-hidden="true" /> Nuevo combo
            </Button>
          )
        }
      />
      <TablaRecurso
        exportar="combos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar combo…"
        vacio="Todavía no hay combos. Arma uno con platos que aguanten el descuento."
        filtros={
          <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            <option value="activo">Solo activos</option>
            <option value="inactivo">Solo inactivos</option>
          </Select>
        }
      />
      <DialogosProducto producto={dialogo?.producto} dialogo={dialogo?.tipo} onCerrar={() => setDialogo(null)} alTerminar={listado.recargar} singular="combo" />
    </div>
  );
}

// =====================================================================
// Formulario
// =====================================================================
const fecha = z.string().refine((s) => s === "" || /^\d{4}-\d{2}-\d{2}$/.test(s), "Fecha inválida");
const ESQUEMA = z
  .object({
    nombre: esquemas.nombreCarta(100),
    categoria_id: z.string(),
    precio: esquemas.precio(),
    descripcion: esquemas.descripcion(500),
    vigente_desde: fecha,
    vigente_hasta: fecha,
    dias_semana: z.array(z.string()),
    componentes: z
      .array(z.object({ producto_id: z.string().min(1, "Elige el plato"), cantidad: esquemas.entero(1, 20) }).loose())
      .min(1, "Un combo necesita al menos un plato")
      .max(15),
  })
  .refine((d) => !d.vigente_desde || !d.vigente_hasta || d.vigente_hasta >= d.vigente_desde, {
    path: ["vigente_hasta"],
    message: "La vigencia termina antes de empezar: revisa las fechas",
  });

const VACIO = { nombre: "", categoria_id: "", precio: "", descripcion: "", vigente_desde: "", vigente_hasta: "", dias_semana: [], componentes: [] };

const cuerpoDe = (d) => ({
  nombre: d.nombre,
  categoria_id: d.categoria_id || null,
  precio: d.precio,
  descripcion: d.descripcion.trim() || null,
  vigente_desde: d.vigente_desde || null,
  vigente_hasta: d.vigente_hasta || null,
  dias_semana: d.dias_semana.length ? d.dias_semana.map(Number) : null,
  componentes: d.componentes.map((c) => ({ producto_id: c.producto_id, cantidad: Number(c.cantidad) })),
});

function CamposCombo({ f }) {
  const { puede, tenant } = useAuth();
  const { items: categorias } = useCatalogo("/catalogo/categorias");
  const { items: platos } = useCatalogo(`${URL}?tipo=plato`);
  const porId = useMemo(() => Object.fromEntries(platos.map((p) => [p.id, p])), [platos]);
  const componentes = f.form.componentes;
  const sueltos = componentes.reduce((acc, c) => acc + Number(porId[c.producto_id]?.precio ?? 0) * Number(c.cantidad || 0), 0);
  const costos = componentes.map((c) => porId[c.producto_id]?.costo);
  const costo = costos.length && costos.every((c) => c != null)
    ? componentes.reduce((acc, c) => acc + Number(porId[c.producto_id].costo) * Number(c.cantidad || 0), 0)
    : null;
  const resumen = costeo(costo, f.form.precio, tenant?.configuracion);
  const ahorro = sueltos - Number(f.form.precio || 0);

  return (
    <>
      <Seccion titulo="Datos del combo" descripcion="Los campos marcados con * son obligatorios.">
        <Input etiqueta="Nombre" {...f.props("nombre")} permitir="carta" maxLength={100} autoComplete="off" />
        <div className="fila-campos">
          <Input etiqueta="Precio del combo" {...f.props("precio")} permitir="decimal" cifra />
          <Select etiqueta="Categoría" {...f.props("categoria_id", { requerido: false })}>
            <option value="">Sin categoría</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Select>
        </div>
        <Textarea etiqueta="Descripción" {...f.props("descripcion", { requerido: false })} maxLength={500} ayuda="Opcional" />
      </Seccion>
      <Seccion titulo="Platos del combo" descripcion="Cada plato descuenta su propia receta al venderse.">
        <EditorLineas
          filas={componentes}
          onCambiar={(filas) => f.setForm((prev) => ({ ...prev, componentes: filas }))}
          nueva={() => ({ producto_id: "", cantidad: "1" })}
          textoAgregar="Agregar plato"
          quitarEtiqueta="Quitar plato de la línea"
          maximo={15}
          vacio={f.errorVisible("componentes") ?? "Agrega al menos un plato."}
          columnas={[
            {
              clave: "plato",
              etiqueta: "Plato",
              render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                <Select
                  etiqueta={etiqueta}
                  aria-label={ariaLabel}
                  required
                  value={fila.producto_id}
                  onChange={(e) => cambiar("producto_id", e.target.value)}
                  onBlur={() => f.tocar(`componentes.${i}.producto_id`)}
                  error={f.errorVisible(`componentes.${i}.producto_id`)}
                  data-campo={`componentes.${i}.producto_id`}
                >
                  <option value="">Plato…</option>
                  {platos.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre} · {formatearMoneda(p.precio)}
                    </option>
                  ))}
                </Select>
              ),
            },
            {
              clave: "cantidad",
              etiqueta: "Cantidad",
              ancho: "6rem",
              render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                <Input
                  etiqueta={etiqueta}
                  aria-label={ariaLabel}
                  required
                  cifra
                  permitir="entero"
                  maxLength={2}
                  value={fila.cantidad}
                  onChange={(e) => cambiar("cantidad", e.target.value)}
                  onBlur={() => f.tocar(`componentes.${i}.cantidad`)}
                  error={f.errorVisible(`componentes.${i}.cantidad`)}
                  data-campo={`componentes.${i}.cantidad`}
                />
              ),
            },
          ]}
          pie={
            componentes.length > 0 && (
              <>
                <span>
                  Por separado: <strong className="cifra">{formatearMoneda(sueltos)}</strong>
                  {ahorro > 0 && <> · el cliente ahorra <span className="cifra">{formatearMoneda(ahorro)}</span></>}
                </span>
                {puede("costos", "ver") && (
                  <span>
                    % de costo <strong className="cifra">{resumen.porcentaje == null ? "—" : `${formatearNumero(Math.round(resumen.porcentaje * 10) / 10)} %`}</strong>
                  </span>
                )}
              </>
            )
          }
        />
      </Seccion>
      <Seccion titulo="Vigencia" descripcion="Fuera de la vigencia o de sus días, el combo no se ofrece en la toma de pedidos.">
        <div className="fila-campos">
          <Input etiqueta="Desde" type="date" {...f.props("vigente_desde", { requerido: false })} cifra ayuda="Vacío: desde ya" />
          <Input etiqueta="Hasta" type="date" {...f.props("vigente_hasta", { requerido: false })} cifra ayuda="Vacío: sin fecha de fin" />
        </div>
        <GrupoCasillas
          etiqueta="Días de la semana"
          campo="dias_semana"
          opciones={DIAS}
          valor={f.form.dias_semana}
          onChange={(v) => f.setCampo("dias_semana", v)}
          ayuda="Ninguno marcado: todos los días"
        />
      </Seccion>
    </>
  );
}

export function ComboNuevo() {
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Combo creado", accion: "crear el combo" });
  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo combo" migas={migas({ etiqueta: "Nuevo combo" })} />
      <FormularioPantalla
        id="form-combo"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, { tipo: "combo", ...cuerpoDe(d) }))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposCombo f={f} />
      </FormularioPantalla>
    </div>
  );
}

export function ComboEditar() {
  const { id } = useParams();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el combo" });
  useEffect(() => {
    if (data) {
      f.reiniciar({
        nombre: data.nombre,
        categoria_id: data.categoria_id ?? "",
        precio: String(Number(data.precio)),
        descripcion: data.descripcion ?? "",
        vigente_desde: data.vigente_desde ?? "",
        vigente_hasta: data.vigente_hasta ?? "",
        dias_semana: (data.dias_semana ?? []).map(String),
        componentes: data.componentes.map((c) => ({ _id: c.producto_id, producto_id: c.producto_id, cantidad: String(c.cantidad) })),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar ${data.nombre}` : "Editar combo"}
      migas={migas({ etiqueta: data?.nombre ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-combo"
        onSubmit={(e) => guardar(e, (d) => api.put(`${URL}/${id}`, cuerpoDe(d)))}
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <Seccion titulo="Foto" descripcion="Se sube al elegirla, aparte del botón Guardar.">
          <SubirImagen
            etiqueta="Foto del combo"
            imagenId={data?.imagen_id}
            urlSubir={`${URL}/${id}/imagen`}
            urlQuitar={`${URL}/${id}/imagen`}
            textoAlt={data?.nombre ?? ""}
            mensajeExito="Foto actualizada"
            mensajeQuitada="Foto quitada"
            onCambio={recargar}
          />
        </Seccion>
        <CamposCombo f={f} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function ComboDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  const verCostos = puede("costos", "ver");
  const sueltos = data?.componentes.reduce((acc, c) => acc + Number(c.precio) * c.cantidad, 0) ?? 0;

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data?.nombre ?? "Combo"}
      descripcion={data ? textoVigencia(data) : undefined}
      migas={migas({ etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("productos", "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogo("agotado")}>
              {data?.agotado_hoy ? <CircleCheck size={14} aria-hidden="true" /> : <Ban size={14} aria-hidden="true" />}
              {data?.agotado_hoy ? "Marcar disponible" : "Agotado hoy"}
            </Button>
          )}
          {puede("productos", "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogo("estado")}>
              <Power size={14} aria-hidden="true" /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede("productos", "eliminar") && (
            <Button variante="terciario" onClick={() => setDialogo("eliminar")}>
              <Trash2 size={14} aria-hidden="true" /> Eliminar
            </Button>
          )}
          {puede("productos", "editar") && (
            <Button onClick={() => navigate(`${RUTA}/${id}/editar`)}>
              <Pencil size={14} aria-hidden="true" /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Datos del combo">
              <div className="flex items-start gap-5">
                <FotoPlato producto={data} tamano={112} className="shrink-0" alt={data.imagen_id ? `Foto de ${data.nombre}` : ""} />
                <div className="flex-1 min-w-0">
                  <Detalle
                    campos={[
                      { etiqueta: "Precio", valor: formatearMoneda(data.precio), cifra: true },
                      { etiqueta: "Por separado", valor: formatearMoneda(sueltos), cifra: true },
                      { etiqueta: "Categoría", valor: data.categoria_nombre },
                      { etiqueta: "Vigencia", valor: textoVigencia(data) },
                      { etiqueta: "Hoy", valor: <BadgeDisponible producto={data} /> },
                      { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
                      { etiqueta: "Descripción", valor: data.descripcion },
                    ]}
                  />
                </div>
              </div>
            </Card>
            {verCostos && <TarjetaCosteo producto={data} />}
          </div>
          <Card titulo="Platos del combo">
            <Table
              idFila={(c) => c.producto_id}
              columnas={[
                {
                  clave: "producto_nombre",
                  titulo: "Plato",
                  render: (c) => (
                    <Link to={`/carta/${c.producto_id}`} className="enlace">
                      {c.producto_nombre}
                    </Link>
                  ),
                },
                { clave: "cantidad", titulo: "Cantidad", cifra: true, render: (c) => formatearNumero(c.cantidad) },
                { clave: "precio", titulo: "Precio suelto", cifra: true, render: (c) => formatearMoneda(c.precio) },
                ...(verCostos ? [{ clave: "costo", titulo: "Costo", cifra: true, render: (c) => (c.costo == null ? "Sin receta" : formatearMoneda(c.costo)) }] : []),
                { clave: "va_a_cocina", titulo: "Cocina", render: (c) => (c.va_a_cocina ? "Sí" : <Badge variante="neutro">Venta directa</Badge>) },
              ]}
              filas={data.componentes}
            />
          </Card>
        </div>
      )}
      <DialogosProducto producto={data} dialogo={dialogo} onCerrar={() => setDialogo(null)} alTerminar={recargar} alEliminar={() => navigate(RUTA)} singular="combo" />
    </PantallaDetalle>
  );
}
