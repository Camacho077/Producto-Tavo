import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

/**
 * Aviso fijo de "sin conexión" (fase 7, 2026-10-12). Se ve mientras el
 * navegador no tenga red y explica qué pasa con lo que se está escribiendo:
 * el pedido en curso se guarda en el equipo (TomarPedidoPage) y se envía
 * cuando vuelva el internet. No bloquea la pantalla.
 */
export default function SinConexion() {
  const [enLinea, setEnLinea] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  useEffect(() => {
    const arriba = () => setEnLinea(true);
    const abajo = () => setEnLinea(false);
    window.addEventListener("online", arriba);
    window.addEventListener("offline", abajo);
    return () => {
      window.removeEventListener("online", arriba);
      window.removeEventListener("offline", abajo);
    };
  }, []);
  if (enLinea) return null;
  return (
    <div className="sin-conexion" role="status">
      <WifiOff size={16} aria-hidden="true" />
      <span>
        <strong>Sin conexión.</strong> Lo que estás escribiendo se guarda en este equipo; envíalo cuando vuelva el internet.
      </span>
    </div>
  );
}
