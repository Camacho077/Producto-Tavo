import { Plus, Trash2 } from "lucide-react";

import { Button, Input, Select } from "@/components/ui";
import { formatearMoneda } from "@/lib/formato";
import { CANTIDAD_MAX } from "@/lib/validaciones";

export const ITEM_VACIO = { producto_id: "", cantidad: "1", precio_unitario: "" };

export function totalDeItems(items) {
  return items.reduce((acc, it) => acc + (Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0), 0);
}

/**
 * Editor de líneas para compras, ventas y pedidos: agregar/quitar productos
 * con subtotal por línea y total en vivo. Al elegir un producto se sugiere
 * el precio (`precioSugerido(producto)`), editable.
 *
 * `errorDe(indice, campo)` y `alSalir(indice, campo)` conectan cada línea con
 * useFormulario (rutas "items.<i>.<campo>"). Las líneas aparecen y
 * desaparecen de una vez, sin animación.
 */
export default function ItemsEditor({
  items,
  onCambiar,
  productos,
  precioSugerido = (p) => p.precio,
  mostrarStock = false,
  etiquetaPrecio = "Precio unitario",
  errorDe = () => undefined,
  alSalir = () => {},
}) {
  function actualizar(indice, campo, valor) {
    onCambiar(
      items.map((it, i) => {
        if (i !== indice) return it;
        const actualizado = { ...it, [campo]: valor };
        if (campo === "producto_id") {
          const producto = productos.find((p) => p.id === valor);
          if (producto && !it.precio_unitario) {
            actualizado.precio_unitario = String(precioSugerido(producto) ?? "");
          }
        }
        return actualizado;
      })
    );
  }

  const total = totalDeItems(items);

  return (
    <div className="space-y-3">
      {items.map((item, i) => {
          const subtotal = (Number(item.cantidad) || 0) * (Number(item.precio_unitario) || 0);
          return (
            <div key={item._id ?? i}>
              <div className="items-editor__fila">
                <Select
                  etiqueta={i === 0 ? "Producto" : undefined}
                  value={item.producto_id}
                  onChange={(e) => actualizar(i, "producto_id", e.target.value)}
                  onBlur={() => alSalir(i, "producto_id")}
                  error={errorDe(i, "producto_id")}
                  required={i === 0}
                  data-campo={`items.${i}.producto_id`}
                  aria-label={i === 0 ? undefined : `Producto de la línea ${i + 1}`}
                >
                  <option value="">Producto...</option>
                  {productos.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre}
                      {mostrarStock ? ` (stock: ${p.stock})` : ""}
                    </option>
                  ))}
                </Select>
                <Input
                  etiqueta={i === 0 ? "Cantidad" : undefined}
                  cifra
                  permitir="entero"
                  maxLength={String(CANTIDAD_MAX).length}
                  value={item.cantidad}
                  onChange={(e) => actualizar(i, "cantidad", e.target.value)}
                  onBlur={() => alSalir(i, "cantidad")}
                  error={errorDe(i, "cantidad")}
                  required={i === 0}
                  data-campo={`items.${i}.cantidad`}
                  aria-label={i === 0 ? undefined : `Cantidad de la línea ${i + 1}`}
                />
                <Input
                  etiqueta={i === 0 ? etiquetaPrecio : undefined}
                  cifra
                  permitir="decimal"
                  value={item.precio_unitario}
                  onChange={(e) => actualizar(i, "precio_unitario", e.target.value)}
                  onBlur={() => alSalir(i, "precio_unitario")}
                  error={errorDe(i, "precio_unitario")}
                  required={i === 0}
                  data-campo={`items.${i}.precio_unitario`}
                  aria-label={i === 0 ? undefined : `${etiquetaPrecio} de la línea ${i + 1}`}
                />
                <Button
                  variante="terciario"
                  soloIcono
                  onClick={() => onCambiar(items.filter((_, idx) => idx !== i))}
                  disabled={items.length === 1}
                  aria-label="Quitar producto"
                  title="Quitar producto"
                >
                  <Trash2 size={14} />
                </Button>
              </div>
              <p className="items-editor__subtotal">
                Subtotal: <span className="cifra">{formatearMoneda(subtotal)}</span>
              </p>
            </div>
          );
        })}

      <Button variante="terciario" tamano="sm" onClick={() => onCambiar([...items, { ...ITEM_VACIO, _id: `${Date.now()}-${items.length}` }])}>
        <Plus size={14} /> Agregar producto
      </Button>

      <div className="items-editor__total">
        <span>
          {items.length} {items.length === 1 ? "línea" : "líneas"}
        </span>
        <span>
          Total: <strong className="cifra">{formatearMoneda(total)}</strong>
        </span>
      </div>
    </div>
  );
}
