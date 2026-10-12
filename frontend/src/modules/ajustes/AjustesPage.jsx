import { useEffect, useMemo } from "react";
import { Pencil, Plus, Printer, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import SubirImagen from "@/components/SubirImagen";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Detalle,
  GrupoCasillas,
  Input,
  Select,
  Table,
} from "@/components/ui";
import {
  CONEXIONES_IMPRESORA,
  MEDIOS_PAGO,
  ORIGENES,
  TIPOS_ORDEN,
  USOS_IMPRESORA,
  etiquetaConexionImpresora,
  etiquetaMedioPago,
  etiquetaOrigen,
  etiquetaTipoOrden,
  etiquetaUsoImpresora,
} from "@/config/restaurante";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { api } from "@/lib/api";
import { urlImagen } from "@/lib/imagenes";
import { MIGAS, migasDe } from "@/lib/migas";
import { MSG, errorNit, esquemas } from "@/lib/validaciones";

import "./ajustes.css";

const RUTA = "/ajustes";
const migas = (...resto) => migasDe(MIGAS.ajustes, ...resto);

// ---------------------------------------------------------------------------
// Detalle: todo lo configurado, de un vistazo
// ---------------------------------------------------------------------------
const lista = (valores, etiquetaDe) => (valores?.length ? valores.map(etiquetaDe).join(" · ") : null);

function textoImpuesto(imp) {
  if (!imp?.aplica) return "No aplica";
  const tasa = `${Number(imp.tasa).toLocaleString("es-CO")} %`;
  return `${tasa} · ${imp.incluido_en_precio ? "incluido en el precio de la carta" : "se suma al cobrar"}`;
}

export function AjustesDetalle() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const negocio = useApiResource("/ajustes/negocio");
  const config = useApiResource("/ajustes/restaurante");
  const datos = negocio.data && config.data ? { negocio: negocio.data, config: config.data } : null;
  const editar = puede("ajustes", "editar");

  return (
    <PantallaDetalle
      titulo="Restaurante"
      descripcion="Lo que sale en la comanda y en la factura, y cómo opera el servicio."
      migas={migas()}
      error={negocio.error || config.error}
      datos={datos}
    >
      {datos && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card
              titulo="Datos del negocio"
              descripcion="Encabezan la comanda, la factura interna y los PDF."
              acciones={
                editar && (
                  <Button variante="terciario" tamano="sm" onClick={() => navigate(`${RUTA}/negocio/editar`)}>
                    <Pencil size={14} aria-hidden="true" /> Editar
                  </Button>
                )
              }
            >
              <Detalle
                campos={[
                  { etiqueta: "Nombre", valor: datos.negocio.nombre_empresa },
                  { etiqueta: "NIT", valor: datos.negocio.nit, cifra: true },
                  { etiqueta: "Dirección", valor: datos.negocio.direccion },
                  { etiqueta: "Ciudad", valor: datos.negocio.ciudad },
                  { etiqueta: "Teléfono", valor: datos.negocio.telefono, cifra: true },
                  { etiqueta: "Correo", valor: datos.negocio.correo },
                ]}
              />
            </Card>
            <Card titulo="Logo" descripcion="Para la comanda y la factura.">
              {datos.negocio.logo_id ? (
                <img className="ajustes-logo" src={urlImagen(datos.negocio.logo_id)} alt={`Logo de ${datos.negocio.nombre_empresa}`} />
              ) : (
                <p className="text-[13px] text-[var(--texto-secundario)]">Sin logo: la comanda y la factura llevan solo el nombre.</p>
              )}
            </Card>
          </div>

          <Card
            titulo="Operación"
            descripcion="Cómo se toman, se preparan y se cobran las órdenes."
            acciones={
              editar && (
                <Button variante="terciario" tamano="sm" onClick={() => navigate(`${RUTA}/operacion/editar`)}>
                  <Pencil size={14} aria-hidden="true" /> Editar
                </Button>
              )
            }
          >
            <Detalle
              campos={[
                { etiqueta: "Tipos de orden", valor: lista(datos.config.tipos_orden, etiquetaTipoOrden) },
                { etiqueta: "Origen del pedido", valor: lista(datos.config.origenes, etiquetaOrigen) },
                { etiqueta: "Medios de pago", valor: lista(datos.config.medios_pago, etiquetaMedioPago) },
                { etiqueta: "Impuesto al consumo", valor: textoImpuesto(datos.config.impuesto_consumo) },
                {
                  etiqueta: "Propina sugerida",
                  valor: `${Number(datos.config.propina_sugerida).toLocaleString("es-CO")} % · el cliente decide, nunca se cobra sola`,
                },
                { etiqueta: "Alerta en cocina", valor: `A los ${datos.config.alerta_cocina_minutos} min de entrar la orden` },
                { etiqueta: "Aviso sonoro", valor: datos.config.sonido_cocina ? "Sí, al entrar una orden" : "No" },
                { etiqueta: "Jornada", valor: `De ${datos.config.jornada.inicio} a ${datos.config.jornada.fin}`, cifra: true },
              ]}
            />
          </Card>

          <Card titulo="Impresoras" descripcion="Térmicas de 58 u 80 mm para comandas y facturas.">
            <Table
              columnas={[
                { clave: "nombre", titulo: "Impresora" },
                { clave: "uso", titulo: "Imprime", render: (i) => etiquetaUsoImpresora(i.uso) },
                { clave: "ancho_mm", titulo: "Ancho", cifra: true, render: (i) => `${i.ancho_mm} mm` },
                {
                  clave: "conexion",
                  titulo: "Conexión",
                  render: (i) => (i.conexion === "ip" ? `${etiquetaConexionImpresora(i.conexion)} · ${i.direccion}` : etiquetaConexionImpresora(i.conexion)),
                },
                { clave: "activa", titulo: "Estado", ajustar: true, render: (i) => <Badge variante={i.activa ? "positivo" : "neutro"}>{i.activa ? "Activa" : "Inactiva"}</Badge> },
              ]}
              filas={datos.config.impresoras}
              vacio="Sin impresoras configuradas: la comanda y la factura se imprimen con el diálogo del navegador, en 80 mm."
            />
          </Card>
        </div>
      )}
    </PantallaDetalle>
  );
}

