import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { Eye, Pencil, Plus, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import { api } from "@/lib/api";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { formatearFecha, formatearNumero } from "@/lib/formato";
import { useAuth } from "@/context/AuthContext";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";
import { AccionesFila, Badge, BotonAccion, Button, Card, Detalle, Input, ModalConfirmar, PageHeader, Table, TablaRecurso, Textarea } from "@/components/ui";

const RUTA = "/seguridad/roles";
const URL = "/seguridad/roles";
const FORM_VACIO = { nombre: "", descripcion: "", permisos: {} };
const ESQUEMA = z.object({
  nombre: esquemas.nombreItem(100),
  descripcion: esquemas.descripcion(255),
  permisos: z.record(z.string(), z.array(z.string())),
});

const migas = (...resto) => migasDe(MIGAS.roles, ...resto);

/**
 * Matriz módulo × acción; `permisos` es {modulo: [acciones]}. Filas y
 * columnas salen del catálogo del backend (GET /seguridad/permisos): cada
 * módulo trae SOLO sus acciones, y donde una acción no existe (editar una
 * venta, eliminar un pedido) la celda dice "No aplica" en vez de una casilla
 * que el backend rechazaría. Usa la tabla compartida del sistema.
 */
function MatrizPermisos({ modulos, acciones, permisos, onCambiar, soloLectura = false }) {
  const tiene = (m, a) => (permisos[m.clave] ?? []).includes(a);

  function alternar(m, a) {
    const actuales = new Set(permisos[m.clave] ?? []);
    if (actuales.has(a)) actuales.delete(a);
    else actuales.add(a);
    const nuevo = { ...permisos };
    if (actuales.size) nuevo[m.clave] = m.acciones.filter((x) => actuales.has(x));
    else delete nuevo[m.clave];
    onCambiar(nuevo);
  }

  function alternarModulo(m) {
    const todo = m.acciones.every((a) => tiene(m, a));
    const nuevo = { ...permisos };
    if (todo) delete nuevo[m.clave];
    else nuevo[m.clave] = [...m.acciones];
    onCambiar(nuevo);
  }

  const casilla = (m, a, marcada, alCambiar, etiqueta) =>
    soloLectura ? (
      marcada ? (
        <span className="text-[var(--positivo-texto)]" aria-label={`${etiqueta}: sí`}>
          ✓
        </span>
      ) : (
        <span className="text-[var(--texto-terciario)]" aria-label={`${etiqueta}: no`}>
          —
        </span>
      )
    ) : (
      <label className="checkbox justify-center">
        <input type="checkbox" checked={marcada} onChange={alCambiar} aria-label={etiqueta} />
      </label>
    );

  const columnas = [
    { clave: "modulo", titulo: "Módulo", render: (m) => m.nombre },
    ...acciones.map((a) => ({
      clave: a.clave,
      titulo: a.nombre,
      ajustar: true,
      render: (m) =>
        m.acciones.includes(a.clave) ? (
          casilla(m, a.clave, tiene(m, a.clave), () => alternar(m, a.clave), `${m.nombre}: ${a.nombre}`)
        ) : (
          <span className="matriz-no-aplica" title={`${m.nombre} no tiene la acción ${a.nombre}`}>
            No aplica
          </span>
        ),
    })),
    ...(soloLectura
      ? []
      : [
          {
            clave: "todo",
            titulo: "Todo",
            ajustar: true,
            render: (m) =>
              casilla(m, "todo", m.acciones.every((a) => tiene(m, a)), () => alternarModulo(m), `${m.nombre}: todos los permisos`),
          },
        ]),
  ];

  return <Table columnas={columnas} filas={modulos} idFila={(m) => m.clave} vacio="Cargando módulos..." />;
}

/** Catálogo de módulos y acciones que el backend reconoce. */
function useCatalogoPermisos() {
  const { data } = useApiResource("/seguridad/permisos");
  const modulos = useMemo(() => data?.modulos ?? [], [data]);
  const nombres = useMemo(() => Object.fromEntries(modulos.map((m) => [m.clave, m.nombre])), [modulos]);
  return { modulos, acciones: data?.acciones ?? [], nombres };
}

function resumenPermisos(rol, nombres) {
  if (rol.es_administrador) return <Badge variante="positivo">Acceso total</Badge>;
  const claves = Object.keys(rol.permisos ?? {});
  if (!claves.length) return <span className="text-[var(--texto-terciario)]">Sin permisos</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {claves.map((m) => (
        <Badge key={m} variante="neutro">
          {nombres[m] ?? m} · {rol.permisos[m].length}
        </Badge>
      ))}
    </span>
  );
}

