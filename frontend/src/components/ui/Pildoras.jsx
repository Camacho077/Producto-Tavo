/**
 * PÍLDORAS SEGMENTADAS (Hoy/Mes/Año, 1D/1S/1M/6M/1A).
 *
 * El indicador de la opción activa es UN solo elemento que se desliza con
 * `translateX`, nunca con `left` ni cambiando el fondo de cada botón (regla de
 * rendimiento 2b de la maqueta: solo transform y opacity).
 *
 * Cómo funciona: la rejilla reparte los botones en columnas iguales, el
 * indicador mide `(100% - padding) / n` y se desplaza `i * 100%` de su propio
 * ancho. Así el cálculo lo hace CSS con dos números —cuántas opciones y cuál
 * está activa— y el desplazamiento es una sola transformación compuesta por la
 * GPU, sin recalcular el layout.
 */
export default function Pildoras({ opciones, valor, onCambiar, etiqueta, compactas = false }) {
  const indice = Math.max(
    0,
    opciones.findIndex((o) => o.clave === valor)
  );

  return (
    <div
      className={`pildoras ${compactas ? "pildoras--compactas" : ""}`}
      role="group"
      aria-label={etiqueta}
      style={{ "--n": opciones.length, "--i": indice }}
    >
      <span className="pildoras__indicador" aria-hidden="true" />
      {opciones.map((opcion) => (
        <button
          key={opcion.clave}
          type="button"
          className="pildora"
          aria-pressed={opcion.clave === valor}
          title={opcion.titulo}
          onClick={() => {
            if (opcion.clave !== valor) onCambiar(opcion.clave);
          }}
        >
          {opcion.etiqueta}
        </button>
      ))}
    </div>
  );
}