// ---------------------------------------------------------------------------
// Editar datos del negocio
// ---------------------------------------------------------------------------
const ESQUEMA_NEGOCIO = z.object({
  nombre_empresa: esquemas.nombreCarta(80),
  nit: z.string().superRefine((s, ctx) => {
    const problema = s.trim() === "" ? null : errorNit(s);
    if (problema) ctx.addIssue({ code: "custom", message: problema });
  }),
  direccion: esquemas.descripcion(150),
  ciudad: z.string().refine((s) => s.trim() === "" || /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]{2,60}$/.test(s.trim()), MSG.nombrePersona),
  telefono: esquemas.telefono(),
  correo: esquemas.emailOpcional(),
});
const NEGOCIO_VACIO = { nombre_empresa: "", nit: "", direccion: "", ciudad: "", telefono: "", correo: "" };

export function NegocioEditar() {
  const { data, error, recargar } = useApiResource("/ajustes/negocio");
  const { refrescarSesion } = useAuth();
  const esquema = useMemo(() => ESQUEMA_NEGOCIO, []);
  const f = useFormulario(esquema, NEGOCIO_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: RUTA,
    mensaje: "Datos del negocio guardados",
    accion: "guardar los datos del negocio",
  });

  useEffect(() => {
    if (data) {
      f.reiniciar({
        nombre_empresa: data.nombre_empresa ?? "",
        nit: data.nit ?? "",
        direccion: data.direccion ?? "",
        ciudad: data.ciudad ?? "",
        telefono: data.telefono ?? "",
        correo: data.correo ?? "",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo="Datos del negocio"
      descripcion="Encabezan la comanda, la factura interna y los PDF."
      migas={migas({ etiqueta: "Datos del negocio" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-negocio"
        onSubmit={(e) =>
          guardar(e, async (d) => {
            await api.put("/ajustes/negocio", {
              nombre_empresa: d.nombre_empresa,
              nit: d.nit.trim() || null,
              direccion: d.direccion.trim() || null,
              ciudad: d.ciudad.trim() || null,
              telefono: d.telefono || null,
              correo: d.correo || null,
            });
            refrescarSesion();
          })
        }
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <Seccion titulo="Identificación" descripcion="Los campos marcados con * son obligatorios.">
          <Input etiqueta="Nombre del restaurante" {...f.props("nombre_empresa")} permitir="carta" maxLength={80} autoComplete="organization" />
          <div className="fila-campos">
            <Input etiqueta="NIT" {...f.props("nit", { requerido: false })} permitir="nit" cifra ayuda="Con dígito de verificación: 900123456-7" />
            <Input etiqueta="Teléfono" {...f.props("telefono", { requerido: false })} permitir="telefono" cifra autoComplete="tel" />
          </div>
        </Seccion>
        <Seccion titulo="Ubicación y contacto">
          <Input etiqueta="Dirección" {...f.props("direccion", { requerido: false })} maxLength={150} autoComplete="street-address" />
          <div className="fila-campos">
            <Input etiqueta="Ciudad" {...f.props("ciudad", { requerido: false })} permitir="nombre" maxLength={60} autoComplete="address-level2" />
            <Input etiqueta="Correo" {...f.props("correo", { requerido: false })} permitir="correo" autoComplete="email" />
          </div>
        </Seccion>
        <Seccion titulo="Logo" descripcion="Se sube al elegirlo, aparte del botón Guardar. Se ajusta solo a 600 × 300 px.">
          <SubirImagen
            etiqueta="Logo"
            forma="ancha"
            imagenId={data?.logo_id}
            urlSubir="/ajustes/negocio/logo"
            urlQuitar="/ajustes/negocio/logo"
            textoAlt={`Logo de ${data?.nombre_empresa ?? "el restaurante"}`}
            mensajeExito="Logo actualizado"
            mensajeQuitada="Logo quitado"
            onCambio={() => {
              recargar();
              refrescarSesion();
            }}
          />
        </Seccion>
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

// ---------------------------------------------------------------------------
// Editar la operación
// ---------------------------------------------------------------------------
const lista1 = (msg) => z.array(z.string()).min(1, msg);
const ESQUEMA_IMPRESORA = z.object({
  id: z.string().optional(),
  nombre: esquemas.nombreCarta(40),
  uso: z.string(),
  ancho_mm: z.string(),
  conexion: z.string(),
  direccion: z.string(),
  activa: z.boolean(),
}).superRefine((imp, ctx) => {
  if (imp.conexion === "ip" && !/^(\d{1,3}\.){3}\d{1,3}(:\d{2,5})?$/.test(imp.direccion.trim())) {
    ctx.addIssue({ code: "custom", path: ["direccion"], message: "Escribe la dirección IP de la impresora, p. ej. 192.168.1.50:9100" });
  }
});

const ESQUEMA_OPERACION = z.object({
  tipos_orden: lista1("Habilita al menos un tipo de orden"),
  origenes: lista1("Habilita al menos un origen"),
  medios_pago: lista1("Habilita al menos un medio de pago"),
  impuesto_aplica: z.boolean(),
  impuesto_tasa: esquemas.porcentaje(),
  impuesto_incluido: z.boolean(),
  propina_sugerida: esquemas.porcentaje().refine((s) => Number(s) <= 30, "La propina sugerida no puede pasar del 30 %"),
  alerta_cocina_minutos: esquemas.entero(1, 180),
  sonido_cocina: z.boolean(),
  jornada_inicio: esquemas.hora(),
  jornada_fin: esquemas.hora(),
  impresoras: z.array(ESQUEMA_IMPRESORA).max(10, "Máximo 10 impresoras"),
}).refine((d) => d.jornada_inicio !== d.jornada_fin, { path: ["jornada_fin"], message: "La hora de inicio y la de cierre de la jornada no pueden ser iguales" });

const OPERACION_VACIA = {
  tipos_orden: [],
  origenes: [],
  medios_pago: [],
  impuesto_aplica: true,
  impuesto_tasa: "8",
  impuesto_incluido: true,
  propina_sugerida: "10",
  alerta_cocina_minutos: "15",
  sonido_cocina: true,
  jornada_inicio: "06:00",
  jornada_fin: "22:00",
  impresoras: [],
};

const numeroATexto = (n) => String(Number(n));
const nuevaImpresora = () => ({ nombre: "", uso: "ambos", ancho_mm: "80", conexion: "navegador", direccion: "", activa: true });

export function OperacionEditar() {
  const { data, error } = useApiResource("/ajustes/restaurante");
  const { refrescarSesion } = useAuth();
  const esquema = useMemo(() => ESQUEMA_OPERACION, []);
  const f = useFormulario(esquema, OPERACION_VACIA);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: RUTA,
    mensaje: "Operación del restaurante guardada",
    accion: "guardar la operación del restaurante",
  });

  useEffect(() => {
    if (data) {
      f.reiniciar({
        tipos_orden: data.tipos_orden,
        origenes: data.origenes,
        medios_pago: data.medios_pago,
        impuesto_aplica: data.impuesto_consumo.aplica,
        impuesto_tasa: numeroATexto(data.impuesto_consumo.tasa),
        impuesto_incluido: data.impuesto_consumo.incluido_en_precio,
        propina_sugerida: numeroATexto(data.propina_sugerida),
        alerta_cocina_minutos: String(data.alerta_cocina_minutos),
        sonido_cocina: data.sonido_cocina,
        jornada_inicio: data.jornada.inicio,
        jornada_fin: data.jornada.fin,
        impresoras: data.impresoras.map((i) => ({ ...i, ancho_mm: String(i.ancho_mm), direccion: i.direccion ?? "" })),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const impresoras = f.form.impresoras;
  const cambiarImpresora = (i, campo, valor) =>
    f.setForm((prev) => ({ ...prev, impresoras: prev.impresoras.map((imp, j) => (j === i ? { ...imp, [campo]: valor } : imp)) }));

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo="Operación del restaurante"
      descripcion="Cómo se toman, se preparan y se cobran las órdenes."
      migas={migas({ etiqueta: "Operación" })}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-operacion"
        onSubmit={(e) =>
          guardar(e, async (d) => {
            await api.put("/ajustes/restaurante", {
              tipos_orden: d.tipos_orden,
              origenes: d.origenes,
              medios_pago: d.medios_pago,
              impuesto_consumo: { aplica: d.impuesto_aplica, tasa: d.impuesto_tasa, incluido_en_precio: d.impuesto_incluido },
              propina_sugerida: d.propina_sugerida,
              alerta_cocina_minutos: Number(d.alerta_cocina_minutos),
              sonido_cocina: d.sonido_cocina,
              jornada: { inicio: d.jornada_inicio, fin: d.jornada_fin },
              impresoras: d.impresoras.map((imp) => ({
                ...(imp.id ? { id: imp.id } : {}),
                nombre: imp.nombre,
                uso: imp.uso,
                ancho_mm: Number(imp.ancho_mm),
                conexion: imp.conexion,
                direccion: imp.conexion === "ip" ? imp.direccion.trim() : null,
                activa: imp.activa,
              })),
            });
            refrescarSesion();
          })
        }
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <Seccion titulo="Órdenes" descripcion="Lo que el mesero puede elegir al tomar un pedido.">
          <GrupoCasillas
            etiqueta="Tipos de orden habilitados"
            required
            campo="tipos_orden"
            opciones={TIPOS_ORDEN}
            valor={f.form.tipos_orden}
            onChange={(v) => f.setCampo("tipos_orden", v)}
            onBlur={() => f.tocar("tipos_orden")}
            error={f.errorVisible("tipos_orden")}
          />
          <GrupoCasillas
            etiqueta="Origen del pedido"
            required
            campo="origenes"
            opciones={ORIGENES}
            valor={f.form.origenes}
            onChange={(v) => f.setCampo("origenes", v)}
            onBlur={() => f.tocar("origenes")}
            error={f.errorVisible("origenes")}
          />
        </Seccion>

        <Seccion titulo="Cobro" descripcion="Medios de pago que acepta la caja, impuesto y propina.">
          <GrupoCasillas
            etiqueta="Medios de pago"
            required
            campo="medios_pago"
            opciones={MEDIOS_PAGO}
            valor={f.form.medios_pago}
            onChange={(v) => f.setCampo("medios_pago", v)}
            onBlur={() => f.tocar("medios_pago")}
            error={f.errorVisible("medios_pago")}
          />
          <Checkbox
            checked={f.form.impuesto_aplica}
            onChange={(e) => f.setCampo("impuesto_aplica", e.target.checked)}
            etiqueta="El restaurante cobra impuesto al consumo"
          />
          <div className="fila-campos">
            <Input etiqueta="Tarifa del impuesto (%)" {...f.props("impuesto_tasa")} permitir="decimal" cifra disabled={!f.form.impuesto_aplica} ayuda="En Colombia es del 8 %" />
            <Input etiqueta="Propina sugerida (%)" {...f.props("propina_sugerida")} permitir="decimal" cifra ayuda="Se ofrece al cobrar; nunca es automática" />
          </div>
          <Checkbox
            checked={f.form.impuesto_incluido}
            onChange={(e) => f.setCampo("impuesto_incluido", e.target.checked)}
            disabled={!f.form.impuesto_aplica}
            etiqueta="Los precios de la carta ya incluyen el impuesto"
          />
          <p className="campo__ayuda">Confirma con el contador del restaurante si es responsable del impuesto al consumo.</p>
        </Seccion>

        <Seccion titulo="Cocina y jornada">
          <div className="fila-campos">
            <Input etiqueta="Alerta en cocina (minutos)" {...f.props("alerta_cocina_minutos")} permitir="entero" maxLength={3} cifra ayuda="La tarjeta cambia de tono al pasar este tiempo" />
            <div className="ajustes-casilla-alineada">
              <Checkbox checked={f.form.sonido_cocina} onChange={(e) => f.setCampo("sonido_cocina", e.target.checked)} etiqueta="Aviso sonoro al entrar una orden" />
            </div>
          </div>
          <div className="fila-campos">
            <Input etiqueta="Inicio de la jornada" type="time" {...f.props("jornada_inicio")} cifra ayuda="Aquí arranca el consecutivo del día" />
            <Input etiqueta="Cierre de la jornada" type="time" {...f.props("jornada_fin")} cifra />
          </div>
        </Seccion>

        <Seccion titulo="Impresoras" descripcion="Sin impresoras, la comanda y la factura se imprimen con el diálogo del navegador.">
          {impresoras.map((imp, i) => (
            <div key={imp.id ?? `nueva-${i}`} className="ajustes-impresora">
              <div className="ajustes-impresora__cabeza">
                <Printer size={14} aria-hidden="true" />
                <span>Impresora {i + 1}</span>
                <Button
                  variante="terciario"
                  soloIcono
                  tamano="sm"
                  className="ml-auto"
                  aria-label={`Quitar la impresora ${imp.nombre || i + 1}`}
                  title="Quitar impresora"
                  onClick={() => f.setForm((prev) => ({ ...prev, impresoras: prev.impresoras.filter((_, j) => j !== i) }))}
                >
                  <Trash2 size={14} />
                </Button>
              </div>
              <div className="fila-campos">
                <Input
                  etiqueta="Nombre"
                  required
                  permitir="carta"
                  maxLength={40}
                  value={imp.nombre}
                  onChange={(e) => cambiarImpresora(i, "nombre", e.target.value)}
                  onBlur={() => f.tocar(`impresoras.${i}.nombre`)}
                  error={f.errorVisible(`impresoras.${i}.nombre`)}
                  data-campo={`impresoras.${i}.nombre`}
                />
                <Select etiqueta="Imprime" value={imp.uso} onChange={(e) => cambiarImpresora(i, "uso", e.target.value)}>
                  {USOS_IMPRESORA.map((u) => (
                    <option key={u.valor} value={u.valor}>
                      {u.etiqueta}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="fila-campos fila-campos--tres">
                <Select etiqueta="Ancho del papel" value={imp.ancho_mm} onChange={(e) => cambiarImpresora(i, "ancho_mm", e.target.value)}>
                  <option value="80">80 mm</option>
                  <option value="58">58 mm</option>
                </Select>
                <Select etiqueta="Conexión" value={imp.conexion} onChange={(e) => cambiarImpresora(i, "conexion", e.target.value)}>
                  {CONEXIONES_IMPRESORA.map((c) => (
                    <option key={c.valor} value={c.valor}>
                      {c.etiqueta}
                    </option>
                  ))}
                </Select>
                <Input
                  etiqueta="Dirección IP"
                  cifra
                  maxLength={21}
                  disabled={imp.conexion !== "ip"}
                  required={imp.conexion === "ip"}
                  value={imp.direccion}
                  placeholder="192.168.1.50:9100"
                  onChange={(e) => cambiarImpresora(i, "direccion", e.target.value.replace(/[^\d.:]/g, ""))}
                  onBlur={() => f.tocar(`impresoras.${i}.direccion`)}
                  error={f.errorVisible(`impresoras.${i}.direccion`)}
                  data-campo={`impresoras.${i}.direccion`}
                />
              </div>
              <Checkbox checked={imp.activa} onChange={(e) => cambiarImpresora(i, "activa", e.target.checked)} etiqueta="Activa" />
            </div>
          ))}
          {impresoras.length < 10 && (
            <Button variante="terciario" tamano="sm" onClick={() => f.setForm((prev) => ({ ...prev, impresoras: [...prev.impresoras, nuevaImpresora()] }))}>
              <Plus size={14} aria-hidden="true" /> Agregar impresora
            </Button>
          )}
        </Seccion>
      </FormularioPantalla>
    </PantallaDetalle>
  );
}