/** Nota que reemplaza a la matriz en el rol Administrador. */
function NotaAdministrador() {
  return (
    <p className="text-[13px] text-[var(--texto-secundario)]">
      El rol Administrador tiene siempre <strong>acceso total</strong> a todos los módulos. Sus permisos no se editan y el
      rol no se puede eliminar: así la empresa nunca se queda sin alguien que la gestione.
    </p>
  );
}

function ModalEliminarRol({ rol, abierto, onCerrar, onConfirmar }) {
  return (
    <ModalConfirmar
      abierto={abierto}
      onCerrar={onCerrar}
      destructivo
      titulo="Eliminar rol"
      textoConfirmar="Eliminar"
      mensaje={`¿Eliminar el rol "${rol?.nombre}"? Esta acción no se puede deshacer.`}
      accion={`eliminar el rol ${rol?.nombre ?? ""}`.trim()}
      mensajeExito={`Rol ${rol?.nombre} eliminado`}
      onConfirmar={onConfirmar}
    >
      {rol?.usuarios_count > 0 && (
        <p className="text-[var(--advertencia-texto)]">Tiene {rol.usuarios_count} usuario(s) asignado(s): el sistema bloqueará la eliminación hasta que los reasignes.</p>
      )}
    </ModalConfirmar>
  );
}

