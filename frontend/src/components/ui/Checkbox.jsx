import { useId } from "react";

export default function Checkbox({ etiqueta, id, className = "", ...props }) {
  const idAuto = useId();
  const inputId = id || idAuto;

  return (
    <label className={`checkbox ${className}`} htmlFor={inputId}>
      <input id={inputId} type="checkbox" {...props} />
      {etiqueta}
    </label>
  );
}
