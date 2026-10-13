import { useCallback, useEffect, useRef, useState } from "react";
import { BellOff, BellRing, ChefHat, CircleCheck } from "lucide-react";

import { Button, PageHeader } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { useAuth } from "@/context/AuthContext";
import { etiquetaCortaTipoOrden } from "@/config/restaurante";
import { useApiResource } from "@/hooks/useApiResource";
import { api } from "@/lib/api";
import { mensajeDeError } from "@/lib/errores";
import { formatearHora, minutosDesde } from "@/lib/formato";

import "./cocina.css";

/**
 * PANTALLA DE COCINA (fase 5, 2026-10-12). Pensada para una tablet a un
 * metro: números y platos grandes, botones grandes, tres columnas. Consulta
 * cada 5 s (sin recargar la página) y los temporizadores avanzan cada 15 s;
 * pasado el tiempo de alerta de Ajustes la tarjeta cambia de tono (borde
 * grueso y cabecera invertida: sin color, como todo el producto).
 *
 * El aviso sonoro es opcional y lo activa quien está en cocina (los
 * navegadores no dejan sonar nada sin un toque previo).
 */
const CONSULTA_MS = 5000;
const RELOJ_MS = 15_000;
const CLAVE_SONIDO = "cocina-sonido";

const COLUMNAS = [
  { estado: "entrante", titulo: "Entrantes", vacio: "Nada nuevo por ahora." },
  { estado: "en_preparacion", titulo: "En preparación", vacio: "Nada en preparación." },
  { estado: "lista", titulo: "Listos", vacio: "Nada esperando al mesero." },
];

function leerSonido() {
  try {
    return localStorage.getItem(CLAVE_SONIDO) === "1";
  } catch {
    return false;
  }
}

/** Dos tonos cortos con Web Audio (sin archivos de sonido). */
function sonar(contexto) {
  if (!contexto) return;
  const t = contexto.currentTime;
  [0, 0.18].forEach((retraso, i) => {
    const osc = contexto.createOscillator();
    const vol = contexto.createGain();
    osc.frequency.value = i ? 1046 : 784;
    vol.gain.setValueAtTime(0.0001, t + retraso);
    vol.gain.exponentialRampToValueAtTime(0.25, t + retraso + 0.02);
    vol.gain.exponentialRampToValueAtTime(0.0001, t + retraso + 0.16);
    osc.connect(vol).connect(contexto.destination);
    osc.start(t + retraso);
    osc.stop(t + retraso + 0.17);
  });
}

