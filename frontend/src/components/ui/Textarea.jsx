import { useId } from "react";

/**
 * Área de texto con contador visible cuando hay `maxLength`.
 *
 * Accesibilidad (2026-09-30): el error o la ayuda y el contador forman la
 * descripción del campo (se leen al entrar). El contador ya NO es una región
 * viva: con `aria-live` el lector anunciaba "12/500", "13/500"… en cada
 * tecla. Solo se anuncia una vez, al llegar al tope.
 */
export default function Textarea({ etiqueta, error, ayuda, id, className = "", filas = 3, required = false, maxLength, value, ...props }) {
  const idAuto = useId();
  const textareaId = id || idAuto;
  const largo = String(value ?? "").length;
  const enTope = Boolean(maxLength) && largo >= maxLength;
  const describe =
    [error ? `${textareaId}-error` : ayuda ? `${textareaId}-ayuda` : "", maxLength ? `${textareaId}-contador` : ""].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className="campo">
      {etiqueta && (
        <label className="campo__etiqueta" htmlFor={textareaId}>
          {etiqueta}
          {required && (
            <span className="campo__obligatorio" aria-hidden="true">
              {" "}*
            </span>
          )}
        </label>
      )}
      <textarea
        id={textareaId}
        rows={filas}
        maxLength={maxLength}
        value={value}
        className={`input textarea ${error ? "input--error" : ""} ${className}`}
        aria-invalid={error ? true : undefined}
        aria-required={required || undefined}
        aria-describedby={describe}
        {...props}
      />
      <div className="campo__pie">
        {error ? (
          <span className="campo__error" id={`${textareaId}-error`} role="alert">
            {error}
          </span>
        ) : (
          <span className="campo__ayuda" id={ayuda ? `${textareaId}-ayuda` : undefined}>
            {ayuda}
          </span>
        )}
        {maxLength && (
          <span id={`${textareaId}-contador`} className={`campo__contador cifra ${enTope ? "campo__contador--tope" : ""}`}>
            <span aria-hidden="true">
              {largo}/{maxLength}
            </span>
            <span className="sr-only">
              {largo} de {maxLength} caracteres
            </span>
          </span>
        )}
      </div>
      <span className="sr-only" role="status">
        {enTope ? `Llegaste al máximo de ${maxLength} caracteres.` : ""}
      </span>
    </div>
  );
}
