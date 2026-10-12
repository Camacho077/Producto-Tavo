/**
 * Marcadores de carga con la misma forma que el contenido final, para que el
 * layout no salte cuando llegan los datos. El brillo lo da .skeleton::after.
 */
export default function Skeleton({ ancho = "100%", alto = "0.8em", className = "", style }) {
  return <span className={`skeleton ${className}`} style={{ width: ancho, height: alto, display: "block", ...style }} aria-hidden="true" />;
}

const ANCHOS = ["70%", "45%", "55%", "40%", "60%", "35%", "50%"];

/**
 * Filas de tabla en carga. Es la MISMA tabla que ui/Table.jsx (mismo
 * <table class="tabla">, mismos títulos y clases por columna), no una rejilla
 * que la imita: así cada fila mide exactamente lo mismo que una real y nada
 * salta cuando llegan los datos. Antes era una rejilla de divs y medía 39 px
 * contra 46,7 px de la fila real.
 *
 * `columnas`: el mismo arreglo de columnas de la tabla (o un número, para
 * usos sueltos). La columna "acciones" lleva un marcador del alto de sus
 * botones, que son lo que fija la altura de la fila real.
 */
export function SkeletonTabla({ columnas = 5, filas = 6 }) {
  const cols =
    typeof columnas === "number"
      ? Array.from({ length: columnas }, (_, i) => ({ clave: `c${i}`, titulo: "" }))
      : columnas;
  const claseDe = (col) =>
    ["celda", col.cifra ? "celda--cifra" : "", col.cifra || col.ajustar || col.clave === "acciones" ? "celda--ajustada" : ""]
      .filter(Boolean)
      .join(" ");

  return (
    <div role="status" aria-label="Cargando registros" className="tabla-contenedor">
      <table className="tabla" aria-hidden="true">
        <thead>
          <tr>
            {cols.map((col) => (
              <th key={col.clave} className={claseDe(col)} scope="col">
                {col.titulo || <Skeleton ancho="3rem" alto="0.65em" style={{ margin: "0 auto" }} />}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: filas }, (_, f) => (
            <tr key={f}>
              {cols.map((col, c) => (
                <td key={col.clave} className={claseDe(col)}>
                  {col.clave === "acciones" ? (
                    <Skeleton ancho="4.5rem" alto="30px" style={{ margin: "0 auto", borderRadius: 8 }} />
                  ) : (
                    <Skeleton ancho={ANCHOS[(f + c) % ANCHOS.length]} style={{ margin: "0 auto" }} />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Tarjeta de cifra en carga (dashboard). */
export function SkeletonTarjeta({ lineas = 1, className = "" }) {
  return (
    <div className={`tarjeta ${className}`} style={{ padding: "1.125rem 1.25rem" }} role="status" aria-label="Cargando">
      <Skeleton ancho="40%" alto="0.65em" />
      <Skeleton className="skeleton--cifra" alto="1.9rem" ancho="58%" />
      {Array.from({ length: lineas }, (_, i) => (
        <Skeleton key={i} ancho={ANCHOS[i % ANCHOS.length]} alto="0.7em" style={{ marginTop: "0.6rem" }} />
      ))}
    </div>
  );
}
