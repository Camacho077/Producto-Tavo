import Skeleton from "@/components/ui/Skeleton";

/** Marcador estático mientras llega el registro de una pantalla de detalle o edición. */
export default function PantallaCarga({ lineas = 6 }) {
  return (
    <div className="card p-5" role="status" aria-label="Cargando">
      <div className="grid grid-cols-2 gap-x-5 gap-y-4">
        {Array.from({ length: lineas }, (_, i) => (
          <div key={i}>
            <Skeleton ancho="40%" alto="0.6em" />
            <Skeleton ancho={`${55 + (i % 3) * 12}%`} alto="0.9em" style={{ marginTop: "0.5rem" }} />
          </div>
        ))}
      </div>
    </div>
  );
}
