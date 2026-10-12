import { useEffect, useMemo, useState } from "react";
import { Eye, LayoutGrid, Map as IconoMapa, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import {
  AccionesFila,
  BotonAccion,
  Button,
  Card,
  Detalle,
  EstadoBadge,
  Input,
  ModalConfirmar,
  PageHeader,
  Select,
  TablaRecurso,
} from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useCatalogo } from "@/hooks/useCatalogo";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { api } from "@/lib/api";
import { formatearFecha, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";

import "./ajustes.css";

/**
 * MESAS Y ZONAS (2026-10-12). Las mesas activas son las que el mesero ve en
 * la cuadrícula "¿Para qué mesa?"; una mesa con historial no se borra, se
 * desactiva. Las zonas ("Salón", "Terraza") agrupan las mesas y ordenan la
 * cuadrícula. Las dos usan el permiso "mesas".
 */
const RUTA_MESAS = "/ajustes/mesas";
const RUTA_ZONAS = "/ajustes/zonas";
const URL_MESAS = "/ajustes/mesas";
const URL_ZONAS = "/ajustes/zonas";

// =====================================================================
// Mesas
// =====================================================================
const ESQUEMA_MESA = z.object({
  nombre: esquemas.mesa(),
  zona_id: z.string(),
  puestos: esquemas.entero(1, 30),
});
const MESA_VACIA = { nombre: "", zona_id: "", puestos: "4" };
const cuerpoMesa = (d) => ({ nombre: d.nombre, zona_id: d.zona_id || null, puestos: Number(d.puestos) });

export function MesasLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [zona, setZona] = useState("");
  const [estado, setEstado] = useState("");
  const { items: zonas } = useCatalogo(URL_ZONAS, { soloActivos: false });
  const filtros = { ...(zona ? { zona_id: zona } : {}), ...(estado ? { activo: estado === "activo" } : {}) };
  const listado = useListadoPaginado(URL_MESAS, { filtros, porPagina: 20 });
  const [dialogo, setDialogo] = useState(null);
  const mesa = dialogo?.mesa;

  const columnas = [
    {
      clave: "nombre",
      titulo: "Mesa",
      cifra: true,
      render: (m) => (
        <Link to={`${RUTA_MESAS}/${m.id}`} className="enlace">
          {m.nombre}
        </Link>
      ),
    },
    { clave: "zona_nombre", titulo: "Zona", render: (m) => m.zona_nombre ?? "Sin zona" },
    { clave: "puestos", titulo: "Puestos", cifra: true, render: (m) => formatearNumero(m.puestos) },
    { clave: "activo", titulo: "Estado", ajustar: true, render: (m) => <EstadoBadge activo={m.activo} /> },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (m) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver la mesa ${m.nombre}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA_MESAS}/${m.id}`)} />
          {puede("mesas", "editar") && (
            <BotonAccion icono={Pencil} etiqueta={`Editar la mesa ${m.nombre}`} titulo="Editar" onClick={() => navigate(`${RUTA_MESAS}/${m.id}/editar`)} />
          )}
          {puede("mesas", "cambiar_estado") && (
            <BotonAccion
              icono={Power}
              etiqueta={`${m.activo ? "Desactivar" : "Activar"} la mesa ${m.nombre}`}
              titulo={m.activo ? "Desactivar" : "Activar"}
              onClick={() => setDialogo({ tipo: "estado", mesa: m })}
            />
          )}
          {puede("mesas", "eliminar") && (
            <BotonAccion icono={Trash2} etiqueta={`Eliminar la mesa ${m.nombre}`} titulo="Eliminar" onClick={() => setDialogo({ tipo: "eliminar", mesa: m })} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Mesas"
        descripcion="Las mesas activas aparecen en la cuadrícula «¿Para qué mesa?» al tomar un pedido."
        migas={migasDe(MIGAS.mesas)}
        acciones={
          <>
            <Button variante="terciario" onClick={() => navigate(RUTA_ZONAS)}>
              <IconoMapa size={14} aria-hidden="true" /> Zonas
            </Button>
            {puede("mesas", "crear") && (
              <Button onClick={() => navigate(`${RUTA_MESAS}/nuevo`)}>
                <Plus size={14} aria-hidden="true" /> Nueva mesa
              </Button>
            )}
          </>
        }
      />
      <TablaRecurso
        exportar="mesas"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar mesa…"
        vacio="Todavía no hay mesas: crea la primera para poder tomar órdenes en el local."
        filtros={
          <>
            <Select value={zona} onChange={(e) => setZona(e.target.value)} className="w-40" aria-label="Filtrar por zona">
              <option value="">Todas las zonas</option>
              {zonas.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.nombre}
                </option>
              ))}
            </Select>
            <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
              <option value="">Todos los estados</option>
              <option value="activo">Solo activas</option>
              <option value="inactivo">Solo inactivas</option>
            </Select>
          </>
        }
      />
      <DialogosMesa mesa={mesa} dialogo={dialogo?.tipo} onCerrar={() => setDialogo(null)} alTerminar={listado.recargar} />
    </div>
  );
}

function DialogosMesa({ mesa, dialogo, onCerrar, alTerminar }) {
  return (
    <>
      <ModalConfirmar
        abierto={dialogo === "estado"}
        onCerrar={onCerrar}
        titulo={mesa?.activo ? `Desactivar la mesa ${mesa?.nombre}` : `Activar la mesa ${mesa?.nombre ?? ""}`}
        textoConfirmar={mesa?.activo ? "Desactivar" : "Activar"}
        mensaje={
          mesa?.activo
            ? "Deja de aparecer en la cuadrícula del mesero; conserva su historial de órdenes."
            : "Vuelve a aparecer en la cuadrícula del mesero."
        }
        accion={`cambiar el estado de la mesa ${mesa?.nombre ?? ""}`.trim()}
        mensajeExito={`Mesa ${mesa?.nombre} ${mesa?.activo ? "desactivada" : "activada"}`}
        onConfirmar={async () => {
          await api.patch(`${URL_MESAS}/${mesa.id}/estado`, { activo: !mesa.activo });
          alTerminar();
        }}
      />
      <ModalConfirmar
        abierto={dialogo === "eliminar"}
        onCerrar={onCerrar}
        destructivo
        titulo={`Eliminar la mesa ${mesa?.nombre ?? ""}`}
        textoConfirmar="Eliminar"
        mensaje="Esta acción no se puede deshacer. Si la mesa ya tiene órdenes, el sistema lo bloqueará: desactívala en su lugar."
        accion={`eliminar la mesa ${mesa?.nombre ?? ""}`.trim()}
        mensajeExito={`Mesa ${mesa?.nombre} eliminada`}
        onConfirmar={async () => {
          await api.delete(`${URL_MESAS}/${mesa.id}`);
          alTerminar();
        }}
      />
    </>
  );
}

function CamposMesa({ f, zonas }) {
  return (
    <Seccion titulo="Datos de la mesa" descripcion="Los campos marcados con * son obligatorios.">
      <div className="fila-campos">
        <Input etiqueta="Nombre o número" {...f.props("nombre")} permitir="mesa" maxLength={20} cifra autoComplete="off" ayuda="Como la conoce el equipo: B2, 4, Terraza 3" />
        <Input etiqueta="Puestos" {...f.props("puestos")} permitir="entero" maxLength={2} cifra ayuda="Entre 1 y 30" />
      </div>
      <div className="fila-campos">
        <Select etiqueta="Zona" {...f.props("zona_id", { requerido: false })}>
          <option value="">Sin zona</option>
          {zonas.map((z) => (
            <option key={z.id} value={z.id}>
              {z.nombre}
            </option>
          ))}
        </Select>
      </div>
    </Seccion>
  );
}

export function MesaNueva() {
  const { items: zonas } = useCatalogo(URL_ZONAS, { soloActivos: false });
  const esquema = useMemo(() => ESQUEMA_MESA, []);
  const f = useFormulario(esquema, MESA_VACIA);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA_MESAS, mensaje: "Mesa creada", accion: "crear la mesa" });
  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA_MESAS} titulo="Nueva mesa" migas={migasDe(MIGAS.mesas, { etiqueta: "Nueva mesa" })} />
      <FormularioPantalla
        id="form-mesa"
        onSubmit={(e) => guardar(e, (d) => api.post(URL_MESAS, cuerpoMesa(d)))}
        volver={RUTA_MESAS}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposMesa f={f} zonas={zonas} />
      </FormularioPantalla>
    </div>
  );
}

export function MesaEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL_MESAS}/${id}`);
  const { items: zonas } = useCatalogo(URL_ZONAS, { soloActivos: false });
  const esquema = useMemo(() => ESQUEMA_MESA, []);
  const f = useFormulario(esquema, MESA_VACIA);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: `${RUTA_MESAS}/${id}`,
    mensaje: "Cambios guardados",
    accion: "guardar la mesa",
  });
  useEffect(() => {
    if (data) f.reiniciar({ nombre: data.nombre, zona_id: data.zona_id ?? "", puestos: String(data.puestos) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <PantallaDetalle
      estrecha
      volver={RUTA_MESAS}
      titulo={data ? `Editar mesa ${data.nombre}` : "Editar mesa"}
      migas={migasDe(MIGAS.mesas, { etiqueta: data?.nombre ?? "…", a: `${RUTA_MESAS}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-mesa"
        onSubmit={(e) => guardar(e, (d) => api.put(`${URL_MESAS}/${id}`, cuerpoMesa(d)))}
        volver={`${RUTA_MESAS}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposMesa f={f} zonas={zonas} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function MesaDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL_MESAS}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  return (
    <PantallaDetalle
      volver={RUTA_MESAS}
      titulo={data ? `Mesa ${data.nombre}` : "Mesa"}
      descripcion={data?.zona_nombre ? `Zona ${data.zona_nombre}` : undefined}
      migas={migasDe(MIGAS.mesas, { etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("mesas", "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogo("estado")}>
              <Power size={14} aria-hidden="true" /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede("mesas", "eliminar") && (
            <Button variante="terciario" onClick={() => setDialogo("eliminar")}>
              <Trash2 size={14} aria-hidden="true" /> Eliminar
            </Button>
          )}
          {puede("mesas", "editar") && (
            <Button onClick={() => navigate(`${RUTA_MESAS}/${id}/editar`)}>
              <Pencil size={14} aria-hidden="true" /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <Card titulo="Datos de la mesa">
          <Detalle
            campos={[
              { etiqueta: "Mesa", valor: data.nombre, cifra: true },
              { etiqueta: "Zona", valor: data.zona_nombre ?? "Sin zona" },
              { etiqueta: "Puestos", valor: formatearNumero(data.puestos), cifra: true },
              { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
              { etiqueta: "Creada", valor: formatearFecha(data.created_at) },
            ]}
          />
        </Card>
      )}
      <DialogosMesa
        mesa={data}
        dialogo={dialogo}
        onCerrar={() => setDialogo(null)}
        alTerminar={dialogo === "eliminar" ? () => navigate(RUTA_MESAS) : recargar}
      />
    </PantallaDetalle>
  );
}

// =====================================================================
// Zonas
// =====================================================================
const ESQUEMA_ZONA = z.object({ nombre: esquemas.nombreCarta(40), orden: esquemas.entero(0, 999) });
const ZONA_VACIA = { nombre: "", orden: "0" };
const cuerpoZona = (d) => ({ nombre: d.nombre, orden: Number(d.orden) });
const migasZonas = (...resto) => migasDe(MIGAS.zonas, ...resto);

export function ZonasLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const listado = useListadoPaginado(URL_ZONAS, { porPagina: 20 });
  const [eliminar, setEliminar] = useState(null);

  const columnas = [
    {
      clave: "nombre",
      titulo: "Zona",
      render: (z) => (
        <Link to={`${RUTA_ZONAS}/${z.id}`} className="enlace">
          {z.nombre}
        </Link>
      ),
    },
    { clave: "orden", titulo: "Orden", cifra: true, render: (z) => formatearNumero(z.orden) },
    { clave: "mesas_count", titulo: "Mesas", cifra: true, render: (z) => formatearNumero(z.mesas_count) },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (z) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta={`Ver la zona ${z.nombre}`} titulo="Ver detalle" onClick={() => navigate(`${RUTA_ZONAS}/${z.id}`)} />
          {puede("mesas", "editar") && (
            <BotonAccion icono={Pencil} etiqueta={`Editar la zona ${z.nombre}`} titulo="Editar" onClick={() => navigate(`${RUTA_ZONAS}/${z.id}/editar`)} />
          )}
          {puede("mesas", "eliminar") && (
            <BotonAccion icono={Trash2} etiqueta={`Eliminar la zona ${z.nombre}`} titulo="Eliminar" onClick={() => setEliminar(z)} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        volver={RUTA_MESAS}
        titulo="Zonas"
        descripcion="Áreas del local que agrupan las mesas; el orden define cómo se ven en la cuadrícula."
        migas={migasZonas()}
        acciones={
          <>
            <Button variante="terciario" onClick={() => navigate(RUTA_MESAS)}>
              <LayoutGrid size={14} aria-hidden="true" /> Mesas
            </Button>
            {puede("mesas", "crear") && (
              <Button onClick={() => navigate(`${RUTA_ZONAS}/nuevo`)}>
                <Plus size={14} aria-hidden="true" /> Nueva zona
              </Button>
            )}
          </>
        }
      />
      <TablaRecurso
        exportar="zonas"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar zona…"
        vacio="Sin zonas: las mesas se muestran todas juntas."
      />
      <ModalConfirmar
        abierto={Boolean(eliminar)}
        onCerrar={() => setEliminar(null)}
        destructivo
        titulo={`Eliminar la zona ${eliminar?.nombre ?? ""}`}
        textoConfirmar="Eliminar"
        mensaje="Esta acción no se puede deshacer."
        accion={`eliminar la zona ${eliminar?.nombre ?? ""}`.trim()}
        mensajeExito={`Zona ${eliminar?.nombre} eliminada`}
        onConfirmar={async () => {
          await api.delete(`${URL_ZONAS}/${eliminar.id}`);
          listado.recargar();
        }}
      >
        {eliminar?.mesas_count > 0 && (
          <p className="text-[var(--advertencia-texto)]">
            Tiene {eliminar.mesas_count} mesa(s): el sistema bloqueará la eliminación. Pásalas a otra zona primero.
          </p>
        )}
      </ModalConfirmar>
    </div>
  );
}

function CamposZona({ f }) {
  return (
    <Seccion titulo="Datos de la zona" descripcion="Los campos marcados con * son obligatorios.">
      <div className="fila-campos">
        <Input etiqueta="Nombre" {...f.props("nombre")} permitir="carta" maxLength={40} autoComplete="off" ayuda="Salón, Terraza, Segundo piso…" />
        <Input etiqueta="Orden" {...f.props("orden")} permitir="entero" maxLength={3} cifra ayuda="Menor primero en la cuadrícula" />
      </div>
    </Seccion>
  );
}

export function ZonaNueva() {
  const esquema = useMemo(() => ESQUEMA_ZONA, []);
  const f = useFormulario(esquema, ZONA_VACIA);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA_ZONAS, mensaje: "Zona creada", accion: "crear la zona" });
  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA_ZONAS} titulo="Nueva zona" migas={migasZonas({ etiqueta: "Nueva zona" })} />
      <FormularioPantalla
        id="form-zona"
        onSubmit={(e) => guardar(e, (d) => api.post(URL_ZONAS, cuerpoZona(d)))}
        volver={RUTA_ZONAS}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposZona f={f} />
      </FormularioPantalla>
    </div>
  );
}

export function ZonaEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL_ZONAS}/${id}`);
  const esquema = useMemo(() => ESQUEMA_ZONA, []);
  const f = useFormulario(esquema, ZONA_VACIA);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA_ZONAS}/${id}`, mensaje: "Cambios guardados", accion: "guardar la zona" });
  useEffect(() => {
    if (data) f.reiniciar({ nombre: data.nombre, orden: String(data.orden) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <PantallaDetalle
      estrecha
      volver={RUTA_ZONAS}
      titulo={data ? `Editar ${data.nombre}` : "Editar zona"}
      migas={migasZonas({ etiqueta: data?.nombre ?? "…", a: `${RUTA_ZONAS}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-zona"
        onSubmit={(e) => guardar(e, (d) => api.put(`${URL_ZONAS}/${id}`, cuerpoZona(d)))}
        volver={`${RUTA_ZONAS}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposZona f={f} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function ZonaDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puede } = useAuth();
  const { data, error } = useApiResource(`${URL_ZONAS}/${id}`);
  const [eliminar, setEliminar] = useState(false);
  return (
    <PantallaDetalle
      volver={RUTA_ZONAS}
      titulo={data?.nombre ?? "Zona"}
      migas={migasZonas({ etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("mesas", "eliminar") && (
            <Button variante="terciario" onClick={() => setEliminar(true)}>
              <Trash2 size={14} aria-hidden="true" /> Eliminar
            </Button>
          )}
          {puede("mesas", "editar") && (
            <Button onClick={() => navigate(`${RUTA_ZONAS}/${id}/editar`)}>
              <Pencil size={14} aria-hidden="true" /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <Card titulo="Datos de la zona">
          <Detalle
            campos={[
              { etiqueta: "Zona", valor: data.nombre },
              { etiqueta: "Orden", valor: formatearNumero(data.orden), cifra: true },
              {
                etiqueta: "Mesas",
                valor: data.mesas_count ? (
                  <Link className="enlace" to={RUTA_MESAS}>
                    {formatearNumero(data.mesas_count)} mesa(s)
                  </Link>
                ) : (
                  "Ninguna"
                ),
              },
              { etiqueta: "Creada", valor: formatearFecha(data.created_at) },
            ]}
          />
        </Card>
      )}
      <ModalConfirmar
        abierto={eliminar}
        onCerrar={() => setEliminar(false)}
        destructivo
        titulo={`Eliminar la zona ${data?.nombre ?? ""}`}
        textoConfirmar="Eliminar"
        mensaje="Esta acción no se puede deshacer."
        accion={`eliminar la zona ${data?.nombre ?? ""}`.trim()}
        mensajeExito={`Zona ${data?.nombre} eliminada`}
        onConfirmar={async () => {
          await api.delete(`${URL_ZONAS}/${id}`);
          navigate(RUTA_ZONAS);
        }}
      />
    </PantallaDetalle>
  );
}
