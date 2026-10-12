import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui";

/**
 * Cuerpo de las pantallas de crear/editar: tarjeta con secciones y pie con
 * Cancelar (vuelve a `volver`) y Guardar (submit del formulario). El botón de
 * guardar se deshabilita mientras haya errores visibles.
 */
export default function FormularioPantalla({
  id,
  onSubmit,
  volver,
  refRaiz,
  hayErrores = false,
  guardando = false,
  textoGuardar = "Guardar",
  errorGeneral,
  children,
}) {
  const navigate = useNavigate();
  return (
    <form id={id} onSubmit={onSubmit} noValidate ref={refRaiz} className="card formulario-pantalla">
      {children}
      {/* role="alert": el lector de pantalla lo anuncia al aparecer (p. ej. el
          stock insuficiente de una venta, que se valida sin ir al backend). */}
      {errorGeneral && (
        <p className="estado estado--error" role="alert">
          {errorGeneral}
        </p>
      )}
      <div className="formulario-pantalla__pie">
        {hayErrores && <span className="formulario-pantalla__aviso">Hay campos con errores</span>}
        <Button variante="terciario" onClick={() => navigate(volver)} disabled={guardando}>
          Cancelar
        </Button>
        <Button type="submit" cargando={guardando} disabled={hayErrores} title={hayErrores ? "Corrige los errores marcados" : undefined}>
          {textoGuardar}
        </Button>
      </div>
    </form>
  );
}

/** Sección con título dentro de un formulario de pantalla. */
export function Seccion({ titulo, descripcion, children }) {
  return (
    <section className="formulario-seccion">
      {titulo && <h2 className="formulario-seccion__titulo">{titulo}</h2>}
      {descripcion && <p className="formulario-seccion__descripcion">{descripcion}</p>}
      {children}
    </section>
  );
}
