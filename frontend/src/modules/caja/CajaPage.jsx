import { useEffect, useMemo, useState } from "react";
import { Banknote, Lock, Minus, Plus, Receipt, Trash2, Wallet } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Seccion } from "@/components/FormularioPantalla";
import PantallaDetalle from "@/components/PantallaDetalle";
import { AccionesFila, BotonAccion, Button, Card, Checkbox, Detalle, Input, PageHeader, Select, Table, Textarea } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { useAuth } from "@/context/AuthContext";
import { MEDIOS_PAGO, etiquetaCortaTipoOrden, etiquetaMedioPago } from "@/config/restaurante";
import { useApiResource } from "@/hooks/useApiResource";
import { api } from "@/lib/api";
import { mensajeDeError } from "@/lib/errores";
import { formatearFechaHora, formatearHora, formatearMoneda, formatearNumero } from "@/lib/formato";
import { imprimirComprobante } from "@/lib/impresion";
import { MIGAS, migasDe } from "@/lib/migas";
import { aNumero, desglose } from "@/modules/caja/dinero";
import { ESTADOS } from "@/modules/ordenes/estados";

import "./caja.css";

/**
 * CAJA (fase 6, 2026-10-12): abrir la caja con su base, cobrar lo que está
 * por cobrar (uno o varios medios, propina voluntaria, dividir la cuenta) y
 * cerrarla contando por medio de pago. El comprobante es INTERNO: no es
 * factura electrónica (ver docs/DECISIONES.md, fase 6).
 */
const RUTA = "/caja";

