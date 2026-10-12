import { useEffect, useMemo, useState } from "react";
import { Ban, CircleCheck, Eye, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import EditorLineas from "@/components/EditorLineas";
import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import FotoPlato from "@/components/FotoPlato";
import PantallaDetalle from "@/components/PantallaDetalle";
import SubirImagen from "@/components/SubirImagen";
import {
  AccionesFila,
  Badge,
  BotonAccion,
  Button,
  Card,
  Checkbox,
  Detalle,
  EstadoBadge,
  Input,
  ModalConfirmar,
  PageHeader,
  Select,
  Table,
  TablaRecurso,
  Textarea,
} from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useCatalogo } from "@/hooks/useCatalogo";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFecha, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { legible, unidadesDe } from "@/lib/unidades";
import { MSG, esquemas } from "@/lib/validaciones";
import { costeo, costoDeLinea, costoDeReceta } from "@/modules/carta/costeo";

import "./carta.css";

/**
 * PLATOS DE LA CARTA (2026-10-12): precio, categoría, foto, si va a cocina o
 * es venta directa, receta (de ahí salen el costo, el margen y el % de costo)
 * y modificadores ("sin…" gratis, "extra…" con precio y su insumo). "Agotado
 * hoy" lo saca de la toma de pedidos por el resto de la jornada sin
 * desactivarlo.
 */
const RUTA = "/carta";
const URL = "/catalogo/productos";
const migas = (...resto) => migasDe(MIGAS.platos, ...resto);

const pct = (n) => (n == null ? "—" : `${formatearNumero(Math.round(Number(n) * 10) / 10)} %`);

export function BadgeDisponible({ producto }) {
  if (!producto.activo) return <Badge variante="neutro">Inactivo</Badge>;
  if (producto.agotado_hoy) return <Badge variante="negativo">Agotado hoy</Badge>;
  if (!producto.vigente) return <Badge variante="neutro">Fuera de vigencia</Badge>;
  return <Badge variante="positivo">Disponible</Badge>;
}

/** Diálogos compartidos de platos y combos: estado, agotado hoy y eliminar. */
export function DialogosProducto({ producto, dialogo, onCerrar, alTerminar, alEliminar, singular = "plato" }) {
  return (
    <>
      <ModalConfirmar
        abierto={dialogo === "estado"}
        onCerrar={onCerrar}
        titulo={producto?.activo ? `Desactivar ${producto?.nombre ?? singular}` : `Activar ${producto?.nombre ?? singular}`}
        textoConfirmar={producto?.activo ? "Desactivar" : "Activar"}
        mensaje={
          producto?.activo
            ? "Sale de la carta y de la toma de pedidos. Conserva su historial de ventas."
            : "Vuelve a la carta y a la toma de pedidos."
        }
        accion={`cambiar el estado de ${producto?.nombre ?? singular}`}
        mensajeExito={`${producto?.nombre} ${producto?.activo ? "desactivado" : "activado"}`}
        onConfirmar={async () => {
          await api.patch(`${URL}/${producto.id}/estado`, { activo: !producto.activo });
          alTerminar();
        }}
      />
      <ModalConfirmar
        abierto={dialogo === "agotado"}
        onCerrar={onCerrar}
        titulo={producto?.agotado_hoy ? `${producto?.nombre} vuelve a estar disponible` : `Marcar ${producto?.nombre ?? singular} agotado hoy`}
        textoConfirmar={producto?.agotado_hoy ? "Marcar disponible" : "Marcar agotado"}
        mensaje={
          producto?.agotado_hoy
            ? "Vuelve a ofrecerse en la toma de pedidos de hoy."
            : "No se ofrece en lo que queda de la jornada. Mañana vuelve solo; no se desactiva."
        }
        accion={`cambiar la disponibilidad de ${producto?.nombre ?? singular}`}
        mensajeExito={producto?.agotado_hoy ? `${producto?.nombre} disponible de nuevo` : `${producto?.nombre} agotado por hoy`}
        onConfirmar={async () => {
          await api.patch(`${URL}/${producto.id}/agotado`, { agotado: !producto.agotado_hoy });
          alTerminar();
        }}
      />
      <ModalConfirmar
        abierto={dialogo === "eliminar"}
        onCerrar={onCerrar}
        destructivo
        titulo={`Eliminar ${producto?.nombre ?? singular}`}
        textoConfirmar="Eliminar"
        mensaje="Esta acción no se puede deshacer. Si ya tiene ventas u órdenes, o está en un combo, el sistema lo bloqueará: desactívalo en su lugar."
        accion={`eliminar ${producto?.nombre ?? singular}`}
        mensajeExito={`${producto?.nombre} eliminado`}
        onConfirmar={async () => {
          await api.delete(`${URL}/${producto.id}`);
          (alEliminar ?? alTerminar)();
        }}
      />
    </>
  );
}