export function RolesLista() {
  const navigate = useNavigate();
  const listado = useListadoPaginado(URL);
  const [registro, setRegistro] = useState(null);
  const { puede, esAdministrador, usuario } = useAuth();
  const { nombres } = useCatalogoPermisos();
  // Solo un administrador edita el rol Administrador; nadie más edita el suyo.
  const noEditable = (r) => (r.es_administrador ? !esAdministrador : !esAdministrador && r.id === usuario?.rol_id);

  const columnas = [
    {
      clave: "nombre",
      titulo: "Rol",
      render: (r) => (
        <Link to={`${RUTA}/${r.id}`} className="enlace">
          {r.nombre}
        </Link>
      ),
    },
    { clave: "descripcion", titulo: "Descripción", render: (r) => r.descripcion || "—" },
    { clave: "permisos", titulo: "Permisos", render: (r) => resumenPermisos(r, nombres) },
    { clave: "usuarios_count", titulo: "Usuarios", cifra: true, render: (r) => formatearNumero(r.usuarios_count ?? 0) },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (r) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${RUTA}/${r.id}`)} />
          {puede("roles", "editar") && (
            <BotonAccion
              icono={Pencil}
              etiqueta="Editar"
              titulo={noEditable(r) ? "Solo un administrador puede editar este rol" : "Editar"}
              disabled={noEditable(r)}
              onClick={() => navigate(`${RUTA}/${r.id}/editar`)}
            />
          )}
          {puede("roles", "eliminar") && (
            <BotonAccion
              icono={Trash2}
              etiqueta="Eliminar"
              titulo={r.es_administrador ? "El rol Administrador no se puede eliminar" : "Eliminar"}
              disabled={r.es_administrador}
              onClick={() => setRegistro(r)}
            />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Roles"
        descripcion="Perfiles de acceso: qué puede hacer cada rol en cada módulo."
        migas={migas()}
        acciones={
          puede("roles", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Nuevo rol
            </Button>
          )
        }
      />

      <TablaRecurso exportar="roles" listado={listado} columnas={columnas} placeholderBusqueda="Buscar por nombre o descripción..." vacio="Aún no hay roles configurados." />

      <ModalEliminarRol
        rol={registro}
        abierto={registro !== null}
        onCerrar={() => setRegistro(null)}
        onConfirmar={async () => {
          await api.delete(`${URL}/${registro.id}`);
          listado.recargar();
        }}
      />
    </div>
  );
}

function CamposRol({ f, modulos, acciones, esAdministrador = false }) {
  return (
    <>
      <Seccion titulo="Datos del rol" descripcion="Los campos marcados con * son obligatorios.">
        <Input etiqueta="Nombre del rol" {...f.props("nombre")} permitir="nombre" maxLength={100} autoComplete="off" />
        <Textarea etiqueta="Descripción" {...f.props("descripcion", { requerido: false })} ayuda="Opcional" maxLength={255} />
      </Seccion>
      <Seccion titulo="Permisos por módulo" descripcion="Marca qué acciones puede hacer este rol en cada módulo.">
        {esAdministrador ? (
          <NotaAdministrador />
        ) : (
          <MatrizPermisos
            modulos={modulos}
            acciones={acciones}
            permisos={f.form.permisos}
            onCambiar={(permisos) => f.setForm((prev) => ({ ...prev, permisos }))}
          />
        )}
      </Seccion>
    </>
  );
}

export function RolNuevo() {
  const { modulos, acciones } = useCatalogoPermisos();
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Rol creado", accion: "crear el rol" });

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo rol" descripcion="Nombre y permisos por módulo." migas={migas({ etiqueta: "Nuevo rol" })} />
      <FormularioPantalla
        id="form-rol"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, { nombre: d.nombre, descripcion: d.descripcion || null, permisos: d.permisos }))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposRol f={f} modulos={modulos} acciones={acciones} />
      </FormularioPantalla>
    </div>
  );
}

export function RolEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const { modulos, acciones } = useCatalogoPermisos();
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el rol" });

  useEffect(() => {
    if (data) f.reiniciar({ nombre: data.nombre, descripcion: data.descripcion ?? "", permisos: data.permisos ?? {} });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar rol ${data.nombre}` : "Editar rol"}
      migas={migas({ etiqueta: data?.nombre ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-rol"
        onSubmit={(e) =>
          guardar(e, (d) =>
            api.put(`${URL}/${id}`, {
              nombre: d.nombre,
              descripcion: d.descripcion || null,
              // El Administrador tiene acceso total: sus permisos no se envían.
              ...(data?.es_administrador ? {} : { permisos: d.permisos }),
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
        <CamposRol f={f} modulos={modulos} acciones={acciones} esAdministrador={Boolean(data?.es_administrador)} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function RolDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const { modulos, acciones } = useCatalogoPermisos();
  const [eliminar, setEliminar] = useState(false);
  const { puede, esAdministrador, usuario } = useAuth();
  const noEditable = data ? (data.es_administrador ? !esAdministrador : !esAdministrador && data.id === usuario?.rol_id) : false;

  return (
    <PantallaDetalle estrecha
      volver={RUTA}
      titulo={data?.nombre ?? "Detalle del rol"}
      descripcion={data?.descripcion ?? undefined}
      migas={migas({ etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("roles", "eliminar") && !data?.es_administrador && (
            <Button variante="terciario" onClick={() => setEliminar(true)}>
              <Trash2 size={14} /> Eliminar
            </Button>
          )}
          {puede("roles", "editar") && (
            <Button
              onClick={() => navigate(`${RUTA}/${id}/editar`)}
              disabled={noEditable}
              title={noEditable ? "Solo un administrador puede editar este rol" : undefined}
            >
              <Pencil size={14} /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <div className="space-y-4">
          <Card titulo="Datos del rol">
            <Detalle
              campos={[
                { etiqueta: "Nombre", valor: data.nombre },
                { etiqueta: "Usuarios asignados", valor: formatearNumero(data.usuarios_count ?? 0), cifra: true },
                { etiqueta: "Descripción", valor: data.descripcion },
                { etiqueta: "Creado", valor: formatearFecha(data.created_at) },
              ]}
            />
          </Card>
          <Card titulo="Permisos por módulo">
            {data.es_administrador ? (
              <NotaAdministrador />
            ) : (
              <MatrizPermisos modulos={modulos} acciones={acciones} permisos={data.permisos ?? {}} soloLectura />
            )}
          </Card>
        </div>
      )}

      <ModalEliminarRol
        rol={data}
        abierto={eliminar}
        onCerrar={() => setEliminar(false)}
        onConfirmar={async () => {
          await api.delete(`${URL}/${id}`);
          navigate(RUTA);
        }}
      />
    </PantallaDetalle>
  );
}
