import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { Eye, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useCatalogo } from "@/hooks/useCatalogo";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { formatearFecha } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";
import { AccionesFila, BotonAccion, Button, Card, Detalle, EstadoBadge, Input, ModalConfirmar, PageHeader, Select, TablaRecurso } from "@/components/ui";

const RUTA = "/seguridad/usuarios";
const URL = "/seguridad/usuarios";
const FORM_VACIO = { nombre_completo: "", email: "", password: "", rol_id: "" };

const esquemaUsuario = (esCreacion) =>
  z.object({
    nombre_completo: esquemas.nombrePersona(),
    email: esquemas.email(),
    password: z
      .string()
      .refine((s) => (esCreacion ? s.length >= 8 : s === "" || s.length >= 8), "Mínimo 8 caracteres")
      .refine((s) => s.length <= 72, "Máximo 72 caracteres"),
    rol_id: z.string().min(1, "Selecciona un rol"),
  });

const migas = (...resto) => migasDe(MIGAS.usuarios, ...resto);

function DialogosUsuario({ usuario, dialogo, onCerrar, onEstado, onEliminar }) {
  return (
    <>
      <ModalConfirmar
        abierto={dialogo === "estado"}
        onCerrar={onCerrar}
        titulo={usuario?.activo ? "Desactivar usuario" : "Activar usuario"}
        textoConfirmar={usuario?.activo ? "Desactivar" : "Activar"}
        mensaje={
          usuario?.activo
            ? `${usuario?.nombre_completo} no podrá iniciar sesión hasta que lo reactives.`
            : `${usuario?.nombre_completo} podrá volver a iniciar sesión.`
        }
        accion={`cambiar el estado de ${usuario?.nombre_completo ?? "el usuario"}`}
        mensajeExito={`${usuario?.nombre_completo} ${usuario?.activo ? "desactivado" : "activado"}`}
        onConfirmar={onEstado}
      />
      <ModalConfirmar
        abierto={dialogo === "eliminar"}
        onCerrar={onCerrar}
        destructivo
        titulo="Eliminar usuario"
        textoConfirmar="Eliminar"
        mensaje={`Se eliminará el acceso de ${usuario?.nombre_completo} (${usuario?.email}). Esta acción no se puede deshacer.`}
        accion={`eliminar a ${usuario?.nombre_completo ?? "el usuario"}`}
        mensajeExito={`${usuario?.nombre_completo} eliminado`}
        onConfirmar={onEliminar}
      />
    </>
  );
}

