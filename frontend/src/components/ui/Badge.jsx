export default function Badge({ variante = "neutro", children, className = "", ...props }) {
  return (
    <span className={`badge badge--${variante} ${className}`} {...props}>
      {children}
    </span>
  );
}

/** Mapea los estados de negocio (compras, ventas y pedidos) a la variante visual. */
export function varianteDeEstado(estado) {
  switch (estado) {
    case "confirmada":
    case "completada":
    case "entregado":
    case "listo":
      return "positivo";
    case "cancelada":
    case "cancelado":
    case "anulada":
      return "negativo";
    case "pendiente":
      return "advertencia";
    case "en_proceso":
      return "acento";
    default:
      return "neutro";
  }
}

const ETIQUETAS = {
  pendiente: "Pendiente",
  confirmada: "Confirmada",
  completada: "Completada",
  cancelada: "Cancelada",
  cancelado: "Cancelado",
  anulada: "Anulada",
  en_proceso: "En proceso",
  listo: "Listo",
  entregado: "Entregado",
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  urgente: "Urgente",
};

/** Texto legible en español de un estado o prioridad. */
export function etiquetaDeEstado(estado) {
  return ETIQUETAS[estado] ?? estado;
}

/**
 * Activo / Inactivo: el mismo badge en productos, proveedores, usuarios,
 * categorías y mesas. Antes cada módulo tenía su propia copia.
 */
export function EstadoBadge({ activo }) {
  return <Badge variante={activo ? "positivo" : "neutro"}>{activo ? "Activo" : "Inactivo"}</Badge>;
}
