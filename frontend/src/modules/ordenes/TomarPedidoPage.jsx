import { useEffect, useMemo, useState } from "react";
import { Minus, Plus, Search, Send, Trash2 } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import FotoPlato from "@/components/FotoPlato";
import { Button, Card, Input, PageHeader, PantallaCarga } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { useAuth } from "@/context/AuthContext";
import { ORIGENES, TIPOS_ORDEN, etiquetaTipoOrden } from "@/config/restaurante";
import { useApiResource } from "@/hooks/useApiResource";
import { api } from "@/lib/api";
import { mensajeDeError } from "@/lib/errores";
import { formatearMoneda } from "@/lib/formato";
import { htmlComanda, impresoraPara, imprimir } from "@/lib/impresion";
import { MIGAS, migasDe } from "@/lib/migas";
import { ETIQUETA_MESA, destinoDeOrden } from "@/modules/ordenes/estados";

import "./ordenes.css";

/**
 * TOMAR EL PEDIDO (fase 4, 2026-10-12). Pensada para el dedo y para ser más
 * rápida que el papel: tocar un plato lo agrega, los modificadores son
 * fichas de un toque, la cantidad va con botones grandes. Una sola pantalla:
 * para quién (tipo y mesa), la carta y el pedido.
 *
 * El borrador vive en el navegador (localStorage) hasta que se envía: si se
 * cae el internet o se recarga la página, el pedido no se pierde.
 */
const CLAVE_BORRADOR = "orden-borrador";
const VACIO = { tipo: "local", origen: "local", mesa_id: "", cliente_nombre: "", cliente_telefono: "", cliente_direccion: "", nota: "" };

function leerBorrador() {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_BORRADOR)) ?? null;
  } catch {
    return null;
  }
}

function guardarBorrador(borrador) {
  try {
    if (borrador) localStorage.setItem(CLAVE_BORRADOR, JSON.stringify(borrador));
    else localStorage.removeItem(CLAVE_BORRADOR);
  } catch {
    /* sin almacenamiento (modo privado): el pedido vive solo en pantalla */
  }
}

let secuencia = 0;
const nuevaClave = () => `l${Date.now()}-${++secuencia}`;

function precioLinea(linea, producto) {
  if (!producto) return 0;
  const extras = producto.modificadores.filter((m) => m.tipo === "extra" && linea.mods.includes(m.id)).reduce((s, m) => s + Number(m.precio), 0);
  return (Number(producto.precio) + extras) * linea.cantidad;
}

export function OrdenNueva() {
  return <TomarPedido />;
}

export function OrdenAgregar() {
  const { id } = useParams();
  const { data: orden, error } = useApiResource(`/ordenes/${id}`);
  if (error) return <p className="estado estado--error">{error}</p>;
  if (!orden) return <PantallaCarga />;
  return <TomarPedido orden={orden} />;
}

