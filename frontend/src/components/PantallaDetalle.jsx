import { PageHeader, PantallaCarga } from "@/components/ui";

/**
 * Esqueleto común de las pantallas de detalle y edición: encabezado con
 * migas, flecha de volver y acciones, y debajo el contenido SOLO cuando el
 * registro ya llegó. Mientras tanto se muestra el marcador estático; nunca
 * un estado vacío ni un formulario en blanco que luego se rellena. En las
 * recargas posteriores (cambiar estado, seguimiento) el contenido actual se
 * queda tal cual hasta que llegan los datos nuevos.
 * `estrecha`: limita el ancho a 720px centrado (pantallas de editar).
 */
export default function PantallaDetalle({ titulo, descripcion, migas, volver, acciones, error, datos, estrecha = false, children }) {
  return (
    <div className={estrecha ? "pantalla-estrecha" : undefined}>
      <PageHeader titulo={titulo} descripcion={descripcion} migas={migas} volver={volver} acciones={datos ? acciones : null} />
      {error && <p className="estado estado--error">{error}</p>}
      {!error && !datos && <PantallaCarga />}
      {!error && datos && children}
    </div>
  );
}
