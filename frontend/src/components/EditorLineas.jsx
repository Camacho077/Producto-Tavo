import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui";

let siguiente = 0;
/** Id local estable para la `key` de una fila nueva (no viaja al backend). */
export const idLocal = () => `l-${Date.now()}-${siguiente++}`;

/**
 * Editor de líneas de un formulario: receta, modificadores, platos de un
 * combo, insumos de una compra. Una rejilla por fila; las etiquetas visibles
 * van en la PRIMERA fila y las demás llevan `aria-label` ("Cantidad de la
 * línea 3"), como el editor de ítems heredado.
 *
 * `columnas`: [{ clave, etiqueta, ancho, render({ fila, i, cambiar, etiqueta, ariaLabel }) }]
 *   - `ancho`: tramo de la rejilla ("minmax(0, 1fr)", "6rem"…).
 *   - `render` recibe `etiqueta` (solo en la fila 0) y `ariaLabel` (en el resto).
 * `debajo(fila, i)`: nota opcional bajo cada fila (subtotal, costo).
 * Las filas aparecen y se van de una vez, sin animación (como el heredado).
 */
export default function EditorLineas({
  filas,
  onCambiar,
  nueva,
  columnas,
  textoAgregar = "Agregar línea",
  quitarEtiqueta = "Quitar línea",
  minimo = 0,
  maximo = 40,
  debajo,
  pie,
  vacio,
}) {
  const plantilla = `${columnas.map((c) => c.ancho ?? "minmax(0, 1fr)").join(" ")} auto`;
  const cambiarFila = (i) => (campo, valor) =>
    onCambiar(filas.map((f, j) => (j === i ? (typeof campo === "object" ? { ...f, ...campo } : { ...f, [campo]: valor }) : f)));

  return (
    <div className="lineas">
      {filas.length === 0 && vacio && <p className="lineas__vacio">{vacio}</p>}
      {filas.map((fila, i) => (
        <div key={fila._id ?? fila.id ?? i}>
          <div className="lineas__fila" style={{ "--lineas-columnas": plantilla }}>
            {columnas.map((col) => (
              <div key={col.clave} className="lineas__celda">
                {col.render({
                  fila,
                  i,
                  cambiar: cambiarFila(i),
                  etiqueta: i === 0 ? col.etiqueta : undefined,
                  ariaLabel: i === 0 ? undefined : `${col.etiqueta} de la línea ${i + 1}`,
                })}
              </div>
            ))}
            <Button
              variante="terciario"
              soloIcono
              onClick={() => onCambiar(filas.filter((_, j) => j !== i))}
              disabled={filas.length <= minimo}
              aria-label={`${quitarEtiqueta} ${i + 1}`}
              title={quitarEtiqueta}
              className="lineas__quitar"
            >
              <Trash2 size={14} />
            </Button>
          </div>
          {debajo && <div className="lineas__nota">{debajo(fila, i)}</div>}
        </div>
      ))}
      {filas.length < maximo && (
        <Button variante="terciario" tamano="sm" onClick={() => onCambiar([...filas, { ...nueva(), _id: idLocal() }])}>
          <Plus size={14} aria-hidden="true" /> {textoAgregar}
        </Button>
      )}
      {pie && <div className="lineas__pie">{pie}</div>}
    </div>
  );
}