/** Acciones de una fila de la carta (platos y combos). */
export function accionesProducto({ p, puede, navigate, ruta, abrir }) {
  return (
    <AccionesFila>
      <BotonAccion icono={Eye} etiqueta={`Ver ${p.nombre}`} titulo="Ver detalle" onClick={() => navigate(`${ruta}/${p.id}`)} />
      {puede("productos", "editar") && (
        <BotonAccion icono={Pencil} etiqueta={`Editar ${p.nombre}`} titulo="Editar" onClick={() => navigate(`${ruta}/${p.id}/editar`)} />
      )}
      {puede("productos", "cambiar_estado") && (
        <BotonAccion
          icono={p.agotado_hoy ? CircleCheck : Ban}
          etiqueta={p.agotado_hoy ? `Marcar ${p.nombre} disponible` : `Marcar ${p.nombre} agotado hoy`}
          titulo={p.agotado_hoy ? "Marcar disponible" : "Agotado hoy"}
          onClick={() => abrir("agotado", p)}
        />
      )}
      {puede("productos", "cambiar_estado") && (
        <BotonAccion
          icono={Power}
          etiqueta={`${p.activo ? "Desactivar" : "Activar"} ${p.nombre}`}
          titulo={p.activo ? "Desactivar" : "Activar"}
          onClick={() => abrir("estado", p)}
        />
      )}
      {puede("productos", "eliminar") && (
        <BotonAccion icono={Trash2} etiqueta={`Eliminar ${p.nombre}`} titulo="Eliminar" onClick={() => abrir("eliminar", p)} />
      )}
    </AccionesFila>
  );
}

/** Columnas de costeo (solo para quien ve costos). */
export function columnasCosteo(verCostos) {
  if (!verCostos) return [];
  return [
    { clave: "costo", titulo: "Costo", cifra: true, render: (p) => (p.costo == null ? "Sin receta" : formatearMoneda(p.costo)) },
    { clave: "porcentaje_costo", titulo: "% costo", cifra: true, render: (p) => pct(p.porcentaje_costo) },
    { clave: "margen", titulo: "Margen", cifra: true, render: (p) => (p.margen == null ? "—" : formatearMoneda(p.margen)) },
  ];
}