export function UsuariosLista() {
  const navigate = useNavigate();
  const { usuario: usuarioActual, puede, esAdministrador } = useAuth();
  // Solo un administrador toca a otro administrador (el backend lo exige igual).
  const bloqueado = (u) => u.rol_es_administrador && !esAdministrador;
  const [filtroEstado, setFiltroEstado] = useState("");
  const listado = useListadoPaginado(URL, { filtros: filtroEstado ? { activo: filtroEstado === "activo" } : {} });
  const [dialogo, setDialogo] = useState(null);
  const registro = dialogo?.registro;
  const esYo = (r) => r.id === usuarioActual?.id;

  const columnas = [
    {
      clave: "nombre_completo",
      titulo: "Nombre",
      render: (u) => (
        <span>
          <Link to={`${RUTA}/${u.id}`} className="enlace">
            {u.nombre_completo}
          </Link>
          {esYo(u) && <span className="ml-2 text-[11px] text-[var(--texto-terciario)]">(tú)</span>}
        </span>
      ),
    },
    { clave: "email", titulo: "Correo" },
    { clave: "rol_nombre", titulo: "Rol", render: (u) => u.rol_nombre ?? "—" },
    { clave: "activo", ajustar: true, titulo: "Estado", render: (u) => <EstadoBadge activo={u.activo} /> },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (u) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${RUTA}/${u.id}`)} />
          {puede("usuarios", "editar") && (
            <BotonAccion
              icono={Pencil}
              etiqueta="Editar"
              titulo={bloqueado(u) ? "Solo un administrador edita a otro administrador" : "Editar"}
              disabled={bloqueado(u)}
              onClick={() => navigate(`${RUTA}/${u.id}/editar`)}
            />
          )}
          {puede("usuarios", "cambiar_estado") && (
            <BotonAccion
              icono={Power}
              etiqueta={u.activo ? "Desactivar" : "Activar"}
              titulo={
                esYo(u)
                  ? "No puedes desactivarte"
                  : bloqueado(u)
                    ? "Solo un administrador cambia el estado de otro administrador"
                    : u.activo
                      ? "Desactivar"
                      : "Activar"
              }
              disabled={esYo(u) || bloqueado(u)}
              onClick={() => setDialogo({ tipo: "estado", registro: u })}
            />
          )}
          {puede("usuarios", "eliminar") && (
            <BotonAccion
              icono={Trash2}
              etiqueta="Eliminar"
              titulo={esYo(u) ? "No puedes eliminarte" : bloqueado(u) ? "Solo un administrador elimina a otro administrador" : "Eliminar"}
              disabled={esYo(u) || bloqueado(u)}
              onClick={() => setDialogo({ tipo: "eliminar", registro: u })}
            />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Usuarios"
        descripcion="Quién puede entrar al sistema y con qué rol."
        migas={migas()}
        acciones={
          puede("usuarios", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Nuevo usuario
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar="usuarios"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por nombre o correo..."
        vacio="Aún no hay usuarios registrados."
        filtros={
          <Select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            <option value="activo">Solo activos</option>
            <option value="inactivo">Solo inactivos</option>
          </Select>
        }
      />

      <DialogosUsuario
        usuario={registro}
        dialogo={dialogo?.tipo}
        onCerrar={() => setDialogo(null)}
        onEstado={async () => {
          await api.patch(`${URL}/${registro.id}/estado`, { activo: !registro.activo });
          listado.recargar();
        }}
        onEliminar={async () => {
          await api.delete(`${URL}/${registro.id}`);
          listado.recargar();
        }}
      />
    </div>
  );
}

function CamposUsuario({ f, roles, esCreacion }) {
  const { esAdministrador } = useAuth();
  // Solo un administrador puede asignar el rol Administrador: a los demás ni
  // se les ofrece (el backend responde 403 si lo intentan igual).
  const asignables = esAdministrador ? roles : roles.filter((r) => !r.es_administrador || r.id === f.form?.rol_id);
  return (
    <>
      <Seccion titulo="Datos de acceso" descripcion="Los campos marcados con * son obligatorios.">
        <Input etiqueta="Nombre completo" {...f.props("nombre_completo")} permitir="nombre" maxLength={80} autoComplete="off" ayuda="Solo letras, espacios, tildes y apóstrofes" />
        <div className="fila-campos">
          <Input etiqueta="Correo electrónico" {...f.props("email")} permitir="correo" maxLength={150} autoComplete="off" ayuda="Se guarda en minúsculas" />
          <Input
            etiqueta={esCreacion ? "Contraseña" : "Nueva contraseña"}
            type="password"
            {...f.props("password", { requerido: esCreacion })}
            ayuda={esCreacion ? "Mínimo 8 caracteres." : "Déjala vacía para no cambiarla."}
            autoComplete="new-password"
            maxLength={72}
          />
        </div>
      </Seccion>
      <Seccion titulo="Rol" descripcion="Define qué módulos y acciones puede usar.">
        <div className="fila-campos">
          <Select etiqueta="Rol" {...f.props("rol_id")}>
            <option value="">Selecciona un rol...</option>
            {asignables.map((r) => (
              <option key={r.id} value={r.id}>
                {r.nombre}
              </option>
            ))}
          </Select>
        </div>
      </Seccion>
    </>
  );
}

export function UsuarioNuevo() {
  const { items: roles } = useCatalogo("/seguridad/roles", { soloActivos: false });
  const esquema = useMemo(() => esquemaUsuario(true), []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Usuario creado", accion: "crear el usuario" });

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo usuario" descripcion="Datos de acceso y rol asignado." migas={migas({ etiqueta: "Nuevo usuario" })} />
      <FormularioPantalla
        id="form-usuario"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, d))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Crear usuario"
        errorGeneral={errorGeneral}
      >
        <CamposUsuario f={f} roles={roles} esCreacion />
      </FormularioPantalla>
    </div>
  );
}

export function UsuarioEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const { items: roles } = useCatalogo("/seguridad/roles", { soloActivos: false });
  const esquema = useMemo(() => esquemaUsuario(false), []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el usuario" });

  useEffect(() => {
    if (data) f.reiniciar({ nombre_completo: data.nombre_completo, email: data.email, password: "", rol_id: data.rol_id ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar ${data.nombre_completo}` : "Editar usuario"}
      migas={migas({ etiqueta: data?.nombre_completo ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-usuario"
        onSubmit={(e) =>
          guardar(e, (d) => {
            const datos = { nombre_completo: d.nombre_completo, email: d.email, rol_id: d.rol_id };
            if (d.password) datos.password = d.password;
            return api.put(`${URL}/${id}`, datos);
          })
        }
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposUsuario f={f} roles={roles} esCreacion={false} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function UsuarioDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { usuario: usuarioActual, puede, esAdministrador } = useAuth();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  const esYo = data?.id === usuarioActual?.id;
  const bloqueado = Boolean(data?.rol_es_administrador && !esAdministrador);
  const motivo = bloqueado ? "Solo un administrador modifica a otro administrador" : undefined;

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data?.nombre_completo ?? "Detalle del usuario"}
      descripcion={data ? `${data.email}${esYo ? " · tu cuenta" : ""}` : undefined}
      migas={migas({ etiqueta: data?.nombre_completo ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("usuarios", "cambiar_estado") && (
            <Button
              variante="terciario"
              onClick={() => setDialogo("estado")}
              disabled={esYo || bloqueado}
              title={esYo ? "No puedes desactivarte" : motivo}
            >
              <Power size={14} /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede("usuarios", "eliminar") && (
            <Button
              variante="terciario"
              onClick={() => setDialogo("eliminar")}
              disabled={esYo || bloqueado}
              title={esYo ? "No puedes eliminarte" : motivo}
            >
              <Trash2 size={14} /> Eliminar
            </Button>
          )}
          {puede("usuarios", "editar") && (
            <Button onClick={() => navigate(`${RUTA}/${id}/editar`)} disabled={bloqueado} title={motivo}>
              <Pencil size={14} /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <Card titulo="Datos de acceso">
          <Detalle
            campos={[
              { etiqueta: "Nombre", valor: data.nombre_completo },
              { etiqueta: "Correo", valor: data.email },
              {
                etiqueta: "Rol",
                valor: data.rol_id ? (
                  <Link to={`/seguridad/roles/${data.rol_id}`} className="enlace">
                    {data.rol_nombre}
                  </Link>
                ) : (
                  data.rol_nombre
                ),
              },
              { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
              { etiqueta: "Creado", valor: formatearFecha(data.created_at) },
            ]}
          />
        </Card>
      )}

      <DialogosUsuario
        usuario={data}
        dialogo={dialogo}
        onCerrar={() => setDialogo(null)}
        onEstado={async () => {
          await api.patch(`${URL}/${id}/estado`, { activo: !data.activo });
          recargar();
        }}
        onEliminar={async () => {
          await api.delete(`${URL}/${id}`);
          navigate(RUTA);
        }}
      />
    </PantallaDetalle>
  );
}
