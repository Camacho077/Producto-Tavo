/**
 * Insignia de variación porcentual (▲ 12,4 % / ▼ 3,2 %), la `.badge` de la
 * maqueta.
 *
 * Con `valor` en null NO se pinta nada: el backend devuelve null cuando el
 * periodo anterior no tuvo movimiento, y ahí un porcentaje no significa nada.
 * Mostrar "+100 %" porque antes había cero sería inventar una cifra.
 */
export default function Variacion({ valor, className = "" }) {
  if (valor == null || !Number.isFinite(Number(valor))) return null;
  const numero = Number(valor);
  const sube = numero >= 0;
  return (
    <span className={`insignia ${sube ? "insignia--sube" : "insignia--baja"} ${className}`}>
      <span aria-hidden="true">{sube ? "▲" : "▼"}</span>
      <span className="cifra">
        {Math.abs(numero).toFixed(1).replace(".", ",")}%
      </span>
    </span>
  );
}
