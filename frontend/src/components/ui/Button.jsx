import Spinner from "@/components/ui/Spinner";

/**
 * Único botón del producto. Variantes: primario (verde de acento), secundario
 * (acero azulado), terciario (fantasma) y destructivo.
 *
 * Todos los estados están cubiertos en ui.css: hover, active (scale .98),
 * foco visible (anillo de 3px al 18% del color propio de la variante),
 * deshabilitado y cargando (con spinner propio).
 */
export default function Button({
  variante = "primario",
  tamano = "md",
  cargando = false,
  bloque = false,
  soloIcono = false,
  disabled = false,
  type = "button",
  className = "",
  children,
  ...props
}) {
  const clases = [
    "btn",
    `btn--${variante}`,
    `btn--${tamano}`,
    bloque ? "btn--bloque" : "",
    soloIcono ? "btn--icono" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type={type}
      className={clases}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      {...props}
    >
      {/* Decorativo: el estado ya lo comunica aria-busy en el botón */}
      {cargando && (
        <Spinner
          tamano={tamano === "lg" ? "md" : "sm"}
          role={undefined}
          aria-label={undefined}
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
}
