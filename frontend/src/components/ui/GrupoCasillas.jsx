import { useId } from "react";

/**
 * Varias casillas que forman UN valor (lista): "tipos de orden habilitados",
 * "medios de pago". Va en un `<fieldset>` con su `<legend>`, así el lector de
 * pantalla anuncia el grupo antes de cada opción; el error se asocia al
 * grupo con `aria-describedby`.
 *
 * `opciones`: [{ valor, etiqueta, ayuda? }]. `valor`: lista de los elegidos,
 * que se devuelve SIEMPRE en el orden de `opciones` (no en el de los clics).
 */
export default function GrupoCasillas({ etiqueta, opciones, valor = [], onChange, onBlur, error, ayuda, required = false, campo }) {
  const id = useId();
  const elegidos = new Set(valor);
  const alternar = (v) => {
    const siguiente = new Set(elegidos);
    if (siguiente.has(v)) siguiente.delete(v);
    else siguiente.add(v);
    onChange(opciones.map((o) => o.valor).filter((x) => siguiente.has(x)));
  };
  const descripcion = error ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined;
  return (
    <fieldset className="grupo-casillas" aria-describedby={descripcion} aria-invalid={error ? true : undefined} data-campo={campo} onBlur={onBlur}>
      <legend className="campo__etiqueta">
        {etiqueta}
        {required && (
          <span className="campo__obligatorio" aria-hidden="true">
            {" "}*
          </span>
        )}
      </legend>
      <div className="grupo-casillas__opciones">
        {opciones.map((o) => (
          <label key={o.valor} className={`checkbox grupo-casillas__opcion${elegidos.has(o.valor) ? " grupo-casillas__opcion--elegida" : ""}`}>
            <input type="checkbox" checked={elegidos.has(o.valor)} onChange={() => alternar(o.valor)} />
            <span>
              {o.etiqueta}
              {o.ayuda && <span className="grupo-casillas__ayuda">{o.ayuda}</span>}
            </span>
          </label>
        ))}
      </div>
      {error && (
        <span className="campo__error" id={`${id}-error`} role="alert">
          {error}
        </span>
      )}
      {!error && ayuda && (
        <span className="campo__ayuda" id={`${id}-ayuda`}>
          {ayuda}
        </span>
      )}
    </fieldset>
  );
}
