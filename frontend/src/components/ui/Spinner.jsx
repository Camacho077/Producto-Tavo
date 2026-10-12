/** Spinner propio del sistema: hereda el color del contexto (currentColor). */
export default function Spinner({ tamano = "md", className = "", ...props }) {
  return (
    <span
      className={`spinner spinner--${tamano} ${className}`}
      role="status"
      aria-label="Cargando"
      {...props}
    />
  );
}
