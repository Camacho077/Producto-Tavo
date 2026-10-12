import { useEffect, useId, useRef } from "react";

import { FILTROS, interceptarEntrada } from "@/lib/entrada";

// Teclado virtual sugerido para cada filtro (móvil); el bloqueo real lo hace
// interceptarEntrada en beforeinput/paste.
const INPUTMODE = {
  nombre: "text",
  entero: "numeric",
  decimal: "decimal",
  digitos: "numeric",
  alfanumerico: "text",
  sku: "text",
  nit: "numeric",
  telefono: "tel",
  documento_nit: "numeric",
  correo: "email",
  carta: "text",
  mesa: "text",
  cantidad: "decimal",
  costo: "decimal",
};

/**
 * Campo de texto del sistema.
 *  - `permitir`: filtro de entrada (ver lib/entrada.js): "nombre", "entero",
 *    "decimal", "digitos", "alfanumerico", "sku", "nit", "telefono",
 *    "correo", "carta" (nombres de la carta), "mesa". La tecla inválida no produce nada; el pegado se filtra; las
 *    máscaras (teléfono, NIT) se formatean solas sin mover el cursor.
 *    Con `permitir` el input es siempre type="text" (los type number/email
 *    no permiten controlar la posición del cursor).
 *  - `cifra` activa JetBrains Mono con tabular-nums: obligatorio en dinero y cantidades.
 *  - `required` pinta el asterisco de obligatorio junto a la etiqueta.
 *  - `error` pinta el mensaje en rojo bajo el campo y resalta el borde.
 */
export default function Input({
  etiqueta,
  error,
  ayuda,
  cifra = false,
  permitir,
  variante = "caja",
  required = false,
  id,
  className = "",
  type = "text",
  onBeforeInput,
  onPaste,
  ...props
}) {
  const idAuto = useId();
  const inputId = id || idAuto;
  const filtro = permitir ? FILTROS[permitir] : null;
  const ref = useRef(null);

  // Se escucha el `beforeinput` NATIVO (no el sintético de React, que se
  // deriva de keypress y no trae inputType ni data) y el `paste`.
  useEffect(() => {
    const input = ref.current;
    if (!input || !filtro) return undefined;
    const antes = (e) => interceptarEntrada(filtro, e);
    const pegar = (e) => interceptarEntrada(filtro, e);
    input.addEventListener("beforeinput", antes);
    input.addEventListener("paste", pegar);
    return () => {
      input.removeEventListener("beforeinput", antes);
      input.removeEventListener("paste", pegar);
    };
  }, [filtro]);

  return (
    <div className="campo">
      {etiqueta && (
        <label className="campo__etiqueta" htmlFor={inputId}>
          {etiqueta}
          {required && (
            <span className="campo__obligatorio" aria-hidden="true">
              {" "}*
            </span>
          )}
        </label>
      )}
      <input
        id={inputId}
        type={filtro ? "text" : type}
        inputMode={filtro ? INPUTMODE[permitir] : undefined}
        autoCapitalize={permitir === "correo" || permitir === "sku" ? "off" : undefined}
        className={`input ${variante === "linea" ? "input--linea" : ""} ${cifra ? "input--cifra" : ""} ${error ? "input--error" : ""} ${className}`}
        aria-invalid={error ? true : undefined}
        aria-required={required || undefined}
        aria-describedby={error ? `${inputId}-error` : ayuda ? `${inputId}-ayuda` : undefined}
        ref={ref}
        onBeforeInput={onBeforeInput}
        onPaste={onPaste}
        {...props}
      />
      {error && (
        <span className="campo__error" id={`${inputId}-error`} role="alert">
          {error}
        </span>
      )}
      {!error && ayuda && (
        <span className="campo__ayuda" id={`${inputId}-ayuda`}>
          {ayuda}
        </span>
      )}
    </div>
  );
}
