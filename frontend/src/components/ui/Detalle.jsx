/**
 * Pares etiqueta / valor de las pantallas de detalle: una fila por dato,
 * etiqueta a la izquierda con ancho fijo y valor alineado en la misma
 * vertical. `campos`: [{ etiqueta, valor, cifra? }] (`ancho` se acepta por
 * compatibilidad y no cambia nada: todas las filas son completas).
 */
export default function Detalle({ campos }) {
  return (
    <dl className="detalle">
      {campos.map(({ etiqueta, valor, cifra = false }) => (
        <div key={etiqueta} className="detalle__campo">
          <dt className="detalle__etiqueta">{etiqueta}</dt>
          <dd className={`detalle__valor ${cifra ? "cifra" : ""}`}>
            {valor === null || valor === undefined || valor === "" ? <span className="text-[var(--texto-terciario)]">—</span> : valor}
          </dd>
        </div>
      ))}
    </dl>
  );
}