export function Cocina() {
  const aviso = useAviso();
  const { puede } = useAuth();
  const { data, error, recargar } = useApiResource("/cocina/comandas");
  const [ahora, setAhora] = useState(() => Date.now());
  const [sonido, setSonido] = useState(leerSonido);
  const [moviendo, setMoviendo] = useState(null);
  const audio = useRef(null);
  const vistas = useRef(null);
  const puedeMover = puede("cocina", "cambiar_estado");

  useEffect(() => {
    const consulta = setInterval(() => document.visibilityState === "visible" && recargar(), CONSULTA_MS);
    const reloj = setInterval(() => setAhora(Date.now()), RELOJ_MS);
    return () => {
      clearInterval(consulta);
      clearInterval(reloj);
    };
  }, [recargar]);

  // Sonido al llegar una comanda nueva (no en la primera carga).
  useEffect(() => {
    if (!data) return;
    const ids = new Set(data.comandas.filter((c) => c.estado === "entrante").map((c) => c.id));
    if (vistas.current && sonido && data.sonido && [...ids].some((id) => !vistas.current.has(id))) sonar(audio.current);
    vistas.current = ids;
  }, [data, sonido]);

  const alternarSonido = () => {
    const nuevo = !sonido;
    setSonido(nuevo);
    try {
      localStorage.setItem(CLAVE_SONIDO, nuevo ? "1" : "0");
    } catch {
      /* sin almacenamiento: vale solo para esta sesión */
    }
    if (nuevo) {
      const Contexto = window.AudioContext || window.webkitAudioContext;
      if (Contexto && !audio.current) audio.current = new Contexto();
      sonar(audio.current);
    }
  };

  const mover = useCallback(
    async (comanda, accion) => {
      setMoviendo(comanda.id);
      try {
        await api.post(`/cocina/comandas/${comanda.id}/${accion}`);
        recargar();
      } catch (err) {
        aviso.error(mensajeDeError(err, accion === "tomar" ? "tomar la comanda" : "finalizar la comanda"));
        recargar();
      } finally {
        setMoviendo(null);
      }
    },
    [aviso, recargar]
  );

  const comandas = data?.comandas ?? [];
  const alerta = data?.alerta_minutos ?? 15;

  return (
    <div className="cocina">
      <PageHeader
        titulo="Cocina"
        descripcion={data ? `${comandas.filter((c) => c.estado !== "lista").length} por preparar · alerta a los ${alerta} min` : "Comandas en vivo"}
        acciones={
          data?.sonido !== false && (
            <Button variante="secundario" onClick={alternarSonido} aria-pressed={sonido}>
              {sonido ? <BellRing size={16} aria-hidden="true" /> : <BellOff size={16} aria-hidden="true" />}
              {sonido ? "Sonido activado" : "Activar sonido"}
            </Button>
          )
        }
      />
      {error && (
        <p className="estado estado--error" role="alert">
          {error}
        </p>
      )}
      {data?.avisos?.length > 0 && (
        <ul className="cocina-avisos" aria-label="Anulaciones recientes">
          {data.avisos.map((a) => (
            <li key={a.id}>
              <strong className="cifra">{formatearHora(a.created_at)}</strong> {a.texto}
            </li>
          ))}
        </ul>
      )}
      <div className="cocina-tablero">
        {COLUMNAS.map((col) => {
          const lista = comandas.filter((c) => c.estado === col.estado);
          return (
            <section key={col.estado} className="cocina-columna" aria-label={col.titulo}>
              <h2 className="cocina-columna__titulo">
                {col.titulo} <span className="cifra">{lista.length}</span>
              </h2>
              {data && !lista.length && <p className="cocina-columna__vacio">{col.vacio}</p>}
              {lista.map((c) => {
                const desde = c.estado === "lista" ? c.lista_en : c.created_at;
                const minutos = minutosDesde(desde, ahora);
                const tarde = c.estado !== "lista" && minutosDesde(c.created_at, ahora) >= alerta;
                return (
                  <article key={c.id} className={`cocina-tarjeta ${tarde ? "cocina-tarjeta--tarde" : ""}`} aria-label={`Orden ${c.orden_numero}`}>
                    <header className="cocina-tarjeta__cabeza">
                      <span className="cocina-tarjeta__numero cifra">#{c.orden_numero}</span>
                      <span className="cocina-tarjeta__destino">
                        {c.destino}
                        <small>
                          {etiquetaCortaTipoOrden(c.tipo)}
                          {c.numero > 1 ? ` · agregado ${c.numero}` : ""}
                        </small>
                      </span>
                      <span className="cocina-tarjeta__tiempo cifra" title={c.estado === "lista" ? "Desde que quedó lista" : "Desde que entró"}>
                        {tarde && "▲ "}
                        {minutos} min
                      </span>
                    </header>
                    <ul className="cocina-tarjeta__platos">
                      {c.items.map((i) => (
                        <li key={i.id} className={i.anulado ? "cocina-plato cocina-plato--anulado" : "cocina-plato"}>
                          <span className="cocina-plato__nombre">
                            {i.cantidad}× {i.nombre}
                          </span>
                          {i.modificadores.map((m) => (
                            <span key={m.id} className="cocina-plato__mod">
                              {m.tipo === "sin" ? "– " : "+ "}
                              {m.nombre.toUpperCase()}
                            </span>
                          ))}
                          {i.nota && <span className="cocina-plato__nota">» {i.nota}</span>}
                          {i.anulado && <span className="cocina-plato__nota">Anulado: {i.anulado_motivo}</span>}
                        </li>
                      ))}
                    </ul>
                    {c.nota && <p className="cocina-tarjeta__nota">Nota: {c.nota}</p>}
                    <footer className="cocina-tarjeta__pie">
                      <span>
                        {c.mesero_nombre}
                        {c.tomada_por && c.estado !== "entrante" && ` · ${c.tomada_por}`}
                      </span>
                      {puedeMover && c.estado === "entrante" && (
                        <Button tamano="lg" onClick={() => mover(c, "tomar")} cargando={moviendo === c.id}>
                          <ChefHat size={18} aria-hidden="true" /> Tomar
                        </Button>
                      )}
                      {puedeMover && c.estado === "en_preparacion" && (
                        <Button tamano="lg" onClick={() => mover(c, "finalizar")} cargando={moviendo === c.id}>
                          <CircleCheck size={18} aria-hidden="true" /> Finalizar
                        </Button>
                      )}
                      {c.estado === "lista" && <span className="cocina-tarjeta__espera">Espera al mesero</span>}
                    </footer>
                  </article>
                );
              })}
            </section>
          );
        })}
      </div>
    </div>
  );
}
