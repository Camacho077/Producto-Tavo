import { useEffect } from "react";
import { CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";

import { useAvisos } from "@/context/AvisosContext";
import { useApiResource } from "@/hooks/useApiResource";
import { Skeleton } from "@/components/ui";
import { enlaceDeAviso } from "@/modules/dashboard/avisos";

/**
 * PANEL DE AVISOS — las cuatro fichas de la maqueta
 * (docs/dashboard-referencia.html) con los datos reales del negocio: stock
 * agotado o bajo el mínimo, subida o caída de ventas, pedidos sin avanzar y el
 * producto estrella de la semana. Las reglas las calcula el backend en
 * /dashboard/avisos; aquí solo se pintan.
 *
 * El NIVEL del aviso (crítico, advertencia, informativo, positivo) cambia el
 * color del punto y del borde, nunca la estructura de la ficha: así la lista se
 * lee igual de rápido tenga lo que tenga.
 *
 * Nunca queda vacío: si ninguna regla tiene algo que decir, lo dice. Mientras
 * llega la primera respuesta se muestra el marcador con la misma forma, y en
 * recargas posteriores se conservan los avisos actuales — nada parpadea.
 */
export default function PanelAvisos() {
  // Dentro del marco los avisos ya los pidió AvisosProvider (la barra
  // superior y el sidebar leen los mismos): aquí solo se refrescan al volver
  // al dashboard, reutilizando la petición en vuelo. Fuera del marco (pruebas
  // de la pantalla suelta) el panel los pide por su cuenta.
  const compartidos = useAvisos();
  const propios = useApiResource(compartidos ? null : "/dashboard/avisos");
  const { data, error } = compartidos ?? propios;
  const pedirCompartidos = compartidos?.pedir;
  useEffect(() => {
    pedirCompartidos?.();
  }, [pedirCompartidos]);

  if (error) {
    return (
      <ul className="avisos-rejilla">
        <li className="avisos-panel__vacio">No se pudieron cargar los avisos. {error}</li>
      </ul>
    );
  }

  if (!data) return <EsqueletoAvisos />;

  if (data.avisos.length === 0) {
    return (
      <ul className="avisos-rejilla">
        <li className="avisos-panel__vacio">
          <CheckCircle2 size={18} className="avisos-panel__vacio-icono" aria-hidden="true" />
          <span>Todo en orden: sin productos agotados, sin pedidos detenidos y sin caídas de ventas esta semana.</span>
        </li>
      </ul>
    );
  }

  return (
    <ul className="avisos-rejilla">
      {data.avisos.map((aviso) => (
        <Aviso key={aviso.clave} aviso={aviso} />
      ))}
    </ul>
  );
}

function Aviso({ aviso }) {
  const enlace = enlaceDeAviso(aviso.enlace);
  return (
    <li className={`aviso-item aviso-item--${aviso.nivel}`}>
      <span className="aviso-item__punto" aria-hidden="true" />
      <div className="aviso-item__cuerpo">
        <p className="aviso-item__titulo">{aviso.titulo}</p>
        <p className="aviso-item__texto">{aviso.texto}</p>
        {enlace && (
          <Link to={enlace.a} className="enlace aviso-item__enlace">
            {enlace.texto}
          </Link>
        )}
      </div>
    </li>
  );
}

function EsqueletoAvisos() {
  return (
    <ul className="avisos-rejilla" aria-busy="true" aria-label="Cargando avisos">
      {[0, 1, 2, 3].map((i) => (
        <li key={i} className="aviso-item">
          <span className="aviso-item__punto" aria-hidden="true" />
          <div className="aviso-item__cuerpo" style={{ flex: 1 }}>
            <Skeleton ancho={`${70 - i * 8}%`} alto="0.8em" />
            <Skeleton ancho="95%" alto="0.7em" style={{ marginTop: "0.5rem" }} />
            <Skeleton ancho="80%" alto="0.7em" style={{ marginTop: "0.3rem" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
