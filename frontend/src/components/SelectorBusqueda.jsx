import { useEffect, useId, useRef, useState } from "react";
import { Search, X } from "lucide-react";

import { api } from "@/lib/api";

const RETARDO_MS = 250;

/**
 * Selector con búsqueda en vivo contra un endpoint paginado del backend.
 *  - `url`: endpoint de listado (acepta ?q=&por_pagina=).
 *  - `multiple`: permite elegir varios; los elegidos se muestran como fichas
 *    removibles debajo (quitar uno no toca los demás).
 *  - `valor`: con multiple, lista de {id, nombre, ...}; sin multiple, un objeto o null.
 *  - `etiquetaDe(item)`: texto a mostrar por ítem; `detalleDe(item)`: texto secundario.
 *
 * Accesibilidad (2026-09-30): patrón COMBOBOX de ARIA 1.2. El foco se queda
 * en el input; ↑/↓ mueven la opción activa (`aria-activedescendant`), Enter
 * la elige y Escape cierra. Las opciones son `<li role="option">` directos
 * del listbox (antes eran botones dentro de <li>, que rompía la estructura
 * que leen los lectores de pantalla) y "Buscando…"/"Sin resultados" van en
 * una región `role="status"` fuera de la lista.
 */
export default function SelectorBusqueda({
  url,
  valor,
  onCambiar,
  multiple = false,
  etiqueta,
  placeholder = "Buscar...",
  etiquetaDe = (x) => x.nombre,
  detalleDe = () => null,
  filtros = {},
  required = false,
  error,
  ayuda,
  nombreCampo,
}) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState([]);
  const [abierto, setAbierto] = useState(false);
  const [buscando, setBuscando] = useState(false);
  const [activa, setActiva] = useState(-1);
  const version = useRef(0);
  const contenedor = useRef(null);
  const filtrosClave = JSON.stringify(filtros);
  const id = useId();
  const idEtiqueta = `${id}-etiqueta`;
  const idLista = `${id}-lista`;
  const idNota = `${id}-nota`;
  const idOpcion = (i) => `${id}-opcion-${i}`;

  useEffect(() => {
    if (!abierto) return undefined;
    const actual = ++version.current;
    setBuscando(true);
    const temporizador = setTimeout(() => {
      api
        .get(url, { params: { q: texto.trim() || undefined, por_pagina: 20, ...JSON.parse(filtrosClave) } })
        .then((res) => {
          if (actual === version.current) {
            setResultados(res.data.items ?? []);
            setActiva(-1);
          }
        })
        .catch(() => {
          if (actual === version.current) setResultados([]);
        })
        .finally(() => {
          if (actual === version.current) setBuscando(false);
        });
    }, RETARDO_MS);
    return () => clearTimeout(temporizador);
  }, [texto, abierto, url, filtrosClave]);

  // Cerrar al hacer clic fuera.
  useEffect(() => {
    if (!abierto) return undefined;
    function fuera(e) {
      if (contenedor.current && !contenedor.current.contains(e.target)) setAbierto(false);
    }
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  const elegidos = multiple ? valor ?? [] : valor ? [valor] : [];
  const idsElegidos = new Set(elegidos.map((x) => x.id));
  const listaVisible = abierto && (multiple || !valor);

  function elegir(item) {
    if (idsElegidos.has(item.id)) return;
    if (multiple) {
      onCambiar([...elegidos, item]);
      setTexto("");
    } else {
      onCambiar(item);
      setTexto("");
      setAbierto(false);
    }
  }

  function quitar(idItem) {
    if (multiple) onCambiar(elegidos.filter((x) => x.id !== idItem));
    else onCambiar(null);
  }

  function alTeclear(e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!abierto) {
        setAbierto(true);
        return;
      }
      if (resultados.length === 0) return;
      const paso = e.key === "ArrowDown" ? 1 : -1;
      setActiva((a) => (a + paso + resultados.length) % resultados.length);
    } else if (e.key === "Enter" && listaVisible && activa >= 0 && resultados[activa]) {
      e.preventDefault();
      elegir(resultados[activa]);
    } else if (e.key === "Escape" && abierto) {
      e.preventDefault();
      setAbierto(false);
      setActiva(-1);
    }
  }

  // La opción activa siempre a la vista dentro de la lista con scroll.
  useEffect(() => {
    if (activa < 0) return;
    document.getElementById(idOpcion(activa))?.scrollIntoView?.({ block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activa]);

  const nota = !listaVisible ? "" : buscando && resultados.length === 0 ? "Buscando..." : !buscando && resultados.length === 0 ? "Sin resultados" : "";
  const describe = [error ? `${id}-error` : "", !error && ayuda ? `${id}-ayuda` : ""].filter(Boolean).join(" ") || undefined;

  return (
    <div className="campo" ref={contenedor}>
      {etiqueta && (
        <span className="campo__etiqueta" id={idEtiqueta}>
          {etiqueta}
          {required && (
            <span className="campo__obligatorio" aria-hidden="true">
              {" "}*
            </span>
          )}
        </span>
      )}

      {!multiple && valor ? (
        <div className="selector__elegido" data-campo={nombreCampo}>
          <span>{etiquetaDe(valor)}</span>
          {detalleDe(valor) && <span className="selector__detalle">{detalleDe(valor)}</span>}
          <button type="button" className="ficha__quitar" onClick={() => quitar(valor.id)} aria-label={`Quitar ${etiquetaDe(valor)}`}>
            <X size={13} aria-hidden="true" />
          </button>
        </div>
      ) : (
        <div className="buscador">
          <Search size={14} className="buscador__icono" aria-hidden="true" />
          <input
            type="text"
            role="combobox"
            className={`input buscador__input ${error ? "input--error" : ""}`}
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setAbierto(true);
            }}
            onFocus={() => setAbierto(true)}
            onKeyDown={alTeclear}
            placeholder={placeholder}
            aria-labelledby={etiqueta ? idEtiqueta : undefined}
            aria-label={etiqueta ? undefined : placeholder}
            aria-required={required || undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={describe}
            aria-expanded={listaVisible}
            aria-controls={idLista}
            aria-autocomplete="list"
            aria-activedescendant={listaVisible && activa >= 0 ? idOpcion(activa) : undefined}
            autoComplete="off"
            data-campo={nombreCampo}
          />
        </div>
      )}

      {listaVisible && resultados.length > 0 && (
        <ul className="selector__lista" role="listbox" id={idLista} aria-labelledby={etiqueta ? idEtiqueta : undefined} aria-label={etiqueta ? undefined : placeholder}>
          {resultados.map((item, i) => {
            const ya = idsElegidos.has(item.id);
            return (
              <li
                key={item.id}
                id={idOpcion(i)}
                role="option"
                aria-selected={ya}
                aria-disabled={ya || undefined}
                className={`selector__opcion ${ya ? "selector__opcion--elegida" : ""} ${i === activa ? "selector__opcion--activa" : ""}`}
                // mousedown sin blur: el foco se queda en el input.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => elegir(item)}
              >
                <span>{etiquetaDe(item)}</span>
                {ya ? <span className="selector__detalle">ya agregado</span> : detalleDe(item) && <span className="selector__detalle">{detalleDe(item)}</span>}
              </li>
            );
          })}
        </ul>
      )}
      <p className="selector__vacio" role="status" id={idNota} hidden={!nota}>
        {nota}
      </p>

      {multiple && elegidos.length > 0 && (
        <ul className="fichas" aria-label={etiqueta ? `${etiqueta}: elegidos` : "Elegidos"}>
          {elegidos.map((x) => (
            <li key={x.id} className="ficha">
              <span>{etiquetaDe(x)}</span>
              <button type="button" className="ficha__quitar" onClick={() => quitar(x.id)} aria-label={`Quitar ${etiquetaDe(x)}`}>
                <X size={12} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <span className="campo__error" role="alert" id={`${id}-error`}>
          {error}
        </span>
      )}
      {!error && ayuda && (
        <span className="campo__ayuda" id={`${id}-ayuda`}>
          {ayuda}
        </span>
      )}
    </div>
  );
}
