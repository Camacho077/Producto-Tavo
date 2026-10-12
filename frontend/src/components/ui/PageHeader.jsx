import { ArrowLeft, ChevronRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";

/**
 * Encabezado de página: migas de pan para volver, título y descripción a la
 * izquierda, botones de acción arriba a la derecha.
 * `migas`: [{ etiqueta, a }] — el último elemento es la pantalla actual (sin enlace).
 * `volver`: ruta del listado del módulo; pinta la flecha de retroceder junto
 * al título (obligatoria en crear, editar y ver detalle).
 */
export default function PageHeader({ titulo, descripcion, acciones, migas, volver }) {
  const navigate = useNavigate();
  return (
    <header className="encabezado-pagina">
      {migas?.length > 0 && (
        <nav className="migas" aria-label="Ruta de navegación">
          <ol>
            {migas.map((m, i) => (
              <li key={`${m.etiqueta}-${i}`}>
                {m.a && i < migas.length - 1 ? <Link to={m.a}>{m.etiqueta}</Link> : <span aria-current="page">{m.etiqueta}</span>}
                {i < migas.length - 1 && <ChevronRight size={12} aria-hidden="true" />}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="encabezado-pagina__fila">
        <div className="encabezado-pagina__titulo-bloque">
          {volver && (
            <Button variante="terciario" soloIcono onClick={() => navigate(volver)} aria-label="Volver al listado" title="Volver al listado" className="encabezado-pagina__volver">
              <ArrowLeft size={16} />
            </Button>
          )}
          <div className="min-w-0">
            <h1 className="encabezado-pagina__titulo">{titulo}</h1>
            {descripcion && <p className="encabezado-pagina__descripcion">{descripcion}</p>}
          </div>
        </div>
        {acciones && <div className="encabezado-pagina__acciones">{acciones}</div>}
      </div>
    </header>
  );
}
