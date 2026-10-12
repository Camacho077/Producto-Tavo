import { useEffect, useMemo, useState } from "react";
import { Eye, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import SelectorBusqueda from "@/components/SelectorBusqueda";
import { api } from "@/lib/api";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { useAuth } from "@/context/AuthContext";
import { formatearFecha, formatearNumero } from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { TIPOS_DOCUMENTO, errorDocumento, esquemas } from "@/lib/validaciones";
import { AccionesFila, Badge, BotonAccion, Button, Card, Detalle, EstadoBadge, Input, ModalConfirmar, PageHeader, Select, Table, TablaRecurso } from "@/components/ui";
import { legible } from "@/lib/unidades";

const RUTA = "/inventario/proveedores";
const URL = "/compras/proveedores";

const FORM_VACIO = {
  tipo_persona: "juridica",
  tipo_documento: "",
  numero_documento: "",
  nombres: "",
  apellidos: "",
  nit: "",
  razon_social: "",
  representante_nombre: "",
  representante_documento: "",
  telefono: "",
  email: "",
  direccion: "",
  insumos: [],
};

// Reglas por tipo de persona. Los campos que no aplican al tipo elegido no
// se validan y se limpian antes de enviar (ver `limpiarPorTipo`).
const ESQUEMA = z
  .object({
    tipo_persona: z.enum(["natural", "juridica"]),
    tipo_documento: z.string(),
    numero_documento: z.string(),
    nombres: z.string(),
    apellidos: z.string(),
    nit: z.string(),
    razon_social: z.string(),
    representante_nombre: z.string(),
    representante_documento: z.string(),
    telefono: esquemas.telefono(),
    email: esquemas.emailOpcional(),
    direccion: esquemas.descripcion(255),
    insumos: z.array(z.object({ id: z.string(), nombre: z.string() }).loose()),
  })
  .superRefine((d, ctx) => {
    const agregar = (path, message) => ctx.addIssue({ code: "custom", path: [path], message });
    const probar = (path, esquema, valor) => {
      const r = esquema.safeParse(valor);
      if (!r.success) agregar(path, r.error.issues[0].message);
    };
    if (d.tipo_persona === "natural") {
      if (!d.tipo_documento) agregar("tipo_documento", "Selecciona el tipo de documento");
      else {
        const err = errorDocumento(d.tipo_documento, d.numero_documento);
        if (!d.numero_documento.trim()) agregar("numero_documento", "Este campo es obligatorio");
        else if (err) agregar("numero_documento", err);
      }
      probar("nombres", esquemas.nombrePersona(), d.nombres);
      probar("apellidos", esquemas.nombrePersona(), d.apellidos);
    } else {
      probar("nit", esquemas.nit(), d.nit);
      probar("razon_social", esquemas.nombreItem(150), d.razon_social);
      probar("representante_nombre", esquemas.nombrePersona(), d.representante_nombre);
      if (d.representante_documento) {
        const err = errorDocumento("CC", d.representante_documento);
        if (err) agregar("representante_documento", err);
      }
    }
  });

function limpiarPorTipo(d) {
  const base = {
    tipo_persona: d.tipo_persona,
    telefono: d.telefono || null,
    email: d.email || null,
    direccion: d.direccion || null,
    insumo_ids: d.insumos.map((p) => p.id),
  };
  if (d.tipo_persona === "natural") {
    return { ...base, tipo_documento: d.tipo_documento, numero_documento: d.numero_documento.trim().toUpperCase(), nombres: d.nombres, apellidos: d.apellidos };
  }
  return {
    ...base,
    nit: d.nit.trim(),
    razon_social: d.razon_social,
    representante_nombre: d.representante_nombre,
    representante_documento: d.representante_documento || null,
  };
}

function formDe(r) {
  return {
    tipo_persona: r.tipo_persona ?? "juridica",
    tipo_documento: r.tipo_documento ?? "",
    numero_documento: r.numero_documento ?? "",
    nombres: r.nombres ?? "",
    apellidos: r.apellidos ?? "",
    nit: r.nit ?? "",
    razon_social: r.razon_social ?? r.nombre ?? "",
    representante_nombre: r.representante_nombre ?? "",
    representante_documento: r.representante_documento ?? "",
    telefono: r.telefono ?? "",
    email: r.email ?? "",
    direccion: r.direccion ?? "",
    insumos: r.insumos ?? [],
  };
}

const migas = (...resto) => migasDe(MIGAS.proveedores, ...resto);

function DialogosProveedor({ proveedor, dialogo, onCerrar, onEstado, onEliminar }) {
  return (
    <>
      <ModalConfirmar
        abierto={dialogo === "estado"}
        onCerrar={onCerrar}
        titulo={proveedor?.activo ? "Desactivar proveedor" : "Activar proveedor"}
        textoConfirmar={proveedor?.activo ? "Desactivar" : "Activar"}
        mensaje={
          proveedor?.activo
            ? `"${proveedor?.nombre}" dejará de aparecer al registrar compras; conserva su historial.`
            : `"${proveedor?.nombre}" volverá a estar disponible.`
        }
        accion={`cambiar el estado del proveedor ${proveedor?.nombre ?? ""}`.trim()}
        mensajeExito={`${proveedor?.nombre} ${proveedor?.activo ? "desactivado" : "activado"}`}
        onConfirmar={onEstado}
      />
      <ModalConfirmar
        abierto={dialogo === "eliminar"}
        onCerrar={onCerrar}
        destructivo
        titulo="Eliminar proveedor"
        textoConfirmar="Eliminar"
        mensaje={`Esta acción no se puede deshacer. ¿Eliminar "${proveedor?.nombre}"?`}
        accion={`eliminar el proveedor ${proveedor?.nombre ?? ""}`.trim()}
        mensajeExito={`${proveedor?.nombre} eliminado`}
        onConfirmar={onEliminar}
      >
        {proveedor?.compras_count > 0 && (
          <p className="text-[var(--advertencia-texto)]">
            Tiene {proveedor.compras_count} compra(s) registrada(s): el sistema bloqueará la eliminación. Puedes desactivarlo en su lugar.
          </p>
        )}
      </ModalConfirmar>
    </>
  );
}

export function ProveedoresLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [filtroEstado, setFiltroEstado] = useState("");
  const listado = useListadoPaginado(URL, { filtros: filtroEstado ? { activo: filtroEstado === "activo" } : {} });
  const [dialogo, setDialogo] = useState(null);
  const registro = dialogo?.registro;

  const columnas = [
    {
      clave: "nombre",
      titulo: "Proveedor",
      render: (r) => (
        <Link to={`${RUTA}/${r.id}`} className="enlace">
          {r.nombre}
        </Link>
      ),
    },
    {
      clave: "tipo_persona", ajustar: true,
      titulo: "Tipo",
      render: (r) => <Badge variante="neutro">{r.tipo_persona === "natural" ? "Natural" : "Jurídica"}</Badge>,
    },
    { clave: "documento", ajustar: true, titulo: "NIT / Documento", render: (r) => <span className="cifra">{r.nit ?? r.numero_documento ?? "—"}</span> },
    { clave: "telefono", ajustar: true, titulo: "Teléfono", render: (r) => <span className="cifra">{r.telefono || "—"}</span> },
    { clave: "insumos", titulo: "Insumos", cifra: true, render: (r) => formatearNumero(r.insumos?.length ?? 0) },
    { clave: "compras_count", titulo: "Compras", cifra: true, render: (r) => formatearNumero(r.compras_count ?? 0) },
    { clave: "activo", ajustar: true, titulo: "Estado", render: (r) => <EstadoBadge activo={r.activo} /> },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (r) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${RUTA}/${r.id}`)} />
          {puede("proveedores", "editar") && (
            <BotonAccion icono={Pencil} etiqueta="Editar" onClick={() => navigate(`${RUTA}/${r.id}/editar`)} />
          )}
          {puede("proveedores", "cambiar_estado") && (
            <BotonAccion
              icono={Power}
              etiqueta={r.activo ? "Desactivar" : "Activar"}
              onClick={() => setDialogo({ tipo: "estado", registro: r })}
            />
          )}
          {puede("proveedores", "eliminar") && (
            <BotonAccion icono={Trash2} etiqueta="Eliminar" onClick={() => setDialogo({ tipo: "eliminar", registro: r })} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Proveedores"
        descripcion="A quién se le compra la mercancía: personas naturales o jurídicas."
        migas={migas()}
        acciones={
          puede("proveedores", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Nuevo proveedor
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar="proveedores"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por nombre, NIT, documento, teléfono o correo..."
        vacio="Todavía no hay proveedores registrados."
        filtros={
          <Select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} className="w-40" aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            <option value="activo">Solo activos</option>
            <option value="inactivo">Solo inactivos</option>
          </Select>
        }
      />

      <DialogosProveedor
        proveedor={registro}
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

function CamposProveedor({ f }) {
  const esNatural = f.form.tipo_persona === "natural";

  // Al cambiar el tipo, los campos del otro tipo se limpian de verdad.
  function cambiarTipo(tipo) {
    f.setForm((prev) => ({
      ...prev,
      tipo_persona: tipo,
      ...(tipo === "natural"
        ? { nit: "", razon_social: "", representante_nombre: "", representante_documento: "" }
        : { tipo_documento: "", numero_documento: "", nombres: "", apellidos: "" }),
    }));
  }

  return (
    <>
      <Seccion titulo="Identificación" descripcion="Los campos marcados con * son obligatorios.">
        <Select etiqueta="Tipo de persona" value={f.form.tipo_persona} onChange={(e) => cambiarTipo(e.target.value)} required data-campo="tipo_persona">
          <option value="juridica">Jurídica (empresa)</option>
          <option value="natural">Natural</option>
        </Select>

        {esNatural ? (
          <div key="natural" className="space-y-4">
            <div className="fila-campos">
              <Select etiqueta="Tipo de documento" {...f.props("tipo_documento")}>
                <option value="">Selecciona...</option>
                {TIPOS_DOCUMENTO.map((t) => (
                  <option key={t.valor} value={t.valor}>
                    {t.etiqueta}
                  </option>
                ))}
              </Select>
              <Input
                etiqueta="Número de documento"
                {...f.props("numero_documento")}
                cifra
                permitir={f.form.tipo_documento === "PA" ? "alfanumerico" : "digitos"}
                maxLength={12}
                ayuda={f.form.tipo_documento === "PA" ? "Letras y números, sin espacios" : "Solo dígitos"}
              />
            </div>
            <div className="fila-campos">
              <Input etiqueta="Nombres" {...f.props("nombres")} permitir="nombre" maxLength={80} autoComplete="off" />
              <Input etiqueta="Apellidos" {...f.props("apellidos")} permitir="nombre" maxLength={80} autoComplete="off" />
            </div>
          </div>
        ) : (
          <div key="juridica" className="space-y-4">
            <Input etiqueta="Razón social" {...f.props("razon_social")} permitir="nombre" maxLength={150} autoComplete="organization" />
            <div className="fila-campos">
              <Input etiqueta="NIT" {...f.props("nit")} cifra permitir="nit" placeholder="900123456-7" ayuda="Con dígito de verificación (DIAN)" />
              <Input
                etiqueta="Cédula del representante"
                {...f.props("representante_documento", { requerido: false })}
                cifra
                permitir="digitos"
                maxLength={10}
                ayuda="Opcional"
              />
            </div>
            <Input etiqueta="Representante legal" {...f.props("representante_nombre")} permitir="nombre" maxLength={80} autoComplete="off" />
          </div>
        )}
      </Seccion>

      <Seccion titulo="Contacto">
        <div className="fila-campos">
          <Input
            etiqueta="Teléfono"
            {...f.props("telefono", { requerido: false })}
            cifra
            permitir="telefono"
            placeholder="300 123 4567"
            ayuda="Celular (3…) o fijo con indicativo (60…)"
          />
          <Input etiqueta="Correo electrónico" {...f.props("email", { requerido: false })} permitir="correo" maxLength={150} ayuda="Opcional" autoComplete="off" />
        </div>
        <Input etiqueta="Dirección" {...f.props("direccion", { requerido: false })} maxLength={255} ayuda="Opcional" />
      </Seccion>

      <Seccion titulo="Insumos que surte" descripcion="Busca y agrega los insumos que este proveedor suministra; al registrar una compra se ofrecen primero.">
        <SelectorBusqueda
          url="/inventario/insumos"
          filtros={{ activo: true }}
          multiple
          valor={f.form.insumos}
          onCambiar={(insumos) => f.setForm((prev) => ({ ...prev, insumos }))}
          placeholder="Buscar insumo por nombre o grupo..."
          etiquetaDe={(p) => p.nombre}
          detalleDe={(p) => p.grupo}
          nombreCampo="insumos"
          ayuda={f.form.insumos.length === 0 ? "Sin insumos asociados todavía (opcional)" : `${f.form.insumos.length} insumo(s) asociado(s)`}
        />
      </Seccion>
    </>
  );
}

export function ProveedorNuevo() {
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: RUTA, mensaje: "Proveedor creado", accion: "crear el proveedor" });

  return (
    <div className="pantalla-estrecha">
      <PageHeader volver={RUTA} titulo="Nuevo proveedor" migas={migas({ etiqueta: "Nuevo proveedor" })} />
      <FormularioPantalla
        id="form-proveedor"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, limpiarPorTipo(d)))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposProveedor f={f} />
      </FormularioPantalla>
    </div>
  );
}

export function ProveedorEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, { volver: `${RUTA}/${id}`, mensaje: "Cambios guardados", accion: "guardar el proveedor" });

  useEffect(() => {
    if (data) f.reiniciar(formDe(data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar ${data.nombre}` : "Editar proveedor"}
      migas={migas({ etiqueta: data?.nombre ?? "…", a: `${RUTA}/${id}` }, { etiqueta: "Editar" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-proveedor"
        onSubmit={(e) => guardar(e, (d) => api.put(`${URL}/${id}`, limpiarPorTipo(d)))}
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposProveedor f={f} />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

export function ProveedorDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogo, setDialogo] = useState(null);
  const { puede } = useAuth();

  const camposPersona = data
    ? data.tipo_persona === "natural"
      ? [
          { etiqueta: "Nombres", valor: data.nombres },
          { etiqueta: "Apellidos", valor: data.apellidos },
          { etiqueta: "Tipo de documento", valor: TIPOS_DOCUMENTO.find((t) => t.valor === data.tipo_documento)?.etiqueta },
          { etiqueta: "Documento", valor: data.numero_documento, cifra: true },
        ]
      : [
          { etiqueta: "Razón social", valor: data.razon_social ?? data.nombre },
          { etiqueta: "NIT", valor: data.nit, cifra: true },
          { etiqueta: "Representante legal", valor: data.representante_nombre },
          { etiqueta: "Cédula del representante", valor: data.representante_documento, cifra: true },
        ]
    : [];

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data?.nombre ?? "Detalle del proveedor"}
      descripcion={data ? (data.tipo_persona === "natural" ? "Persona natural" : "Persona jurídica") : undefined}
      migas={migas({ etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("proveedores", "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogo("estado")}>
              <Power size={14} /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede("proveedores", "eliminar") && (
            <Button variante="terciario" onClick={() => setDialogo("eliminar")}>
              <Trash2 size={14} /> Eliminar
            </Button>
          )}
          {puede("proveedores", "editar") && (
            <Button onClick={() => navigate(`${RUTA}/${id}/editar`)}>
              <Pencil size={14} /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Datos generales">
              <Detalle
                campos={[
                  ...camposPersona,
                  { etiqueta: "Teléfono", valor: data.telefono, cifra: true },
                  { etiqueta: "Correo", valor: data.email },
                  { etiqueta: "Dirección", valor: data.direccion },
                  { etiqueta: "Estado", valor: <EstadoBadge activo={data.activo} /> },
                  { etiqueta: "Creado", valor: formatearFecha(data.created_at) },
                ]}
              />
            </Card>
            <Card titulo="Compras">
              <p className="dato-grande cifra">{formatearNumero(data.compras_count ?? 0)}</p>
              <p className="text-[12px] text-[var(--texto-terciario)] mt-1">compras registradas a este proveedor</p>
              {puede("compras", "crear") && (
                <Button variante="terciario" tamano="sm" className="mt-3" onClick={() => navigate(`/inventario/compras/nuevo?proveedor=${id}`)}>
                  <Plus size={14} /> Registrar compra
                </Button>
              )}
            </Card>
          </div>

          <Card titulo="Insumos que surte" descripcion={`${data.insumos?.length ?? 0} insumo(s) asociado(s).`}>
            <Table
              columnas={[
                {
                  clave: "nombre",
                  titulo: "Insumo",
                  render: (p) => (
                    <Link to={`/inventario/insumos/${p.id}`} className="enlace">
                      {p.nombre}
                    </Link>
                  ),
                },
                { clave: "existencia", titulo: "Existencia", cifra: true, render: (p) => legible(p.existencia, p.unidad) },
              ]}
              filas={data.insumos ?? []}
              vacio="Este proveedor no tiene insumos asociados. Agrégalos desde Editar."
            />
          </Card>
        </div>
      )}

      <DialogosProveedor
        proveedor={data}
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
