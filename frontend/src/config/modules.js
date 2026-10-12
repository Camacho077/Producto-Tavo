import {
  ClipboardList,
  LayoutGrid,
  KeyRound,
  LayoutDashboard,
  Package,
  Receipt,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Store,
  Tags,
  Truck,
  Users,
} from "lucide-react";

// Cada módulo del catálogo (brief sección 2) mapeado a su ruta de frontend.
// `plan` indica el nivel mínimo en el que aparece, para poder
// mostrar/ocultar según el plan contratado por el tenant.
//
// Un módulo con `hijos` se muestra en el sidebar como grupo desplegable; el
// primer hijo es la pantalla principal del módulo (misma ruta que `path`).
export const MODULES = [
  {
    key: "dashboard",
    label: "Dashboard",
    path: "/",
    icon: LayoutDashboard,
    plan: "basico",
  },
  {
    key: "compras",
    label: "Compras",
    path: "/compras",
    icon: ShoppingCart,
    plan: "estandar",
    hijos: [
      { key: "compras", label: "Compras", path: "/compras", icon: ShoppingCart },
      { key: "productos", label: "Productos", path: "/compras/productos", icon: Package },
      { key: "categorias", label: "Categorías", path: "/compras/categorias", icon: Tags },
      { key: "proveedores", label: "Proveedores", path: "/compras/proveedores", icon: Truck },
    ],
  },
  {
    // Restaurante (2026-10-12): Ventas pasa a ser la CAJA y Pedidos, las
    // ÓRDENES con comanda. Las rutas y las claves de permiso se quedan hasta
    // que sus fases las reemplacen (docs/DECISIONES.md §0).
    key: "ventas",
    label: "Caja",
    path: "/ventas",
    icon: Receipt,
    plan: "estandar",
    hijos: [
      { key: "ventas", label: "Caja", path: "/ventas", icon: Receipt },
      { key: "pedidos", label: "Órdenes", path: "/ventas/pedidos", icon: ClipboardList },
    ],
  },
  {
    key: "seguridad",
    label: "Seguridad",
    path: "/seguridad",
    icon: ShieldCheck,
    plan: "basico",
    hijos: [
      { key: "usuarios", label: "Usuarios", path: "/seguridad/usuarios", icon: Users },
      { key: "roles", label: "Roles", path: "/seguridad/roles", icon: KeyRound },
    ],
  },
  {
    key: "ia",
    label: "Sugerencias IA",
    path: "/ia",
    icon: Sparkles,
    plan: "pro_ia",
  },
  {
    // Ajustes del restaurante (2026-10-12): datos del negocio (comanda y
    // factura), operación (tipos de orden, medios de pago, impuesto, propina,
    // cocina, jornada, impresoras) y mesas por zona.
    key: "ajustes",
    label: "Ajustes",
    path: "/ajustes",
    icon: Store,
    plan: "basico",
    hijos: [
      { key: "ajustes", label: "Restaurante", path: "/ajustes", icon: Store },
      { key: "mesas", label: "Mesas", path: "/ajustes/mesas", icon: LayoutGrid },
    ],
  },
];

const ORDEN_PLANES = ["basico", "estandar", "pro_ia"];

// Nombre comercial de cada plan. No se deriva del identificador: "pro_ia"
// capitalizado da "Pro + Ia", que no es como se llama el plan en el catálogo.
const NOMBRE_PLANES = {
  basico: "Básico",
  estandar: "Estándar",
  pro_ia: "Pro + IA",
};

export function etiquetaDePlan(plan = "basico") {
  return NOMBRE_PLANES[plan] ?? plan;
}

/**
 * Módulos visibles para un tenant: los que incluye su plan, más los que
 * tenga activados explícitamente en `modulos_activos` (casos a medida).
 *
 * Con `puede` (de useAuth) filtra además por el ROL del usuario: cada ítem y
 * cada submódulo exige el permiso "ver" de su módulo (la `key` es la misma
 * del catálogo de permisos del backend). Un grupo sin submódulos visibles
 * desaparece, y su ruta pasa a ser la del primer submódulo que sí se ve.
 * Esto solo OCULTA: la verificación real la hace el backend (403).
 */
export function modulosVisibles(planTenant = "basico", modulosActivos = [], puede = null) {
  const nivel = ORDEN_PLANES.indexOf(planTenant);
  const activos = new Set(modulosActivos ?? []);
  const porPlan = MODULES.filter((m) => ORDEN_PLANES.indexOf(m.plan) <= nivel || activos.has(m.key));
  if (!puede) return porPlan;
  return porPlan.flatMap((m) => {
    if (!m.hijos) return puede(m.key, "ver") ? [m] : [];
    const hijos = m.hijos.filter((h) => puede(h.key, "ver"));
    return hijos.length ? [{ ...m, hijos, path: hijos[0].path }] : [];
  });
}

/**
 * ¿El plan de la empresa (o un add-on en `modulos_activos`) incluye este
 * módulo o submódulo? Espejo de `modulo_contratado` del backend
 * (app/core/catalogo_permisos.py), que es quien responde 403 de verdad.
 */
export function moduloContratado(planTenant = "basico", modulosActivos = [], clave) {
  return modulosVisibles(planTenant, modulosActivos).some(
    (m) => m.key === clave || (m.hijos ?? []).some((h) => h.key === clave)
  );
}

/** Plan mínimo del grupo al que pertenece un módulo o submódulo. */
export function planMinimoDe(clave) {
  const grupo = MODULES.find((m) => m.key === clave || (m.hijos ?? []).some((h) => h.key === clave));
  return grupo ? etiquetaDePlan(grupo.plan) : null;
}

/** Primera pantalla a la que el usuario tiene acceso (para quien no ve el dashboard). */
export function primeraRutaPermitida(modulos) {
  const primero = modulos[0];
  if (!primero) return null;
  return primero.hijos ? primero.hijos[0].path : primero.path;
}