// =====================================================================
// Listado
// =====================================================================
export function PlatosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [parametros] = useSearchParams();
  const [categoria, setCategoria] = useState("");
  const [disponibilidad, setDisponibilidad] = useState("");
  const [estado, setEstado] = useState("");
  const { items: categorias } = useCatalogo("/catalogo/categorias");
  const filtros = {
    tipo: "plato",
    ...(categoria ? { categoria_id: categoria } : {}),
    ...(disponibilidad ? { disponible: disponibilidad === "si" } : {}),
    ...(estado ? { activo: estado === "activo" } : {}),
  };
  const listado = useListadoPaginado(URL, { filtros, porPagina: 20, busquedaInicial: parametros.get("q") ?? "" });
  const [dialogo, setDialogo] = useState(null);

  const columnas = [
    { clave: "foto", titulo: "Foto", ajustar: true, render: (p) => <FotoPlato producto={p} className="miniatura" /> },
    {
      clave: "nombre",
      titulo: "Plato",
      render: (p) => (
        <Link to={`${RUTA}/${p.id}`} className="enlace">
          {p.nombre}
        </Link>
      ),
    },
    { clave: "categoria_nombre", titulo: "Categoría", render: (p) => p.categoria_nombre ?? "—" },
    { clave: "precio", titulo: "Precio", cifra: true, render: (p) => formatearMoneda(p.precio) },
    ...columnasCosteo(puede("costos", "ver")),
    { clave: "va_a_cocina", titulo: "Cocina", ajustar: true, render: (p) => (p.va_a_cocina ? "Sí" : "Venta directa") },
    { clave: "disponible", titulo: "Hoy", ajustar: true, render: (p) => <BadgeDisponible producto={p} /> },
    { clave: "acciones", titulo: "Acciones", render: (p) => accionesProducto({ p, puede, navigate, ruta: RUTA, abrir: (tipo, producto) => setDialogo({ tipo, producto }) }) },
  ];

  return (
    <div>
      <PageHeader
        titulo="Platos"
        descripcion="La carta con su precio y su receta: de la receta salen el costo y el margen de cada plato."
        migas={migas()}
        acciones={
          puede("productos", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} aria-hidden="true" /> Nuevo plato
            </Button>
          )
        }
      />
      <TablaRecurso
        exportar="carta"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar plato o código…"
        vacio="Todavía no hay platos en la carta."
        filtros={
          <>
            <Select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="w-44" aria-label="Filtrar por categoría">
              <option value="">Todas las categorías</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </Select>
            <Select value={disponibilidad} onChange={(e) => setDisponibilidad(e.target.value)} className="w-44" aria-label="Filtrar por disponibilidad">
              <option value="">Toda la carta</option>
              <option value="si">Disponibles hoy</option>
              <option value="no">No disponibles hoy</option>
            </Select>
            <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
              <option value="">Todos los estados</option>
              <option value="activo">Solo activos</option>
              <option value="inactivo">Solo inactivos</option>
            </Select>
          </>
        }
      />
      <DialogosProducto producto={dialogo?.producto} dialogo={dialogo?.tipo} onCerrar={() => setDialogo(null)} alTerminar={listado.recargar} />
    </div>
  );
}

// =====================================================================
// Formulario
// =====================================================================
const LINEA_RECETA = z.object({
  insumo_id: z.string().min(1, "Elige el insumo"),
  cantidad: esquemas.cantidad(),
  unidad: z.string().min(1, "Elige la unidad"),
  merma_porcentaje: esquemas.merma(),
}).loose();

const MODIFICADOR = z
  .object({
    tipo: z.enum(["sin", "extra"]),
    nombre: esquemas.nombreCarta(60),
    precio: esquemas.precio({ permitirCero: true }),
    insumo_id: z.string(),
    cantidad: esquemas.cantidad({ obligatorio: false }),
    unidad: z.string(),
  })
  .loose()
  .superRefine((m, ctx) => {
    if (m.tipo === "sin" && Number(m.precio) !== 0) ctx.addIssue({ code: "custom", path: ["precio"], message: "Un «sin…» es gratis: su precio debe ser 0" });
    if (m.tipo === "extra" && m.insumo_id && m.cantidad.trim() === "") ctx.addIssue({ code: "custom", path: ["cantidad"], message: "Indica cuánto lleva el extra" });
  });

const ESQUEMA = z.object({
  nombre: esquemas.nombreCarta(100),
  categoria_id: z.string(),
  precio: esquemas.precio(),
  sku: z.string().refine((s) => s.trim() === "" || /^[A-Za-z0-9_-]{2,50}$/.test(s.trim()), MSG.sku),
  descripcion: esquemas.descripcion(500),
  va_a_cocina: z.boolean(),
  receta: z.array(LINEA_RECETA).max(40),
  modificadores: z.array(MODIFICADOR).max(30),
});

