import { Search, X } from "lucide-react";

/** Caja de búsqueda de los listados. Misma altura y estilo que <Input>. */
export default function Buscador({ valor, onCambiar, placeholder = "Buscar...", className = "" }) {
  return (
    <div className={`buscador ${className}`}>
      <Search size={14} className="buscador__icono" aria-hidden="true" />
      <input
        type="search"
        className="input buscador__input"
        value={valor}
        onChange={(e) => onCambiar(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
      {valor && (
        <button
          type="button"
          className="buscador__limpiar"
          onClick={() => onCambiar("")}
          aria-label="Limpiar búsqueda"
        >
          <X size={13} />
        </button>
      )}
    </div>
  );
}
