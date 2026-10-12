import { useRef } from "react";

import useTablaApilada, { CLASE_TABLA_APILADA } from "@/hooks/useTablaApilada";

/**
 * Tabla del sistema: la ÚNICA tabla del producto (todo listado o matriz
 * pasa por aquí). Cada fila se convierte en tarjeta cuando la tabla NO CABE
 * en su contenedor o la pantalla mide menos de 768 px
 * (`hooks/useTablaApilada.js` + ui.css): por eso cada celda lleva
 * data-etiqueta. Así la página nunca se desplaza de lado.
 * Sin animaciones de filas: el contenido aparece de una vez y se queda.
 *
 * Columnas: { clave, titulo, cifra?, ajustar?, render? }
 * Alineación (decisión del 2026-09-19): TODO centrado, encabezado y
 * contenido, sin excepción por tipo de dato; vertical al centro en toda la
 * fila. El <th> y los <td> de una columna comparten clase y, por ser la
 * misma columna de la misma <table>, exactamente el mismo ancho.
 *  - `cifra: true`: JetBrains Mono con tabular-nums (números y montos).
 *  - `ajustar: true`, `cifra` y la columna "acciones": sin salto de línea.
 *  - Anchos proporcionales al contenido (2026-09-30): el espacio sobrante se
 *    reparte entre todas las columnas según lo que ocupa cada una.
 */
export default function Table({ columnas, filas, idFila = (f) => f.id, vacio = "Sin registros." }) {
  if (!filas || filas.length === 0) {
    return <p className="tabla__vacio">{vacio}</p>;
  }
  return <TablaConFilas columnas={columnas} filas={filas} idFila={idFila} />;
}

function TablaConFilas({ columnas, filas, idFila }) {
  const refContenedor = useRef(null);
  const apilada = useTablaApilada(refContenedor, filas);

  const claseDe = (col) =>
    ["celda", col.cifra ? "celda--cifra" : "", col.cifra || col.ajustar || col.clave === "acciones" ? "celda--ajustada" : ""].filter(Boolean).join(" ");

  return (
    <div ref={refContenedor} className={`tabla-contenedor${apilada ? ` ${CLASE_TABLA_APILADA}` : ""}`}>
      <table className="tabla">
        <thead>
          <tr>
            {columnas.map((col) => (
              <th key={col.clave} className={claseDe(col)} scope="col">
                {col.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={idFila(fila)}>
              {columnas.map((col) => (
                <td key={col.clave} data-etiqueta={col.titulo} className={claseDe(col)}>
                  {col.render ? col.render(fila) : fila[col.clave]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