const VACIO = { nombre: "", categoria_id: "", precio: "", sku: "", descripcion: "", va_a_cocina: true, receta: [], modificadores: [] };
const nuevaLinea = () => ({ insumo_id: "", cantidad: "", unidad: "", merma_porcentaje: "" });
const nuevoModificador = () => ({ tipo: "extra", nombre: "", precio: "0", insumo_id: "", cantidad: "", unidad: "", activo: true });

const aTexto = (n) => (n == null ? "" : String(Number(n)));

function aFormulario(p) {
  return {
    nombre: p.nombre,
    categoria_id: p.categoria_id ?? "",
    precio: aTexto(p.precio),
    sku: p.sku ?? "",
    descripcion: p.descripcion ?? "",
    va_a_cocina: p.va_a_cocina,
    receta: p.receta.map((l) => ({ _id: l.id, insumo_id: l.insumo_id, cantidad: aTexto(l.cantidad), unidad: l.unidad, merma_porcentaje: Number(l.merma_porcentaje) ? aTexto(l.merma_porcentaje) : "" })),
    modificadores: p.modificadores.map((m) => ({
      _id: m.id, id: m.id, tipo: m.tipo, nombre: m.nombre, precio: aTexto(m.precio), insumo_id: m.insumo_id ?? "",
      cantidad: aTexto(m.cantidad), unidad: m.unidad ?? "", activo: m.activo,
    })),
  };
}

function cuerpoDe(d) {
  return {
    nombre: d.nombre,
    categoria_id: d.categoria_id || null,
    precio: d.precio,
    sku: d.sku.trim() || null,
    descripcion: d.descripcion.trim() || null,
    va_a_cocina: d.va_a_cocina,
    receta: d.receta.map((l) => ({ insumo_id: l.insumo_id, cantidad: l.cantidad, unidad: l.unidad, merma_porcentaje: l.merma_porcentaje || "0" })),
    modificadores: d.modificadores.map((m) => ({
      ...(m.id ? { id: m.id } : {}),
      tipo: m.tipo,
      nombre: m.nombre,
      precio: m.tipo === "sin" ? "0" : m.precio || "0",
      insumo_id: m.insumo_id || null,
      cantidad: m.tipo === "extra" && m.insumo_id ? m.cantidad : null,
      unidad: m.tipo === "extra" && m.insumo_id ? m.unidad : null,
      activo: m.activo ?? true,
    })),
  };
}

/** Unidad sugerida al elegir un insumo: en la receta se habla en g y ml. */
const unidadSugerida = (insumo) => (insumo?.unidad === "kg" ? "g" : insumo?.unidad === "L" ? "ml" : insumo?.unidad ?? "");

function SelectorUnidad({ insumo, valor, onChange, etiqueta, ariaLabel, error, onBlur, campo, required = true }) {
  return (
    <Select etiqueta={etiqueta} aria-label={ariaLabel} value={valor} onChange={(e) => onChange(e.target.value)} onBlur={onBlur} error={error} required={required} data-campo={campo} disabled={!insumo}>
      <option value="">Unidad</option>
      {(insumo ? unidadesDe(insumo.unidad) : []).map((u) => (
        <option key={u.valor} value={u.valor}>
          {u.valor}
        </option>
      ))}
    </Select>
  );
}

