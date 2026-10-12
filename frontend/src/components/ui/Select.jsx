import { useId } from "react";

export default function Select({ etiqueta, error, ayuda, id, className = "", required = false, children, ...props }) {
  const idAuto = useId();
  const selectId = id || idAuto;

  return (
    <div className="campo">
      {etiqueta && (
        <label className="campo__etiqueta" htmlFor={selectId}>
          {etiqueta}
          {required && (
            <span className="campo__obligatorio" aria-hidden="true">
              {" "}*
            </span>
          )}
        </label>
      )}
      <select
        id={selectId}
        className={`select ${error ? "select--error" : ""} ${className}`}
        aria-invalid={error ? true : undefined}
        aria-required={required || undefined}
        aria-describedby={error ? `${selectId}-error` : ayuda ? `${selectId}-ayuda` : undefined}
        {...props}
      >
        {children}
      </select>
      {error && (
        <span className="campo__error" id={`${selectId}-error`} role="alert">
          {error}
        </span>
      )}
      {!error && ayuda && (
        <span className="campo__ayuda" id={`${selectId}-ayuda`}>
          {ayuda}
        </span>
      )}
    </div>
  );
}