// =====================================================================
// Inicio de caja
// =====================================================================
export function CajaInicio() {
  const navigate = useNavigate();
  const aviso = useAviso();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource(`${RUTA}/actual`);
  const puedeCobrar = puede("ventas", "crear");
  const caja = data?.caja;
  const { data: pendientes, recargar: recargarPendientes } = useApiResource(caja && puedeCobrar ? `${RUTA}/por-cobrar` : null);
  const [base, setBase] = useState("");
  const [abriendo, setAbriendo] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      recargar();
      if (caja && puedeCobrar) recargarPendientes();
    }, 20_000);
    return () => clearInterval(id);
  }, [recargar, recargarPendientes, caja, puedeCobrar]);

  const abrir = async (e) => {
    e.preventDefault();
    setAbriendo(true);
    try {
      await api.post(`${RUTA}/abrir`, { base_inicial: base || "0" });
      aviso.exito("Caja abierta");
      recargar();
    } catch (err) {
      aviso.error(mensajeDeError(err, "abrir la caja"));
    } finally {
      setAbriendo(false);
    }
  };

  if (error) return <p className="estado estado--error">{error}</p>;
  if (!data) return <PageHeader titulo="Caja" descripcion="Cargando…" migas={MIGAS.caja} />;

  if (!caja) {
    return (
      <div className="pantalla-estrecha">
        <PageHeader titulo="Caja" descripcion="La caja está cerrada. Ábrela con el efectivo que hay para devueltas." migas={MIGAS.caja} />
        {puede("caja", "cambiar_estado") ? (
          <form className="card formulario-pantalla" onSubmit={abrir} noValidate>
            <Seccion titulo="Abrir caja">
              <Input
                etiqueta="Base inicial (efectivo)"
                value={base}
                onChange={(e) => setBase(e.target.value)}
                permitir="decimal"
                cifra
                autoComplete="off"
                ayuda="Lo que hay en el cajón al empezar. Puede ser 0."
              />
            </Seccion>
            <div className="formulario-pantalla__pie">
              <Button type="submit" cargando={abriendo}>
                <Wallet size={16} aria-hidden="true" /> Abrir caja
              </Button>
            </div>
          </form>
        ) : (
          <p className="estado">Tu rol no puede abrir la caja: pídele a quien la maneja que la abra.</p>
        )}
      </div>
    );
  }

  const r = caja.resumen;
  return (
    <div>
      <PageHeader
        titulo={`Caja ${caja.numero}`}
        descripcion={`Abierta desde las ${formatearHora(caja.abierta_en)} por ${caja.abierta_por}`}
        migas={MIGAS.caja}
        acciones={
          puede("caja", "cambiar_estado") && (
            <Button variante="secundario" onClick={() => navigate(`${RUTA}/cierre`)}>
              <Lock size={14} aria-hidden="true" /> Cerrar caja
            </Button>
          )
        }
      />
      <div className="caja-cifras">
        <Card>
          <p className="caja-cifra__etiqueta">Vendido</p>
          <p className="caja-cifra__valor cifra">{formatearMoneda(r.total_ventas)}</p>
          <p className="caja-cifra__detalle">
            {formatearNumero(r.ventas)} cobros · impuesto {formatearMoneda(r.impuesto)}
          </p>
        </Card>
        <Card>
          <p className="caja-cifra__etiqueta">Efectivo esperado</p>
          <p className="caja-cifra__valor cifra">{formatearMoneda(r.esperado.efectivo ?? 0)}</p>
          <p className="caja-cifra__detalle">
            Base {formatearMoneda(r.base_inicial)} · gastos de caja {formatearMoneda(r.gastos_de_caja)}
          </p>
        </Card>
        <Card>
          <p className="caja-cifra__etiqueta">Propinas</p>
          <p className="caja-cifra__valor cifra">{formatearMoneda(r.propinas)}</p>
          <p className="caja-cifra__detalle">No son ingreso del restaurante</p>
        </Card>
      </div>
      <Card titulo="Por medio de pago">
        <div className="caja-medios">
          {Object.entries(r.esperado).map(([medio, valor]) => (
            <div key={medio}>
              <span>{etiquetaMedioPago(medio)}</span>
              <strong className="cifra">{formatearMoneda(valor)}</strong>
            </div>
          ))}
        </div>
      </Card>
      {puedeCobrar && (
        <div className="mt-4">
          <Card titulo="Por cobrar" descripcion="Órdenes con platos sin pagar, de la más antigua a la más reciente.">
            <Table
              columnas={[
                {
                  clave: "numero",
                  titulo: "Orden",
                  ajustar: true,
                  render: (o) => (
                    <Link to={`/ordenes/${o.id}`} className="enlace cifra">
                      #{o.numero}
                    </Link>
                  ),
                },
                {
                  clave: "destino",
                  titulo: "Mesa o cliente",
                  render: (o) => (o.mesa_nombre ? `Mesa ${o.mesa_nombre}` : o.cliente_nombre || etiquetaCortaTipoOrden(o.tipo)),
                },
                {
                  clave: "estado",
                  titulo: "Cocina",
                  ajustar: true,
                  render: (o) => ESTADOS[o.estado_cocina]?.etiqueta ?? "—",
                },
                {
                  clave: "platos",
                  titulo: "Platos",
                  cifra: true,
                  render: (o) => formatearNumero(o.platos),
                },
                {
                  clave: "por_cobrar",
                  titulo: "Por cobrar",
                  cifra: true,
                  render: (o) => formatearMoneda(o.por_cobrar),
                },
                {
                  clave: "created_at",
                  titulo: "Hora",
                  cifra: true,
                  render: (o) => formatearHora(o.created_at),
                },
                {
                  clave: "acciones",
                  titulo: "Acciones",
                  render: (o) => (
                    <AccionesFila>
                      <BotonAccion icono={Banknote} etiqueta={`Cobrar la orden #${o.numero}`} titulo="Cobrar" onClick={() => navigate(`${RUTA}/cobrar/${o.id}`)} />
                    </AccionesFila>
                  ),
                },
              ]}
              filas={pendientes ?? []}
              vacio="Nada por cobrar."
            />
          </Card>
        </div>
      )}
      {!puedeCobrar && <p className="estado mt-4">Tu rol puede ver la caja pero no cobrar.</p>}
    </div>
  );
}

// =====================================================================
// Cobrar
// =====================================================================
let secuencia = 0;
const nuevoPago = (medio, monto = "") => ({
  clave: `p${++secuencia}`,
  medio,
  monto,
  recibido: "",
});