function CamposPlato({ f, categorias, insumos, configuracion, verCostos }) {
  const insumosPorId = useMemo(() => Object.fromEntries(insumos.map((i) => [i.id, i])), [insumos]);
  const receta = f.form.receta;
  const resumen = costeo(costoDeReceta(receta, insumosPorId), f.form.precio, configuracion);

  const opcionesInsumo = (
    <>
      <option value="">Insumo…</option>
      {insumos.map((i) => (
        <option key={i.id} value={i.id}>
          {i.nombre} ({i.unidad})
        </option>
      ))}
    </>
  );

  return (
    <>
      <Seccion titulo="Datos del plato" descripcion="Los campos marcados con * son obligatorios.">
        <Input etiqueta="Nombre" {...f.props("nombre")} permitir="carta" maxLength={100} autoComplete="off" />
        <div className="fila-campos fila-campos--tres">
          <Input etiqueta="Precio de venta" {...f.props("precio")} permitir="decimal" cifra ayuda={configuracion?.impuesto_consumo?.incluido_en_precio ? "Con el impuesto al consumo incluido" : undefined} />
          <Select etiqueta="Categoría" {...f.props("categoria_id", { requerido: false })}>
            <option value="">Sin categoría</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Select>
          <Input etiqueta="Código" {...f.props("sku", { requerido: false })} permitir="sku" maxLength={50} cifra ayuda="Opcional" />
        </div>
        <Textarea etiqueta="Descripción" {...f.props("descripcion", { requerido: false })} maxLength={500} ayuda="Opcional: lo que lleva, para el mesero" />
        <Checkbox
          checked={f.form.va_a_cocina}
          onChange={(e) => f.setCampo("va_a_cocina", e.target.checked)}
          etiqueta="Va a cocina (sin marcar: venta directa, como una gaseosa; no sale en la comanda)"
        />
      </Seccion>

      <Seccion titulo="Receta" descripcion="Lo que lleva UNA porción. Escríbelo como se cocina (g, ml) aunque el insumo se compre en kg o L. La merma es lo que se pierde al pelar o limpiar.">
        <EditorLineas
          filas={receta}
          onCambiar={(filas) => f.setForm((prev) => ({ ...prev, receta: filas }))}
          nueva={nuevaLinea}
          textoAgregar="Agregar insumo"
          quitarEtiqueta="Quitar insumo de la línea"
          vacio="Sin receta: el plato no descuenta inventario y su costo queda «sin dato»."
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
                  onChange={(e) => cambiar({ insumo_id: e.target.value, unidad: unidadSugerida(insumosPorId[e.target.value]) })}
                  onBlur={() => f.tocar(`receta.${i}.insumo_id`)}
                  error={f.errorVisible(`receta.${i}.insumo_id`)}
                  data-campo={`receta.${i}.insumo_id`}
                >
                  {opcionesInsumo}
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
                  onBlur={() => f.tocar(`receta.${i}.cantidad`)}
                  error={f.errorVisible(`receta.${i}.cantidad`)}
                  data-campo={`receta.${i}.cantidad`}
                />
              ),
            },
            {
              clave: "unidad",
              etiqueta: "Unidad",
              ancho: "6rem",
              render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                <SelectorUnidad
                  insumo={insumosPorId[fila.insumo_id]}
                  valor={fila.unidad}
                  onChange={(v) => cambiar("unidad", v)}
                  etiqueta={etiqueta}
                  ariaLabel={ariaLabel}
                  onBlur={() => f.tocar(`receta.${i}.unidad`)}
                  error={f.errorVisible(`receta.${i}.unidad`)}
                  campo={`receta.${i}.unidad`}
                />
              ),
            },
            {
              clave: "merma",
              etiqueta: "Merma %",
              ancho: "5.5rem",
              render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                <Input
                  etiqueta={etiqueta}
                  aria-label={ariaLabel}
                  cifra
                  permitir="decimal"
                  placeholder="0"
                  value={fila.merma_porcentaje}
                  onChange={(e) => cambiar("merma_porcentaje", e.target.value)}
                  onBlur={() => f.tocar(`receta.${i}.merma_porcentaje`)}
                  error={f.errorVisible(`receta.${i}.merma_porcentaje`)}
                  data-campo={`receta.${i}.merma_porcentaje`}
                />
              ),
            },
          ]}
          debajo={
            verCostos
              ? (fila) => {
                  const c = costoDeLinea(fila, insumosPorId[fila.insumo_id]);
                  return c == null ? null : (
                    <>
                      Costo: <span className="cifra">{formatearMoneda(c)}</span>
                    </>
                  );
                }
              : undefined
          }
          pie={
            verCostos && (
              <>
                <span>
                  Costo de la porción: <strong className="cifra">{resumen.costo == null ? "—" : formatearMoneda(resumen.costo)}</strong>
                </span>
                <span>
                  % de costo <strong className="cifra">{pct(resumen.porcentaje)}</strong> · margen{" "}
                  <strong className="cifra">{resumen.margen == null ? "—" : formatearMoneda(resumen.margen)}</strong>
                </span>
              </>
            )
          }
        />
      </Seccion>

      <Seccion titulo="Modificadores" descripcion="«Sin tomate» es gratis y deja de descontar ese insumo. «Extra queso» suma su precio y su insumo. Salen resaltados en la comanda.">
        <EditorLineas
          filas={f.form.modificadores}
          onCambiar={(filas) => f.setForm((prev) => ({ ...prev, modificadores: filas }))}
          nueva={nuevoModificador}
          textoAgregar="Agregar modificador"
          quitarEtiqueta="Quitar modificador de la línea"
          maximo={30}
          vacio="Sin modificadores."
          columnas={[
            {
              clave: "tipo",
              etiqueta: "Tipo",
              ancho: "6rem",
              render: ({ fila, cambiar, etiqueta, ariaLabel }) => (
                <Select etiqueta={etiqueta} aria-label={ariaLabel} value={fila.tipo} onChange={(e) => cambiar({ tipo: e.target.value, precio: e.target.value === "sin" ? "0" : fila.precio })}>
                  <option value="extra">Extra</option>
                  <option value="sin">Sin</option>
                </Select>
              ),
            },
            {
              clave: "nombre",
              etiqueta: "Nombre",
              render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                <Input
                  etiqueta={etiqueta}
                  aria-label={ariaLabel}
                  required
                  permitir="carta"
                  maxLength={60}
                  placeholder={fila.tipo === "sin" ? "Tomate" : "Queso"}
                  value={fila.nombre}
                  onChange={(e) => cambiar("nombre", e.target.value)}
                  onBlur={() => f.tocar(`modificadores.${i}.nombre`)}
                  error={f.errorVisible(`modificadores.${i}.nombre`)}
                  data-campo={`modificadores.${i}.nombre`}
                />
              ),
            },
            {
              clave: "precio",
              etiqueta: "Precio",
              ancho: "6.5rem",
              render: ({ fila, i, cambiar, etiqueta, ariaLabel }) => (
                <Input
                  etiqueta={etiqueta}
                  aria-label={ariaLabel}
                  cifra
                  permitir="decimal"
                  disabled={fila.tipo === "sin"}
                  value={fila.precio}
                  onChange={(e) => cambiar("precio", e.target.value)}
                  onBlur={() => f.tocar(`modificadores.${i}.precio`)}
                  error={f.errorVisible(`modificadores.${i}.precio`)}
                  data-campo={`modificadores.${i}.precio`}
                />
              ),
            },
            {
              clave: "insumo",
              etiqueta: "Insumo",
              render: ({ fila, cambiar, etiqueta, ariaLabel }) => (
                <Select
                  etiqueta={etiqueta}
                  aria-label={ariaLabel}
                  value={fila.insumo_id}
                  onChange={(e) => cambiar({ insumo_id: e.target.value, unidad: unidadSugerida(insumosPorId[e.target.value]) })}
                >
                  <option value="">{fila.tipo === "sin" ? "No quita insumo" : "No suma insumo"}</option>
                  {(fila.tipo === "sin" ? insumos.filter((x) => receta.some((l) => l.insumo_id === x.id)) : insumos).map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.nombre}
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
                  cifra
                  permitir="cantidad"
                  disabled={fila.tipo === "sin" || !fila.insumo_id}
                  value={fila.tipo === "sin" ? "" : fila.cantidad}
                  onChange={(e) => cambiar("cantidad", e.target.value)}
                  onBlur={() => f.tocar(`modificadores.${i}.cantidad`)}
                  error={f.errorVisible(`modificadores.${i}.cantidad`)}
                  data-campo={`modificadores.${i}.cantidad`}
                />
              ),
            },
            {
              clave: "unidad",
              etiqueta: "Unidad",
              ancho: "5.5rem",
              render: ({ fila, cambiar, etiqueta, ariaLabel }) =>
                fila.tipo === "sin" ? (
                  <Select etiqueta={etiqueta} aria-label={ariaLabel} disabled value="">
                    <option value="">—</option>
                  </Select>
                ) : (
                  <SelectorUnidad
                    insumo={fila.insumo_id ? insumosPorId[fila.insumo_id] : null}
                    valor={fila.unidad}
                    onChange={(v) => cambiar("unidad", v)}
                    etiqueta={etiqueta}
                    ariaLabel={ariaLabel}
                    required={false}
                  />
                ),
            },
          ]}
        />
      </Seccion>
    </>
  );
}

