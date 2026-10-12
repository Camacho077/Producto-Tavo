import Spinner from "@/components/ui/Spinner";

/**
 * Estado de carga / error compartido: ninguna página falla en silencio.
 * Devuelve null cuando no hay nada que mostrar, para poder usarlo inline.
 */
export default function EstadoCarga({ cargando, error, textoCargando = "Cargando..." }) {
  if (cargando) {
    return (
      <p className="estado">
        <Spinner tamano="sm" />
        {textoCargando}
      </p>
    );
  }
  if (error) {
    return <p className="estado estado--error">{error}</p>;
  }
  return null;
}