function TomarPedido({ orden = null }) {
  const navigate = useNavigate();
  const aviso = useAviso();
  const { tenant } = useAuth();
  const [parametros] = useSearchParams();
  const config = tenant?.configuracion ?? {};
  const tiposHabilitados = TIPOS_ORDEN.filter((t) => !config.tipos_orden || config.tipos_orden.includes(t.valor));
  const origenesHabilitados = ORIGENES.filter((o) => !config.origenes || config.origenes.includes(o.valor));

  const [borrador] = useState(() => (orden ? null : leerBorrador()));
  const [datos, setDatos] = useState(() => {
    const base = borrador?.datos ?? { ...VACIO, tipo: tiposHabilitados[0]?.valor ?? "local" };
    const mesa = parametros.get("mesa");
    return mesa ? { ...base, tipo: "local", mesa_id: mesa } : base;
  });
  const [lineas, setLineas] = useState(() => borrador?.lineas ?? []);
  const [categoria, setCategoria] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState(null);
  const [errores, setErrores] = useState({});

  const { data: carta, error: errorCarta, recargar: recargarCarta } = useApiResource("/ordenes/carta");
  const { data: mesas } = useApiResource(orden ? null : "/ordenes/mesas");
  const productos = useMemo(() => Object.fromEntries((carta?.productos ?? []).map((p) => [p.id, p])), [carta]);

  useEffect(() => {
    if (!orden) guardarBorrador(lineas.length || datos.mesa_id || datos.cliente_nombre ? { datos, lineas } : null);
  }, [orden, datos, lineas]);

  const visibles = (carta?.productos ?? []).filter((p) => {
    if (busqueda.trim()) return p.nombre.toLowerCase().includes(busqueda.trim().toLowerCase());
    return !categoria || p.categoria_id === categoria;
  });
  const total = lineas.reduce((s, l) => s + precioLinea(l, productos[l.producto_id]), 0);
  const unidades = lineas.reduce((s, l) => s + l.cantidad, 0);

  const cambiar = (campo, valor) => {
    setDatos((d) => ({ ...d, [campo]: valor }));
    setErrores((e) => ({ ...e, [campo]: undefined }));
  };

  const agregar = (p) => {
    if (p.agotado_hoy) return;
    setFallo(null);
    setLineas((ls) => {
      // Tocar de nuevo un plato SIN modificadores ni nota suma uno.
      const igual = ls.find((l) => l.producto_id === p.id && l.mods.length === 0 && !l.nota);
      if (igual) return ls.map((l) => (l === igual ? { ...l, cantidad: Math.min(99, l.cantidad + 1) } : l));
      return [...ls, { clave: nuevaClave(), producto_id: p.id, cantidad: 1, mods: [], nota: "" }];
    });
  };
  const actualizar = (clave, cambio) => setLineas((ls) => ls.map((l) => (l.clave === clave ? { ...l, ...cambio } : l)));
  const quitar = (clave) => setLineas((ls) => ls.filter((l) => l.clave !== clave));

  const validar = () => {
    if (orden) return {};
    const e = {};
    if (datos.tipo === "local" && !datos.mesa_id) e.mesa_id = "Elige la mesa";
    if (datos.tipo === "domicilio") {
      if (!datos.cliente_direccion.trim()) e.cliente_direccion = "Escribe la dirección";
      if (!/^(3\d{9}|60\d{8})$/.test(datos.cliente_telefono.replace(/\s/g, ""))) e.cliente_telefono = "Celular de 10 dígitos (3…) o fijo con indicativo (60…)";
    }
    return e;
  };

  const enviar = async () => {
    const e = validar();
    setErrores(e);
    if (Object.keys(e).length || !lineas.length) return;
    setEnviando(true);
    setFallo(null);
    const items = lineas.map((l) => ({ producto_id: l.producto_id, cantidad: l.cantidad, modificador_ids: l.mods, nota: l.nota.trim() || null }));
    try {
      const { data } = orden
        ? await api.post(`/ordenes/${orden.id}/items`, { items })
        : await api.post("/ordenes", {
            ...datos,
            mesa_id: datos.tipo === "local" ? datos.mesa_id : null,
            cliente_telefono: datos.cliente_telefono.replace(/\s/g, "") || null,
            items,
          });
      guardarBorrador(null);
      const comanda = data.comandas[data.comandas.length - 1];
      aviso.exito(orden ? `Comanda ${comanda.numero} de la orden #${data.numero} enviada` : `Orden #${data.numero} enviada${comanda.va_a_cocina ? " a cocina" : ""}`);
      const impresora = impresoraPara(config, "comanda");
      if (impresora && comanda.va_a_cocina) {
        imprimir(
          htmlComanda(data, comanda.numero, { tipo: etiquetaTipoOrden(data.tipo), destino: destinoDeOrden(data), empresa: tenant?.nombre_empresa }),
          impresora
        ).catch((err) => aviso.error(err.message));
      }
      navigate(`/ordenes/${data.id}`);
    } catch (err) {
      const texto = mensajeDeError(err, orden ? "agregar los platos" : "enviar la orden");
      const datosError = err?.response?.data?.datos;
      const faltan = new Set((datosError?.faltantes ?? []).map((f) => f.insumo_id));
      const afectados = (datosError?.productos ?? []).filter((p) => p.insumo_ids.some((i) => faltan.has(i)));
      setFallo({ texto, afectados: [...new Map(afectados.map((p) => [p.producto_id, p])).values()] });
      aviso.error(texto);
    } finally {
      setEnviando(false);
    }
  };

  const agotar = async (p) => {
    try {
      await api.post("/ordenes/agotados", { producto_id: p.producto_id });
      setLineas((ls) => ls.filter((l) => l.producto_id !== p.producto_id));
      setFallo((f) => (f ? { ...f, afectados: f.afectados.filter((x) => x.producto_id !== p.producto_id) } : f));
      aviso.exito(`${p.nombre} quedó agotado hoy y salió del pedido`);
      recargarCarta();
    } catch (err) {
      aviso.error(mensajeDeError(err, `marcar ${p.nombre} como agotado`));
    }
  };

  const titulo = orden ? `Agregar a la orden #${orden.numero}` : "Tomar pedido";
  const volver = orden ? `/ordenes/${orden.id}` : "/ordenes";

  return (
    <div className="pedido">
      <PageHeader
        volver={volver}
        titulo={titulo}
        descripcion={orden ? `${destinoDeOrden(orden)} · sale una comanda solo con lo nuevo` : "Toca un plato para agregarlo. Los modificadores van con un toque."}
        migas={migasDe(MIGAS.ordenes, ...(orden ? [{ etiqueta: `#${orden.numero}`, a: volver }, { etiqueta: "Agregar" }] : [{ etiqueta: "Tomar pedido" }]))}
      />
      <div className="pedido__rejilla">
        <div className="pedido__principal">
          {!orden && (
            <Card titulo="¿Para quién?">
              <div className="pedido__tipos" role="radiogroup" aria-label="Tipo de orden">
                {tiposHabilitados.map((t) => (
                  <button
                    key={t.valor}
                    type="button"
                    role="radio"
                    aria-checked={datos.tipo === t.valor}
                    className={`pedido-opcion ${datos.tipo === t.valor ? "pedido-opcion--activa" : ""}`}
                    onClick={() => cambiar("tipo", t.valor)}
                  >
                    <span className="pedido-opcion__titulo">{t.etiqueta}</span>
                    <span className="pedido-opcion__ayuda">{t.ayuda}</span>
                  </button>
                ))}
              </div>
              {origenesHabilitados.length > 1 && (
                <div className="pedido__origenes" role="radiogroup" aria-label="Origen del pedido">
                  {origenesHabilitados.map((o) => (
                    <button
                      key={o.valor}
                      type="button"
                      role="radio"
                      aria-checked={datos.origen === o.valor}
                      className={`pedido-ficha ${datos.origen === o.valor ? "pedido-ficha--activa" : ""}`}
                      onClick={() => cambiar("origen", o.valor)}
                    >
                      {o.etiqueta}
                    </button>
                  ))}
                </div>
              )}
              {datos.tipo === "local" && (
                <SelectorMesa mesas={mesas} valor={datos.mesa_id} onElegir={(id) => cambiar("mesa_id", id)} error={errores.mesa_id} />
              )}
              <div className="fila-campos mt-3">
                <Input etiqueta="Cliente" value={datos.cliente_nombre} onChange={(e) => cambiar("cliente_nombre", e.target.value)} permitir="nombre" maxLength={80} ayuda="Opcional" autoComplete="off" />
                {datos.tipo !== "local" && (
                  <Input
                    etiqueta="Teléfono"
                    value={datos.cliente_telefono}
                    onChange={(e) => cambiar("cliente_telefono", e.target.value)}
                    permitir="telefono"
                    required={datos.tipo === "domicilio"}
                    error={errores.cliente_telefono}
                    autoComplete="off"
                  />
                )}
              </div>
              {datos.tipo === "domicilio" && (
                <Input
                  etiqueta="Dirección"
                  value={datos.cliente_direccion}
                  onChange={(e) => cambiar("cliente_direccion", e.target.value)}
                  maxLength={150}
                  required
                  error={errores.cliente_direccion}
                  autoComplete="off"
                />
              )}
            </Card>
          )}

          <Card titulo="Carta">
            {errorCarta && <p className="estado estado--error">{errorCarta}</p>}
            <label className="pedido__buscador">
              <Search size={16} aria-hidden="true" />
              <input type="search" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar plato…" aria-label="Buscar plato" />
            </label>
            <div className="pedido__categorias" role="tablist" aria-label="Categorías">
              {[{ id: "", nombre: "Todo" }, ...(carta?.categorias ?? [])].map((c) => (
                <button
                  key={c.id || "todo"}
                  type="button"
                  role="tab"
                  aria-selected={!busqueda && categoria === c.id}
                  className={`pedido-ficha ${!busqueda && categoria === c.id ? "pedido-ficha--activa" : ""}`}
                  onClick={() => {
                    setCategoria(c.id);
                    setBusqueda("");
                  }}
                >
                  {c.nombre}
                </button>
              ))}
            </div>
            {!carta && !errorCarta && <p className="text-[13px] text-[var(--texto-terciario)]">Cargando la carta…</p>}
            <div className="pedido__platos">
              {visibles.map((p) => {
                const enPedido = lineas.filter((l) => l.producto_id === p.id).reduce((s, l) => s + l.cantidad, 0);
                return (
                  <button
                    key={p.id}
                    type="button"
                    className={`pedido-plato ${p.agotado_hoy ? "pedido-plato--agotado" : ""}`}
                    onClick={() => agregar(p)}
                    disabled={p.agotado_hoy}
                    aria-label={`${p.nombre}, ${formatearMoneda(p.precio)}${p.agotado_hoy ? ", agotado hoy" : ""}${enPedido ? `, ${enPedido} en el pedido` : ""}`}
                  >
                    <FotoPlato producto={p} tamano={56} />
                    <span className="pedido-plato__nombre">{p.nombre}</span>
                    <span className="pedido-plato__precio cifra">{p.agotado_hoy ? "Agotado hoy" : formatearMoneda(p.precio)}</span>
                    {enPedido > 0 && <span className="pedido-plato__cantidad cifra" aria-hidden="true">{enPedido}</span>}
                  </button>
                );
              })}
              {carta && !visibles.length && <p className="text-[13px] text-[var(--texto-terciario)]">Ningún plato coincide.</p>}
            </div>
          </Card>
        </div>

        <aside className="pedido__resumen" aria-label="Pedido">
          <Card titulo={`Pedido${unidades ? ` · ${unidades}` : ""}`}>
            {!lineas.length && <p className="text-[13px] text-[var(--texto-terciario)]">Todavía no hay platos: toca uno en la carta.</p>}
            <ul className="pedido__lineas">
              {lineas.map((l) => {
                const p = productos[l.producto_id];
                if (!p) return null;
                return (
                  <li key={l.clave} className="pedido-linea">
                    <div className="pedido-linea__cabeza">
                      <span className="pedido-linea__nombre">{p.nombre}</span>
                      <span className="cifra">{formatearMoneda(precioLinea(l, p))}</span>
                    </div>
                    <div className="pedido-linea__controles">
                      <div className="pedido-cantidad">
                        <button type="button" onClick={() => (l.cantidad > 1 ? actualizar(l.clave, { cantidad: l.cantidad - 1 }) : quitar(l.clave))} aria-label={`Uno menos de ${p.nombre}`}>
                          {l.cantidad > 1 ? <Minus size={18} aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}
                        </button>
                        <span className="cifra" aria-live="polite">{l.cantidad}</span>
                        <button type="button" onClick={() => actualizar(l.clave, { cantidad: Math.min(99, l.cantidad + 1) })} aria-label={`Uno más de ${p.nombre}`}>
                          <Plus size={18} aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                    {p.modificadores.length > 0 && (
                      <div className="pedido-linea__mods" role="group" aria-label={`Modificadores de ${p.nombre}`}>
                        {p.modificadores.map((m) => {
                          const activo = l.mods.includes(m.id);
                          return (
                            <button
                              key={m.id}
                              type="button"
                              aria-pressed={activo}
                              className={`pedido-ficha pedido-ficha--mod ${activo ? "pedido-ficha--activa" : ""}`}
                              onClick={() => actualizar(l.clave, { mods: activo ? l.mods.filter((x) => x !== m.id) : [...l.mods, m.id] })}
                            >
                              {m.nombre}
                              {m.tipo === "extra" && Number(m.precio) > 0 ? ` +${formatearMoneda(m.precio)}` : ""}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    <input
                      className="pedido-linea__nota"
                      value={l.nota}
                      onChange={(e) => actualizar(l.clave, { nota: e.target.value.slice(0, 120) })}
                      placeholder="Nota para cocina (opcional)"
                      aria-label={`Nota de ${p.nombre}`}
                    />
                  </li>
                );
              })}
            </ul>
            {!orden && (
              <Input etiqueta="Nota de la orden" value={datos.nota} onChange={(e) => cambiar("nota", e.target.value)} maxLength={200} ayuda="Opcional: va en la comanda" />
            )}
            {fallo && (
              <div className="estado estado--error pedido__fallo" role="alert">
                <p>{fallo.texto}</p>
                {fallo.afectados.map((p) => (
                  <Button key={p.producto_id} variante="secundario" tamano="sm" onClick={() => agotar(p)}>
                    Marcar «{p.nombre}» agotado hoy
                  </Button>
                ))}
              </div>
            )}
          </Card>
          <div className="pedido__barra">
            <div>
              <span className="pedido__barra-etiqueta">{unidades ? `${unidades} plato${unidades === 1 ? "" : "s"}` : "Sin platos"}</span>
              <span className="pedido__barra-total cifra">{formatearMoneda(total)}</span>
            </div>
            <Button onClick={enviar} cargando={enviando} disabled={!lineas.length}>
              <Send size={16} aria-hidden="true" /> {orden ? "Enviar lo nuevo" : "Enviar orden"}
            </Button>
          </div>
        </aside>
      </div>

    </div>
  );
}

function SelectorMesa({ mesas, valor, onElegir, error }) {
  if (!mesas) return <p className="text-[13px] text-[var(--texto-terciario)] mt-3">Cargando mesas…</p>;
  if (!mesas.length) return <p className="estado estado--error mt-3">No hay mesas habilitadas: créalas en Ajustes → Mesas.</p>;
  const zonas = [...new Map(mesas.map((m) => [m.zona_nombre ?? "Sin zona", []])).keys()];
  return (
    <div className="mt-3">
      <p className="campo__etiqueta">¿Para qué mesa?</p>
      {zonas.map((z) => (
        <div key={z} className="mt-2">
          <p className="pedido__zona">{z}</p>
          <div className="mesas-rejilla" role="radiogroup" aria-label={`Mesas de ${z}`}>
            {mesas
              .filter((m) => (m.zona_nombre ?? "Sin zona") === z)
              .map((m) => (
                <button
                  key={m.id}
                  type="button"
                  role="radio"
                  aria-checked={valor === m.id}
                  className={`mesas-tile mesas-tile--${m.estado} ${valor === m.id ? "mesas-tile--elegida" : ""}`}
                  onClick={() => onElegir(m.id)}
                >
                  <span className="mesas-tile__nombre">{m.nombre}</span>
                  <span className="mesas-tile__estado">{ETIQUETA_MESA[m.estado]}</span>
                </button>
              ))}
          </div>
        </div>
      ))}
      {error && (
        <span className="campo__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