/** Categorías e insumos para el formulario (los insumos solo si el rol los ve). */
function useDatosDelFormulario() {
  const { puede, tenant } = useAuth();
  const { items: categorias } = useCatalogo("/catalogo/categorias");
  const { items: insumos } = useCatalogo(puede("insumos", "ver") ? "/inventario/insumos" : null);
  return { categorias, insumos, configuracion: tenant?.configuracion, verCostos: puede("costos", "ver") };
}

export function PlatoNuevo() {
  const datos = useDatosDelFormulario();
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Plato creado", accion: "crear el plato" });
  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo plato" descripcion="La foto se sube después, desde el detalle o al editar." migas={migas({ etiqueta: "Nuevo plato" })} />
      <FormularioPantalla
        id="form-plato"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, { tipo: "plato", ...cuerpoDe(d) }))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposPlato f={f} {...datos} />
      </FormularioPantalla>
    </div>
  );
}

export function PlatoEditar() {
  const { id } = useParams();
  const datos = useDatosDelFormulario();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el plato" });
  useEffect(() => {
    if (data) f.reiniciar(aFormulario(data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar ${data.nombre}` : "Editar plato"}
      migas={migas({ etiqueta: data?.nombre ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-plato"
        onSubmit={(e) => guardar(e, (d) => api.put(`${URL}/${id}`, cuerpoDe(d)))}
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <Seccion titulo="Foto" descripcion="Se sube al elegirla, aparte del botón Guardar. Se recorta cuadrada.">
          <SubirImagen
            etiqueta="Foto del plato"
            imagenId={data?.imagen_id}
            urlSubir={`${URL}/${id}/imagen`}
            urlQuitar={`${URL}/${id}/imagen`}
            textoAlt={data?.nombre ?? ""}
            mensajeExito="Foto actualizada"
            mensajeQuitada="Foto quitada"
            onCambio={recargar}
          />
        </Seccion>
        <CamposPlato f={f} {...datos} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

// =====================================================================
// Detalle
// =====================================================================
export function TarjetaCosteo({ producto }) {
  return (
    <Card titulo="Costo y margen" descripcion="De la receta, con el costo vigente de cada insumo.">
      {producto.costo == null ? (
        <p className="text-[13px] text-[var(--texto-secundario)]">
          Sin receta completa: arma la receta para conocer el costo y el margen de {producto.nombre}.
        </p>
      ) : (
        <div className="carta-costeo">
          <div>
            <p className="carta-costeo__etiqueta">% de costo</p>
            <p className="dato-grande cifra">{pct(producto.porcentaje_costo)}</p>
          </div>
          <Detalle
            campos={[
              { etiqueta: "Costo por porción", valor: formatearMoneda(producto.costo), cifra: true },
              { etiqueta: "Precio sin impuesto", valor: formatearMoneda(producto.precio_neto), cifra: true },
              { etiqueta: "Margen", valor: formatearMoneda(producto.margen), cifra: true },
            ]}
          />
        </div>
      )}
    </Card>
  );
}

export function PlatoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  const verCostos = puede("costos", "ver");

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data?.nombre ?? "Plato"}
      descripcion={data ? [data.categoria_nombre, data.va_a_cocina ? "va a cocina" : "venta directa"].filter(Boolean).join(" · ") : undefined}
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
            <Card titulo="Datos del plato">
              <div className="flex items-start gap-5">
                <FotoPlato producto={data} tamano={112} className="shrink-0" alt={data.imagen_id ? `Foto de ${data.nombre}` : ""} />
                <div className="flex-1 min-w-0">
                  <Detalle
                    campos={[
                      { etiqueta: "Precio", valor: formatearMoneda(data.precio), cifra: true },
                      { etiqueta: "Categoría", valor: data.categoria_nombre },
                      { etiqueta: "Código", valor: data.sku, cifra: true },
                      { etiqueta: "Cocina", valor: data.va_a_cocina ? "Va a cocina y sale en la comanda" : "Venta directa: no pasa por cocina" },
                      { etiqueta: "Hoy", valor: <BadgeDisponible producto={data} /> },
                      { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
                      { etiqueta: "Descripción", valor: data.descripcion },
                      { etiqueta: "Creado", valor: formatearFecha(data.created_at) },
                    ]}
                  />
                </div>
              </div>
            </Card>
            {verCostos && <TarjetaCosteo producto={data} />}
          </div>
          <Card titulo="Receta" descripcion="Por porción. Al vender, estos insumos salen de la bodega.">
            <Table
              columnas={[
                {
                  clave: "insumo_nombre",
                  titulo: "Insumo",
                  render: (l) =>
                    puede("insumos", "ver") ? (
                      <Link to={`/inventario/insumos/${l.insumo_id}`} className="enlace">
                        {l.insumo_nombre}
                      </Link>
                    ) : (
                      l.insumo_nombre
                    ),
                },
                { clave: "cantidad", titulo: "Cantidad", cifra: true, render: (l) => legible(l.cantidad, l.unidad) },
                { clave: "merma_porcentaje", titulo: "Merma", cifra: true, render: (l) => (Number(l.merma_porcentaje) ? pct(l.merma_porcentaje) : "—") },
                ...(verCostos ? [{ clave: "costo", titulo: "Costo", cifra: true, render: (l) => formatearMoneda(l.costo) }] : []),
              ]}
              filas={data.receta}
              vacio="Sin receta: este plato no descuenta inventario."
            />
          </Card>
          <Card titulo="Modificadores">
            <Table
              columnas={[
                { clave: "tipo", titulo: "Comanda", render: (m) => <span className="carta-modificador">{`${m.tipo} ${m.nombre}`.toUpperCase()}</span> },
                { clave: "precio", titulo: "Precio", cifra: true, render: (m) => (Number(m.precio) ? `+${formatearMoneda(m.precio)}` : "Gratis") },
                {
                  clave: "insumo_nombre",
                  titulo: "Inventario",
                  render: (m) =>
                    !m.insumo_nombre ? "—" : m.tipo === "sin" ? `No descuenta ${m.insumo_nombre}` : `Suma ${legible(m.cantidad, m.unidad)} de ${m.insumo_nombre}`,
                },
                ...(verCostos ? [{ clave: "costo", titulo: "Costo", cifra: true, render: (m) => (m.costo == null ? "—" : formatearMoneda(m.costo)) }] : []),
              ]}
              filas={data.modificadores}
              vacio="Sin modificadores."
            />
          </Card>
        </div>
      )}
      <DialogosProducto producto={data} dialogo={dialogo} onCerrar={() => setDialogo(null)} alTerminar={recargar} alEliminar={() => navigate(RUTA)} />
    </PantallaDetalle>
  );
}
