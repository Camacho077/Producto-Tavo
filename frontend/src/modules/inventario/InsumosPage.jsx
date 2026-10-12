import { useEffect, useId, useMemo, useState } from "react";
import { Eye, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import {
  AccionesFila,
  Badge,
  BotonAccion,
  Button,
  Card,
  Detalle,
  EstadoBadge,
  Input,
  ModalConfirmar,
  PageHeader,
  Select,
  Table,
  TablaRecurso,
} from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFecha, formatearFechaHora, formatearMoneda, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { UNIDADES, legible, porUnidad } from "@/lib/unidades";
import { esquemas } from "@/lib/validaciones";

/**
 * INSUMOS (2026-10-12): la materia prima del restaurante. La existencia NO se
 * edita: es la suma de sus movimientos (compras, ventas por receta, mermas,
 * ajustes) y aquí solo se ve, con su historial. El costo unitario lo ven solo
 * los roles con "costos.ver"; las compras lo recalculan por promedio
 * ponderado.
 */
const RUTA = "/inventario/insumos";
const URL = "/inventario/insumos";
const migas = (...resto) => migasDe(MIGAS.insumos, ...resto);

export const TIPOS_MOVIMIENTO = {
  inicial: { etiqueta: "Existencia inicial", variante: "neutro" },
  compra: { etiqueta: "Compra", variante: "positivo" },
  anulacion_compra: { etiqueta: "Anulación de compra", variante: "neutro" },
  venta: { etiqueta: "Venta", variante: "neutro" },
  anulacion_venta: { etiqueta: "Anulación de venta", variante: "neutro" },
  merma: { etiqueta: "Merma", variante: "negativo" },
  ajuste: { etiqueta: "Ajuste por conteo", variante: "neutro" },
};

function BadgeMinimo({ insumo }) {
  if (!insumo.bajo_minimo) return null;
  return (
    <Badge variante="negativo" title={`Mínimo: ${legible(insumo.minimo, insumo.unidad)}`}>
      ▼ Bajo el mínimo
    </Badge>
  );
}

function ModalEstado({ insumo, abierto, onCerrar, onConfirmar }) {
  return (
    <ModalConfirmar
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={insumo?.activo ? `Desactivar ${insumo?.nombre ?? "insumo"}` : `Activar ${insumo?.nombre ?? "insumo"}`}
      textoConfirmar={insumo?.activo ? "Desactivar" : "Activar"}
      mensaje={
        insumo?.activo
          ? "Deja de ofrecerse en compras y recetas nuevas; conserva su historial y las recetas que ya lo usan."
          : "Vuelve a ofrecerse en compras y recetas."
      }
      accion={`cambiar el estado del insumo ${insumo?.nombre ?? ""}`.trim()}
      mensajeExito={`${insumo?.nombre} ${insumo?.activo ? "desactivado" : "activado"}`}
      onConfirmar={onConfirmar}
    />
  );
}

function ModalEliminar({ insumo, abierto, onCerrar, onConfirmar }) {
  return (
    <ModalConfirmar
      abierto={abierto}
      onCerrar={onCerrar}
      destructivo
      titulo={`Eliminar ${insumo?.nombre ?? "insumo"}`}
      textoConfirmar="Eliminar"
      mensaje="Esta acción no se puede deshacer. Si el insumo está en una receta o ya tiene movimientos, el sistema lo bloqueará: desactívalo en su lugar."
      accion={`eliminar el insumo ${insumo?.nombre ?? ""}`.trim()}
      mensajeExito={`${insumo?.nombre} eliminado`}
      onConfirmar={onConfirmar}
    />
  );
}

// =====================================================================
// Listado
// =====================================================================
export function InsumosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const verCostos = puede("costos", "ver");
  const [parametros] = useSearchParams();
  const [grupo, setGrupo] = useState("");
  const [situacion, setSituacion] = useState(parametros.get("bajo_minimo") ? "bajo" : "");
  const [estado, setEstado] = useState("");
  const { data: grupos } = useApiResource("/inventario/grupos");
  const filtros = {
    ...(grupo ? { grupo } : {}),
    ...(situacion ? { bajo_minimo: situacion === "bajo" } : {}),
    ...(estado ? { activo: estado === "activo" } : {}),
  };
  const listado = useListadoPaginado(URL, { filtros, porPagina: 20 });
  const [dialogo, setDialogo] = useState(null);
  const insumo = dialogo?.insumo;

  const columnas = [
    {
      clave: "nombre",
      titulo: "Insumo",
      render: (i) => (
        <Link to={`${RUTA}/${i.id}`} className="enlace">
          {i.nombre}
        </Link>
      ),
    },
    { clave: "grupo", titulo: "Grupo", render: (i) => i.grupo ?? "—" },
    {
      clave: "existencia",
      titulo: "Existencia",
      cifra: true,
      render: (i) => (
        <span className="flex flex-col items-center gap-1">
          <span>{legible(i.existencia, i.unidad)}</span>
          <BadgeMinimo insumo={i} />
        </span>
      ),
    },
    { clave: "minimo", titulo: "Mínimo", cifra: true, render: (i) => (Number(i.minimo) > 0 ? legible(i.minimo, i.unidad) : "—") },
    ...(verCostos
      ? [
          { clave: "costo_unitario", titulo: "Costo unitario", cifra: true, render: (i) => `${formatearMoneda(i.costo_unitario)} ${porUnidad(i.unidad)}` },
          { clave: "costo_total", titulo: "Costo total", cifra: true, render: (i) => formatearMoneda(i.costo_total) },
        ]
      : []),
    { clave: "platos_count", titulo: "Platos", cifra: true, render: (i) => formatearNumero(i.platos_count) },
    { clave: "activo", titulo: "Estado", ajustar: true, render: (i) => <EstadoBadge activo={i.activo} /> },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (i) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver ${i.nombre}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA}/${i.id}`)} />
          {puede("insumos", "editar") && (
            <BotonAccion icono={Pencil} etiqueta={`Editar ${i.nombre}`} titulo="Editar" onClick={() => navigate(`${RUTA}/${i.id}/editar`)} />
          )}
          {puede("insumos", "cambiar_estado") && (
            <BotonAccion
              icono={Power}
              etiqueta={`${i.activo ? "Desactivar" : "Activar"} ${i.nombre}`}
              titulo={i.activo ? "Desactivar" : "Activar"}
              onClick={() => setDialogo({ tipo: "estado", insumo: i })}
            />
          )}
          {puede("insumos", "eliminar") && (
            <BotonAccion icono={Trash2} etiqueta={`Eliminar ${i.nombre}`} titulo="Eliminar" onClick={() => setDialogo({ tipo: "eliminar", insumo: i })} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Insumos"
        descripcion="Materia prima con su existencia. Las compras la suben y cada venta la baja según la receta del plato."
        migas={migas()}
        acciones={
          puede("insumos", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} aria-hidden="true" /> Nuevo insumo
            </Button>
          )
        }
      />
      <TablaRecurso
        exportar="insumos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar insumo o grupo…"
        vacio="Todavía no hay insumos: crea los que usan tus recetas (arroz, pollo, queso…)."
        filtros={
          <>
            <Select value={grupo} onChange={(e) => setGrupo(e.target.value)} className="w-40" aria-label="Filtrar por grupo">
              <option value="">Todos los grupos</option>
              {(grupos ?? []).map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
            <Select value={situacion} onChange={(e) => setSituacion(e.target.value)} className="w-44" aria-label="Filtrar por existencia">
              <option value="">Toda la existencia</option>
              <option value="bajo">Bajo el mínimo</option>
              <option value="ok">Sobre el mínimo</option>
            </Select>
            <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
              <option value="">Todos los estados</option>
              <option value="activo">Solo activos</option>
              <option value="inactivo">Solo inactivos</option>
            </Select>
          </>
        }
      />
      <ModalEstado
        insumo={insumo}
        abierto={dialogo?.tipo === "estado"}
        onCerrar={() => setDialogo(null)}
        onConfirmar={async () => {
          await api.patch(`${URL}/${insumo.id}/estado`, { activo: !insumo.activo });
          listado.recargar();
        }}
      />
      <ModalEliminar
        insumo={insumo}
        abierto={dialogo?.tipo === "eliminar"}
        onCerrar={() => setDialogo(null)}
        onConfirmar={async () => {
          await api.delete(`${URL}/${insumo.id}`);
          listado.recargar();
        }}
      />
    </div>
  );
}

// =====================================================================
// Formulario
// =====================================================================
const esquemaInsumo = (nuevo) =>
  z.object({
    nombre: esquemas.nombreCarta(100),
    unidad: z.string().min(1, "Elige la unidad en que se lleva el insumo"),
    grupo: z.string().refine((s) => s.trim() === "" || /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9' .,\-+&/()%]{2,40}$/.test(s) && s === s.trim(), "Solo letras, números, espacios y . , - + & / ( ) % (entre 2 y 40)"),
    minimo: esquemas.cantidad({ permitirCero: true }),
    costo_unitario: esquemas.costo(),
    ...(nuevo ? { existencia_inicial: esquemas.cantidad({ permitirCero: true }) } : {}),
  });

const VACIO = { nombre: "", unidad: "kg", grupo: "", minimo: "0", costo_unitario: "0", existencia_inicial: "0" };

function cuerpoDe(d, verCostos, nuevo) {
  return {
    nombre: d.nombre,
    unidad: d.unidad,
    grupo: d.grupo.trim() || null,
    minimo: d.minimo || "0",
    ...(verCostos ? { costo_unitario: d.costo_unitario || "0" } : {}),
    ...(nuevo ? { existencia_inicial: d.existencia_inicial || "0" } : {}),
  };
}

function CamposInsumo({ f, nuevo, grupos }) {
  const { puede } = useAuth();
  const idGrupos = useId();
  const unidad = f.form.unidad;
  return (
    <>
      <Seccion titulo="Datos del insumo" descripcion="Los campos marcados con * son obligatorios.">
        <Input etiqueta="Nombre" {...f.props("nombre")} permitir="carta" maxLength={100} autoComplete="off" ayuda="Como lo compras: Arroz, Queso mozzarella, Gaseosa 400 ml" />
        <div className="fila-campos">
          <Select etiqueta="Unidad" {...f.props("unidad")} ayuda="Se puede comprar en kg y gastar en g (misma familia)">
            {UNIDADES.map((u) => (
              <option key={u.valor} value={u.valor}>
                {u.etiqueta}
              </option>
            ))}
          </Select>
          <Input etiqueta="Grupo" {...f.props("grupo", { requerido: false })} permitir="carta" maxLength={40} list={idGrupos} ayuda="Carnes, Lácteos, Verduras… (opcional)" />
          <datalist id={idGrupos}>
            {(grupos ?? []).map((g) => (
              <option key={g} value={g} />
            ))}
          </datalist>
        </div>
      </Seccion>
      <Seccion titulo="Existencia y costo">
        <div className="fila-campos">
          <Input
            etiqueta={`Mínimo (${unidad})`}
            {...f.props("minimo")}
            permitir="cantidad"
            cifra
            ayuda="Por debajo de esto se avisa que hay que comprar"
          />
          {puede("costos", "ver") && (
            <Input
              etiqueta={`Costo unitario ($ ${porUnidad(unidad)})`}
              {...f.props("costo_unitario")}
              permitir="costo"
              cifra
              ayuda="Las compras lo recalculan con el promedio ponderado"
            />
          )}
        </div>
        {nuevo && (
          <div className="fila-campos">
            <Input
              etiqueta={`Existencia inicial (${unidad})`}
              {...f.props("existencia_inicial")}
              permitir="cantidad"
              cifra
              ayuda="Lo que hay hoy en la bodega. Queda como movimiento «Existencia inicial»."
            />
          </div>
        )}
      </Seccion>
    </>
  );
}

export function InsumoNuevo() {
  const { puede } = useAuth();
  const { data: grupos } = useApiResource("/inventario/grupos");
  const esquema = useMemo(() => esquemaInsumo(true), []);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Insumo creado", accion: "crear el insumo" });
  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo insumo" migas={migas({ etiqueta: "Nuevo insumo" })} />
      <FormularioPantalla
        id="form-insumo"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, cuerpoDe(d, puede("costos", "ver"), true)))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposInsumo f={f} nuevo grupos={grupos} />
      </FormularioPantalla>
    </div>
  );
}

export function InsumoEditar() {
  const { id } = useParams();
  const { puede } = useAuth();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const { data: grupos } = useApiResource("/inventario/grupos");
  const esquema = useMemo(() => esquemaInsumo(false), []);
  const f = useFormulario(esquema, VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el insumo" });
  useEffect(() => {
    if (data) {
      f.reiniciar({
        nombre: data.nombre,
        unidad: data.unidad,
        grupo: data.grupo ?? "",
        minimo: String(Number(data.minimo)),
        costo_unitario: data.costo_unitario == null ? "0" : String(Number(data.costo_unitario)),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar ${data.nombre}` : "Editar insumo"}
      migas={migas({ etiqueta: data?.nombre ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-insumo"
        onSubmit={(e) => guardar(e, (d) => api.put(`${URL}/${id}`, cuerpoDe(d, puede("costos", "ver"), false)))}
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposInsumo f={f} grupos={grupos} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

// =====================================================================
// Detalle con historial
// =====================================================================
export function enlaceDeDocumento(m) {
  if (m.documento_tipo === "compra") return `/inventario/compras/${m.documento_id}`;
  if (m.documento_tipo === "venta") return `/ventas/${m.documento_id}`;
  return null;
}

function Movimientos({ insumo }) {
  const { puede } = useAuth();
  const listado = useListadoPaginado(`${URL}/${insumo.id}/movimientos`, { porPagina: 15 });
  const columnas = [
    { clave: "created_at", titulo: "Fecha", ajustar: true, render: (m) => formatearFechaHora(m.created_at) },
    {
      clave: "tipo",
      titulo: "Movimiento",
      ajustar: true,
      render: (m) => {
        const t = TIPOS_MOVIMIENTO[m.tipo] ?? { etiqueta: m.tipo, variante: "neutro" };
        return <Badge variante={t.variante}>{t.etiqueta}</Badge>;
      },
    },
    {
      clave: "cantidad",
      titulo: "Cantidad",
      cifra: true,
      render: (m) => `${Number(m.cantidad) > 0 ? "+" : "−"}${legible(Math.abs(Number(m.cantidad)), insumo.unidad)}`,
    },
    { clave: "existencia_resultante", titulo: "Queda", cifra: true, render: (m) => legible(m.existencia_resultante, insumo.unidad) },
    ...(puede("costos", "ver") ? [{ clave: "valor", titulo: "Valor a costo", cifra: true, render: (m) => formatearMoneda(m.valor) }] : []),
    {
      clave: "documento_codigo",
      titulo: "Documento",
      render: (m) => {
        const ruta = enlaceDeDocumento(m);
        if (!m.documento_codigo) return m.motivo ?? "—";
        return ruta ? (
          <Link to={ruta} className="enlace cifra">
            {m.documento_codigo}
          </Link>
        ) : (
          <span className="cifra">{m.documento_codigo}</span>
        );
      },
    },
    { clave: "usuario_nombre", titulo: "Quién", render: (m) => m.usuario_nombre || "—" },
  ];
  return (
    <TablaRecurso
      exportar={`movimientos-${insumo.nombre}`}
      listado={listado}
      columnas={columnas}
      titulo="Movimientos"
      descripcion="Cada entrada y salida, de la más reciente a la más antigua. Su suma es la existencia actual."
      placeholderBusqueda="Buscar por documento o motivo…"
      vacio="Sin movimientos todavía: la existencia entra con una compra o con la existencia inicial."
    />
  );
}

export function InsumoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const { data: platos } = useApiResource(data ? `/catalogo/productos?insumo_id=${id}&por_pagina=100` : null);
  const [dialogo, setDialogo] = useState(null);
  const verCostos = puede("costos", "ver");

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data?.nombre ?? "Insumo"}
      descripcion={data ? `Se lleva en ${data.unidad}${data.grupo ? ` · ${data.grupo}` : ""}` : undefined}
      migas={migas({ etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("insumos", "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogo("estado")}>
              <Power size={14} aria-hidden="true" /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede("insumos", "eliminar") && (
            <Button variante="terciario" onClick={() => setDialogo("eliminar")}>
              <Trash2 size={14} aria-hidden="true" /> Eliminar
            </Button>
          )}
          {puede("insumos", "editar") && (
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
            <Card titulo="Datos del insumo">
              <Detalle
                campos={[
                  { etiqueta: "Nombre", valor: data.nombre },
                  { etiqueta: "Grupo", valor: data.grupo },
                  { etiqueta: "Unidad", valor: UNIDADES.find((u) => u.valor === data.unidad)?.etiqueta ?? data.unidad },
                  { etiqueta: "Mínimo", valor: Number(data.minimo) > 0 ? legible(data.minimo, data.unidad) : "Sin mínimo", cifra: true },
                  ...(verCostos
                    ? [
                        { etiqueta: "Costo unitario", valor: `${formatearMoneda(data.costo_unitario)} ${porUnidad(data.unidad)}`, cifra: true },
                        { etiqueta: "Costo total", valor: formatearMoneda(data.costo_total), cifra: true },
                      ]
                    : []),
                  { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
                  { etiqueta: "Creado", valor: formatearFecha(data.created_at) },
                ]}
              />
            </Card>
            <div className="space-y-4">
              <Card titulo="Existencia" descripcion="Solo lectura: la mueven compras, ventas, mermas y conteos.">
                <p className="dato-grande cifra">{legible(data.existencia, data.unidad)}</p>
                <p className="text-[12px] text-[var(--texto-terciario)] mt-1">
                  {data.bajo_minimo ? `▼ Bajo el mínimo de ${legible(data.minimo, data.unidad)}: conviene comprar.` : "Por encima del mínimo."}
                </p>
              </Card>
              <Card titulo="Proveedores" descripcion="Quiénes lo surten.">
                {data.proveedores?.length ? (
                  <ul className="fichas" style={{ marginTop: 0 }}>
                    {data.proveedores.map((p) => (
                      <li key={p.id} className="ficha">
                        <Link to={`/inventario/proveedores/${p.id}`} className="enlace">
                          {p.nombre}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[13px] text-[var(--texto-terciario)]">Ningún proveedor lo tiene registrado todavía.</p>
                )}
              </Card>
            </div>
          </div>
          <Card titulo="Platos que lo usan" descripcion="Si sube su costo, el costo de estos platos se recalcula solo.">
            <Table
              columnas={[
                {
                  clave: "nombre",
                  titulo: "Plato",
                  render: (p) => (
                    <Link to={`/carta/${p.id}`} className="enlace">
                      {p.nombre}
                    </Link>
                  ),
                },
                {
                  clave: "cantidad",
                  titulo: "Por porción",
                  cifra: true,
                  render: (p) => {
                    const l = p.receta.find((r) => r.insumo_id === id);
                    return l ? legible(l.cantidad, l.unidad) : "—";
                  },
                },
                ...(verCostos
                  ? [{ clave: "porcentaje_costo", titulo: "% de costo del plato", cifra: true, render: (p) => (p.porcentaje_costo == null ? "—" : `${formatearNumero(p.porcentaje_costo)} %`) }]
                  : []),
              ]}
              filas={platos?.items ?? []}
              vacio="Ninguna receta lo usa todavía."
            />
          </Card>
          <Movimientos insumo={data} />
        </div>
      )}
      <ModalEstado
        insumo={data}
        abierto={dialogo === "estado"}
        onCerrar={() => setDialogo(null)}
        onConfirmar={async () => {
          await api.patch(`${URL}/${id}/estado`, { activo: !data.activo });
          recargar();
        }}
      />
      <ModalEliminar
        insumo={data}
        abierto={dialogo === "eliminar"}
        onCerrar={() => setDialogo(null)}
        onConfirmar={async () => {
          await api.delete(`${URL}/${id}`);
          navigate(RUTA);
        }}
      />
    </PantallaDetalle>
  );
}
