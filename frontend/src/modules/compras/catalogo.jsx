import { useEffect, useMemo, useState } from "react";
import { Eye, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import { api } from "@/lib/api";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { useAuth } from "@/context/AuthContext";
import { formatearFecha, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { esquemas } from "@/lib/validaciones";
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
  Textarea,
} from "@/components/ui";

const ESQUEMA = z.object({
  nombre: esquemas.nombreItem(100),
  descripcion: esquemas.descripcion(255),
});
const FORM_VACIO = { nombre: "", descripcion: "" };

/**
 * Pantallas de un catálogo simple (Categorías y Marcas): listado, crear,
 * detalle y editar, cada una con su ruta. Solo cambiar estado y eliminar
 * siguen siendo diálogos de confirmación.
 *
 * `config`: { titulo, descripcion, singular, articulo ("la"|"el"), url, ruta, placeholder }
 */
function migasDeCatalogo(config, ...resto) {
  return migasDe([...MIGAS.compras, { etiqueta: config.titulo, a: config.ruta }], ...resto);
}

const nuevoDe = (config) => (config.articulo === "la" ? "Nueva" : "Nuevo");
// El módulo de permisos es el último tramo de la URL: /compras/categorias -> "categorias".
const moduloDe = (config) => config.modulo ?? config.url.split("/").pop();
const genero = (config) => (config.articulo === "la" ? "a" : "o");

export function CatalogoLista({ config }) {
  const { titulo, descripcion, singular, articulo, url, ruta, placeholder } = config;
  const navigate = useNavigate();
  const { puede } = useAuth();
  const modulo = moduloDe(config);
  const [filtroEstado, setFiltroEstado] = useState("");
  const listado = useListadoPaginado(url, { filtros: filtroEstado ? { activo: filtroEstado === "activo" } : {} });
  const [dialogo, setDialogo] = useState(null);
  const registro = dialogo?.registro;
  const cerrar = () => setDialogo(null);

  const columnas = [
    {
      clave: "nombre",
      titulo: "Nombre",
      render: (r) => (
        <Link to={`${ruta}/${r.id}`} className="enlace">
          {r.nombre}
        </Link>
      ),
    },
    { clave: "descripcion", titulo: "Descripción", render: (r) => r.descripcion || "—" },
    { clave: "productos_count", titulo: "Productos", cifra: true, render: (r) => formatearNumero(r.productos_count ?? 0) },
    {
      clave: "activo", ajustar: true,
      titulo: "Estado",
      render: (r) => <EstadoBadge activo={r.activo} />,
    },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (r) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${ruta}/${r.id}`)} />
          {puede(modulo, "editar") && (
            <BotonAccion icono={Pencil} etiqueta="Editar" onClick={() => navigate(`${ruta}/${r.id}/editar`)} />
          )}
          {puede(modulo, "cambiar_estado") && (
            <BotonAccion
              icono={Power}
              etiqueta={r.activo ? "Desactivar" : "Activar"}
              onClick={() => setDialogo({ tipo: "estado", registro: r })}
            />
          )}
          {puede(modulo, "eliminar") && (
            <BotonAccion icono={Trash2} etiqueta="Eliminar" onClick={() => setDialogo({ tipo: "eliminar", registro: r })} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo={titulo}
        descripcion={descripcion}
        migas={migasDeCatalogo(config)}
        acciones={
          puede(modulo, "crear") && (
            <Button onClick={() => navigate(`${ruta}/nuevo`)}>
              <Plus size={14} /> {nuevoDe(config)} {singular}
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar={modulo}
        listado={listado}
        columnas={columnas}
        placeholderBusqueda={placeholder}
        vacio={`Todavía no hay ${titulo.toLowerCase()} registrad${articulo === "la" ? "as" : "os"}.`}
        filtros={
          <Select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            <option value="activo">Solo activos</option>
            <option value="inactivo">Solo inactivos</option>
          </Select>
        }
      />

      <ModalConfirmar
        abierto={dialogo?.tipo === "estado"}
        onCerrar={cerrar}
        titulo={registro?.activo ? `Desactivar ${singular}` : `Activar ${singular}`}
        textoConfirmar={registro?.activo ? "Desactivar" : "Activar"}
        mensaje={
          registro?.activo
            ? `"${registro?.nombre}" dejará de aparecer en los formularios, pero conserva su historial.`
            : `"${registro?.nombre}" volverá a estar disponible en los formularios.`
        }
        accion={`cambiar el estado de ${registro?.nombre ?? singular}`}
        mensajeExito={`${registro?.nombre} ${registro?.activo ? "desactivad" : "activad"}${genero(config)}`}
        onConfirmar={async () => {
          await api.patch(`${url}/${registro.id}/estado`, { activo: !registro.activo });
          listado.recargar();
        }}
      />

      <ModalConfirmar
        abierto={dialogo?.tipo === "eliminar"}
        onCerrar={cerrar}
        destructivo
        titulo={`Eliminar ${singular}`}
        textoConfirmar="Eliminar"
        mensaje={`Esta acción no se puede deshacer. ¿Eliminar "${registro?.nombre}"?`}
        accion={`eliminar ${config.articulo} ${singular} ${registro?.nombre ?? ""}`.trim()}
        mensajeExito={`${registro?.nombre} eliminad${genero(config)}`}
        onConfirmar={async () => {
          await api.delete(`${url}/${registro.id}`);
          listado.recargar();
        }}
      >
        {registro?.productos_count > 0 && (
          <p className="text-[var(--advertencia-texto)]">
            Tiene {registro.productos_count} producto(s) asociado(s): el sistema bloqueará la eliminación. Puedes desactivar
            {articulo === "la" ? "la" : "lo"} en su lugar.
          </p>
        )}
      </ModalConfirmar>
    </div>
  );
}

function CamposCatalogo({ f }) {
  return (
    <Seccion titulo="Datos generales" descripcion="Los campos marcados con * son obligatorios.">
      <Input etiqueta="Nombre" {...f.props("nombre")} permitir="nombre" maxLength={100} autoComplete="off" />
      <Textarea etiqueta="Descripción" {...f.props("descripcion", { requerido: false })} maxLength={255} ayuda="Opcional" />
    </Seccion>
  );
}

export function CatalogoNuevo({ config }) {
  const { singular, url, ruta, descripcion } = config;
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const titulo = `${nuevoDe(config)} ${singular}`;
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: ruta,
    mensaje: `${singular[0].toUpperCase()}${singular.slice(1)} cread${genero(config)}`,
    accion: `crear ${config.articulo} ${singular}`,
  });

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={ruta} titulo={titulo} descripcion={descripcion} migas={migasDeCatalogo(config, { etiqueta: titulo })} />
      <FormularioPantalla
        id={`form-${singular}`}
        onSubmit={(e) => guardar(e, (d) => api.post(url, { nombre: d.nombre, descripcion: d.descripcion || null }))}
        volver={ruta}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposCatalogo f={f} />
      </FormularioPantalla>
    </div>
  );
}

export function CatalogoEditar({ config }) {
  const { singular, url, ruta } = config;
  const { id } = useParams();
  const { data, error } = useApiResource(`${url}/${id}`);
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: `${ruta}/${id}`,
    mensaje: "Cambios guardados",
    accion: `guardar ${config.articulo} ${singular}`,
  });

  useEffect(() => {
    if (data) f.reiniciar({ nombre: data.nombre, descripcion: data.descripcion ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={ruta}
      titulo={data ? `Editar ${data.nombre}` : `Editar ${singular}`}
      migas={migasDeCatalogo(config, { etiqueta: data?.nombre ?? "…", a: `${ruta}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id={`form-${singular}`}
        onSubmit={(e) => guardar(e, (d) => api.put(`${url}/${id}`, { nombre: d.nombre, descripcion: d.descripcion || null }))}
        volver={`${ruta}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposCatalogo f={f} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function CatalogoDetalle({ config }) {
  const { singular, url, ruta } = config;
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error, recargar } = useApiResource(`${url}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  const { puede } = useAuth();
  const modulo = moduloDe(config);

  return (
    <PantallaDetalle
      volver={ruta}
      titulo={data?.nombre ?? `Detalle de ${singular}`}
      migas={migasDeCatalogo(config, { etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede(modulo, "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogo("estado")}>
              <Power size={14} /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede(modulo, "eliminar") && (
            <Button variante="terciario" onClick={() => setDialogo("eliminar")}>
              <Trash2 size={14} /> Eliminar
            </Button>
          )}
          {puede(modulo, "editar") && (
            <Button onClick={() => navigate(`${ruta}/${id}/editar`)}>
              <Pencil size={14} /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <Card titulo="Datos generales">
          <Detalle
            campos={[
              { etiqueta: "Nombre", valor: data.nombre },
              { etiqueta: "Productos", valor: formatearNumero(data.productos_count ?? 0), cifra: true },
              { etiqueta: "Descripción", valor: data.descripcion },
              { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
              { etiqueta: "Creado", valor: formatearFecha(data.created_at) },
            ]}
          />
        </Card>
      )}

      <ModalConfirmar
        abierto={dialogo === "estado"}
        onCerrar={() => setDialogo(null)}
        titulo={data?.activo ? `Desactivar ${singular}` : `Activar ${singular}`}
        textoConfirmar={data?.activo ? "Desactivar" : "Activar"}
        mensaje={
          data?.activo
            ? `"${data?.nombre}" dejará de aparecer en los formularios, pero conserva su historial.`
            : `"${data?.nombre}" volverá a estar disponible en los formularios.`
        }
        accion={`cambiar el estado de ${data?.nombre ?? singular}`}
        mensajeExito={`${data?.nombre} ${data?.activo ? "desactivad" : "activad"}${genero(config)}`}
        onConfirmar={async () => {
          await api.patch(`${url}/${id}/estado`, { activo: !data.activo });
          recargar();
        }}
      />
      <ModalConfirmar
        abierto={dialogo === "eliminar"}
        onCerrar={() => setDialogo(null)}
        destructivo
        titulo={`Eliminar ${singular}`}
        textoConfirmar="Eliminar"
        mensaje={`Esta acción no se puede deshacer. ¿Eliminar "${data?.nombre}"?`}
        accion={`eliminar ${config.articulo} ${singular} ${data?.nombre ?? ""}`.trim()}
        mensajeExito={`${data?.nombre} eliminad${genero(config)}`}
        onConfirmar={async () => {
          await api.delete(`${url}/${id}`);
          navigate(ruta);
        }}
      />
    </PantallaDetalle>
  );
}