export function Cobrar() {
  const { id } = useParams();
  const navigate = useNavigate();
  const aviso = useAviso();
  const { tenant } = useAuth();
  const config = tenant?.configuracion;
  const medios = MEDIOS_PAGO.filter((m) => !config?.medios_pago || config.medios_pago.includes(m.valor));
  const { data: orden, error } = useApiResource(`/ordenes/${id}`);
  const [cantidades, setCantidades] = useState(null);
  const [propina, setPropina] = useState("");
  const [pagos, setPagos] = useState(() => [nuevoPago(medios[0]?.valor ?? "efectivo")]);
  const [cliente, setCliente] = useState({
    nombre: "",
    documento_tipo: "",
    documento: "",
    correo: "",
  });
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState(null);

  const pendientes = useMemo(() => (orden ? orden.items.filter((i) => !i.anulado && !i.venta_id) : []), [orden]);
  // Por defecto se cobra todo lo pendiente; tocar un plato guarda la elección.
  const todo = useMemo(() => Object.fromEntries(pendientes.map((i) => [i.id, i.cantidad])), [pendientes]);
  const sel = cantidades ?? todo;
  const elegir = (id, n) => setCantidades((c) => ({ ...(c ?? todo), [id]: n }));
  const totalPlatos = pendientes.reduce((s, i) => s + Number(i.precio_unitario) * (sel[i.id] ?? 0), 0);
  const cuenta = desglose(totalPlatos, config);
  const valorPropina = aNumero(propina);
  const aPagar = Math.round((cuenta.total + valorPropina) * 100) / 100;
  const pagado = pagos.reduce((s, p) => s + aNumero(p.monto), 0);
  const falta = Math.round((aPagar - pagado) * 100) / 100;
  const sugerida = Number(config?.propina_sugerida ?? 10);
  const ninguno = !pendientes.some((i) => (sel[i.id] ?? 0) > 0);

  const cambiarPago = (clave, cambio) => setPagos((ps) => ps.map((p) => (p.clave === clave ? { ...p, ...cambio } : p)));
  const completar = (clave) =>
    cambiarPago(clave, {
      monto: String(Math.max(0, aNumero(pagos.find((p) => p.clave === clave).monto) + falta)),
    });

  const cobrar = async () => {
    setEnviando(true);
    setFallo(null);
    const todos = pendientes.every((i) => sel[i.id] === i.cantidad);
    const doc = cliente.documento.trim();
    try {
      const { data } = await api.post(`${RUTA}/cobros`, {
        orden_id: id,
        items: todos ? null : pendientes.filter((i) => sel[i.id] > 0).map((i) => ({ orden_item_id: i.id, cantidad: sel[i.id] })),
        propina: String(valorPropina),
        pagos: pagos
          .filter((p) => aNumero(p.monto) > 0)
          .map((p) => ({
            medio: p.medio,
            monto: String(aNumero(p.monto)),
            recibido: p.medio === "efectivo" && p.recibido ? String(aNumero(p.recibido)) : null,
          })),
        cliente:
          cliente.nombre.trim() || doc || cliente.correo.trim()
            ? {
                nombre: cliente.nombre.trim() || null,
                documento_tipo: doc ? cliente.documento_tipo || null : null,
                documento: doc || null,
                correo: cliente.correo.trim() || null,
              }
            : null,
      });
      aviso.exito(`Cobro ${data.codigo} registrado`);
      imprimirComprobante(data, tenant).catch((err) => aviso.error(err.message));
      navigate(`${RUTA}/ventas/${data.id}`);
    } catch (err) {
      const texto = mensajeDeError(err, "cobrar");
      setFallo(texto);
      aviso.error(texto);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={orden ? `Cobrar la orden #${orden.numero}` : "Cobrar"}
      descripcion={orden ? (orden.mesa_nombre ? `Mesa ${orden.mesa_nombre}` : orden.cliente_nombre || etiquetaCortaTipoOrden(orden.tipo)) : undefined}
      migas={migasDe(MIGAS.caja, {
        etiqueta: orden ? `Cobrar #${orden.numero}` : "Cobrar",
      })}
      error={error}
      datos={orden}
    >
      {orden && (
        <div className="caja-cobro">
          <div className="space-y-4">
            <Card titulo="Qué se cobra" descripcion="Para dividir la cuenta, desmarca platos o baja la cantidad: lo que quede se cobra después.">
              {!pendientes.length && <p className="estado">Esta orden no tiene nada por cobrar.</p>}
              <ul className="caja-platos">
                {pendientes.map((i) => {
                  const n = sel[i.id] ?? 0;
                  return (
                    <li key={i.id}>
                      <Checkbox
                        etiqueta={`${i.nombre}${i.modificadores.length ? ` (${i.modificadores.map((m) => m.nombre).join(", ")})` : ""}`}
                        checked={n > 0}
                        onChange={(e) => elegir(i.id, e.target.checked ? i.cantidad : 0)}
                      />
                      {i.cantidad > 1 && (
                        <span className="caja-cantidad">
                          <button type="button" onClick={() => elegir(i.id, Math.max(0, n - 1))} aria-label={`Uno menos de ${i.nombre}`} disabled={n === 0}>
                            <Minus size={16} aria-hidden="true" />
                          </button>
                          <span className="cifra">
                            {n}/{i.cantidad}
                          </span>
                          <button
                            type="button"
                            onClick={() => elegir(i.id, Math.min(i.cantidad, n + 1))}
                            aria-label={`Uno más de ${i.nombre}`}
                            disabled={n === i.cantidad}
                          >
                            <Plus size={16} aria-hidden="true" />
                          </button>
                        </span>
                      )}
                      <span className="cifra">{formatearMoneda(Number(i.precio_unitario) * n)}</span>
                    </li>
                  );
                })}
              </ul>
            </Card>
            <Card titulo="Cliente (opcional)" descripcion="Para el comprobante; lo pediría una factura electrónica.">
              <div className="grid gap-3">
                <div className="fila-campos">
                  <Input
                    etiqueta="Nombre"
                    value={cliente.nombre}
                    onChange={(e) => setCliente((c) => ({ ...c, nombre: e.target.value }))}
                    permitir="nombre"
                    maxLength={80}
                  />
                  <Input
                    etiqueta="Correo"
                    value={cliente.correo}
                    onChange={(e) => setCliente((c) => ({ ...c, correo: e.target.value }))}
                    permitir="correo"
                    maxLength={120}
                  />
                </div>
                <div className="fila-campos">
                  <Select
                    etiqueta="Tipo de documento"
                    value={cliente.documento_tipo}
                    onChange={(e) =>
                      setCliente((c) => ({
                        ...c,
                        documento_tipo: e.target.value,
                      }))
                    }
                  >
                    <option value="">—</option>
                    {["CC", "CE", "NIT", "PA", "TI"].map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </Select>
                  <Input
                    etiqueta="Número"
                    value={cliente.documento}
                    onChange={(e) => setCliente((c) => ({ ...c, documento: e.target.value }))}
                    permitir={cliente.documento_tipo === "NIT" ? "nit" : "alfanumerico"}
                  />
                </div>
              </div>
            </Card>
          </div>
          <aside className="space-y-4" aria-label="Cuenta">
            <Card titulo="Cuenta">
              <dl className="caja-cuenta">
                <dt>Base</dt>
                <dd className="cifra">{formatearMoneda(cuenta.subtotal)}</dd>
                {cuenta.impuesto > 0 && (
                  <>
                    <dt>Impuesto al consumo {cuenta.tasa} %</dt>
                    <dd className="cifra">{formatearMoneda(cuenta.impuesto)}</dd>
                  </>
                )}
                <dt className="caja-cuenta__total">Total</dt>
                <dd className="caja-cuenta__total cifra">{formatearMoneda(cuenta.total)}</dd>
              </dl>
              <div className="caja-propina">
                <Input etiqueta="Propina (voluntaria)" value={propina} onChange={(e) => setPropina(e.target.value)} permitir="decimal" cifra autoComplete="off" />
                <div className="caja-propina__botones">
                  <Button variante="terciario" tamano="sm" onClick={() => setPropina("")}>
                    Sin propina
                  </Button>
                  <Button variante="terciario" tamano="sm" onClick={() => setPropina(String(Math.round((cuenta.total * sugerida) / 100)))}>
                    {sugerida} %
                  </Button>
                </div>
              </div>
              <p className="caja-apagar">
                A pagar <strong className="cifra">{formatearMoneda(aPagar)}</strong>
              </p>
            </Card>
            <Card titulo="Pagos" descripcion="Se puede pagar con varios medios.">
              <ul className="caja-pagos">
                {pagos.map((p) => {
                  const cambio = p.medio === "efectivo" && p.recibido ? aNumero(p.recibido) - aNumero(p.monto) : null;
                  return (
                    <li key={p.clave}>
                      <div className="fila-campos">
                        <Select
                          etiqueta="Medio"
                          value={p.medio}
                          onChange={(e) =>
                            cambiarPago(p.clave, {
                              medio: e.target.value,
                              recibido: "",
                            })
                          }
                        >
                          {medios.map((m) => (
                            <option key={m.valor} value={m.valor}>
                              {m.etiqueta}
                            </option>
                          ))}
                        </Select>
                        <Input
                          etiqueta="Monto"
                          value={p.monto}
                          onChange={(e) => cambiarPago(p.clave, { monto: e.target.value })}
                          permitir="decimal"
                          cifra
                          autoComplete="off"
                        />
                      </div>
                      {p.medio === "efectivo" && (
                        <div className="fila-campos">
                          <Input
                            etiqueta="Recibido"
                            value={p.recibido}
                            onChange={(e) => cambiarPago(p.clave, { recibido: e.target.value })}
                            permitir="decimal"
                            cifra
                            autoComplete="off"
                          />
                          <p className="caja-devueltas" aria-live="polite">
                            {cambio === null ? (
                              ""
                            ) : cambio < 0 ? (
                              "▼ No alcanza"
                            ) : (
                              <>
                                Devueltas <strong className="cifra">{formatearMoneda(cambio)}</strong>
                              </>
                            )}
                          </p>
                        </div>
                      )}
                      <div className="caja-pago__acciones">
                        {falta !== 0 && (
                          <Button variante="terciario" tamano="sm" onClick={() => completar(p.clave)}>
                            {falta > 0 ? "Completar aquí" : "Ajustar aquí"}
                          </Button>
                        )}
                        {pagos.length > 1 && (
                          <Button variante="terciario" tamano="sm" onClick={() => setPagos((ps) => ps.filter((x) => x.clave !== p.clave))} aria-label="Quitar este pago">
                            <Trash2 size={14} aria-hidden="true" />
                          </Button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
              {pagos.length < 6 && (
                <Button
                  variante="secundario"
                  tamano="sm"
                  onClick={() =>
                    setPagos((ps) => [
                      ...ps,
                      nuevoPago(medios.find((m) => m.valor !== ps[ps.length - 1]?.medio)?.valor ?? medios[0].valor, falta > 0 ? String(falta) : ""),
                    ])
                  }
                >
                  <Plus size={14} aria-hidden="true" /> Otro medio
                </Button>
              )}
              <p className={`caja-falta ${falta === 0 ? "caja-falta--ok" : ""}`} aria-live="polite">
                {falta === 0 ? "Los pagos cuadran con la cuenta." : falta > 0 ? `Faltan ${formatearMoneda(falta)}` : `Sobran ${formatearMoneda(-falta)}`}
              </p>
              {fallo && (
                <p className="estado estado--error" role="alert">
                  {fallo}
                </p>
              )}
              <Button bloque onClick={cobrar} cargando={enviando} disabled={falta !== 0 || ninguno}>
                <Receipt size={16} aria-hidden="true" /> Cobrar {formatearMoneda(aPagar)}
              </Button>
            </Card>
          </aside>
        </div>
      )}
    </PantallaDetalle>
  );
}

// =====================================================================
// Cierre
// =====================================================================
export function CierreCaja() {
  const navigate = useNavigate();
  const aviso = useAviso();
  const { tenant } = useAuth();
  const { data, error } = useApiResource(`${RUTA}/actual`);
  const caja = data?.caja;
  const medios = MEDIOS_PAGO.filter((m) => !tenant?.configuracion?.medios_pago || tenant.configuracion.medios_pago.includes(m.valor) || caja?.resumen.esperado[m.valor]);
  const [contado, setContado] = useState({});
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState(null);

  const esperado = caja?.resumen.esperado ?? {};
  const filas = medios.map((m) => {
    const esp = Number(esperado[m.valor] ?? 0);
    const escrito = contado[m.valor];
    const cont = escrito === undefined || escrito === "" ? null : aNumero(escrito);
    return {
      ...m,
      esperado: esp,
      contado: cont,
      diferencia: cont === null ? null : Math.round((cont - esp) * 100) / 100,
    };
  });
  const completos = filas.every((f) => f.contado !== null);
  const diferencia = filas.reduce((s, f) => s + (f.diferencia ?? 0), 0);
  const descuadre = filas.some((f) => f.diferencia);

  const cerrar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setFallo(null);
    try {
      const { data: cerrada } = await api.post(`${RUTA}/cerrar`, {
        contado: Object.fromEntries(filas.map((f) => [f.valor, String(f.contado ?? 0)])),
        motivo_diferencia: motivo.trim() || null,
      });
      aviso.exito(`Caja ${cerrada.numero} cerrada`);
      navigate(`${RUTA}/cierres/${cerrada.id}`);
    } catch (err) {
      const texto = mensajeDeError(err, "cerrar la caja");
      setFallo(texto);
      aviso.error(texto);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="pantalla-estrecha">
      <PageHeader
        volver={RUTA}
        titulo={caja ? `Cerrar la caja ${caja.numero}` : "Cerrar la caja"}
        descripcion="Cuenta lo que hay por cada medio de pago."
        migas={migasDe(MIGAS.caja, { etiqueta: "Cierre" })}
      />
      {error && <p className="estado estado--error">{error}</p>}
      {data && !caja && <p className="estado">No hay ninguna caja abierta.</p>}
      {caja && (
        <form className="card formulario-pantalla" onSubmit={cerrar} noValidate>
          <Seccion
            titulo="Conteo"
            descripcion={`Efectivo esperado = base ${formatearMoneda(caja.resumen.base_inicial)} + cobros en efectivo − gastos pagados desde la caja.`}
          >
            <ul className="caja-conteo">
              {filas.map((f) => (
                <li key={f.valor}>
                  <span className="caja-conteo__medio">{f.etiqueta}</span>
                  <span className="caja-conteo__esperado cifra">Esperado {formatearMoneda(f.esperado)}</span>
                  <Input
                    aria-label={`Contado en ${f.etiqueta}`}
                    value={contado[f.valor] ?? ""}
                    onChange={(e) => setContado((c) => ({ ...c, [f.valor]: e.target.value }))}
                    permitir="decimal"
                    cifra
                    placeholder="Contado"
                    autoComplete="off"
                  />
                  <span className="caja-conteo__diferencia cifra">
                    {f.diferencia === null
                      ? "—"
                      : f.diferencia === 0
                        ? "Cuadra"
                        : `${f.diferencia > 0 ? "▲ Sobran" : "▼ Faltan"} ${formatearMoneda(Math.abs(f.diferencia))}`}
                  </span>
                </li>
              ))}
            </ul>
            {completos && (
              <p className="caja-falta" aria-live="polite">
                {descuadre ? `Diferencia total: ${diferencia > 0 ? "▲ +" : "▼ −"}${formatearMoneda(Math.abs(diferencia))}` : "La caja cuadra."}
              </p>
            )}
            {completos && descuadre && (
              <Textarea
                etiqueta="Motivo de la diferencia"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                maxLength={250}
                required
                ayuda="Obligatorio cuando no cuadra: queda en el reporte del cierre."
              />
            )}
          </Seccion>
          {fallo && (
            <p className="estado estado--error" role="alert">
              {fallo}
            </p>
          )}
          <div className="formulario-pantalla__pie">
            <Button variante="terciario" onClick={() => navigate(RUTA)} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" cargando={enviando} disabled={!completos || (descuadre && motivo.trim().length < 3)}>
              <Lock size={16} aria-hidden="true" /> Cerrar caja
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export function ResumenCaja({ caja }) {
  const r = caja.resumen;
  return (
    <Detalle
      campos={[
        { etiqueta: "Caja", valor: caja.numero, cifra: true },
        {
          etiqueta: "Abrió",
          valor: `${caja.abierta_por} · ${formatearFechaHora(caja.abierta_en)}`,
        },
        ...(caja.cerrada_en
          ? [
              {
                etiqueta: "Cerró",
                valor: `${caja.cerrada_por} · ${formatearFechaHora(caja.cerrada_en)}`,
              },
            ]
          : []),
        {
          etiqueta: "Base inicial",
          valor: formatearMoneda(r.base_inicial),
          cifra: true,
        },
        {
          etiqueta: "Cobros",
          valor: `${formatearNumero(r.ventas)}${r.ventas_anuladas ? ` (+${r.ventas_anuladas} anulados)` : ""}`,
          cifra: true,
        },
        {
          etiqueta: "Vendido",
          valor: formatearMoneda(r.total_ventas),
          cifra: true,
        },
        {
          etiqueta: "Impuesto al consumo",
          valor: formatearMoneda(r.impuesto),
          cifra: true,
        },
        {
          etiqueta: "Propinas",
          valor: formatearMoneda(r.propinas),
          cifra: true,
        },
        {
          etiqueta: "Gastos desde la caja",
          valor: formatearMoneda(r.gastos_de_caja),
          cifra: true,
        },
        ...(caja.diferencia !== null && caja.diferencia !== undefined
          ? [
              {
                etiqueta: "Diferencia",
                valor: Number(caja.diferencia) === 0 ? "Cuadró" : `${Number(caja.diferencia) > 0 ? "▲ +" : "▼ −"}${formatearMoneda(Math.abs(Number(caja.diferencia)))}`,
                cifra: true,
              },
            ]
          : []),
        ...(caja.motivo_diferencia ? [{ etiqueta: "Motivo", valor: caja.motivo_diferencia }] : []),
      ]}
    />
  );
}
