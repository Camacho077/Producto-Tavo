import {
  Banknote,
  ChefHat,
  ClipboardCheck,
  ClipboardList,
  FileUp,
  HandPlatter,
  History,
  Layers,
  LayoutGrid,
  Lock,
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
  UtensilsCrossed,
  Wallet,
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
    // Órdenes de pedido con comanda (fase 4, 2026-10-12). Tomar pedido va
    // primero: es la pantalla del mesero.
    key: "ordenes",
    label: "Órdenes",
    path: "/ordenes/nueva",
    icon: ClipboardList,
    plan: "basico",
    hijos: [
      { key: "tomar_pedido", permiso: "ordenes", accion: "crear", label: "Tomar pedido", path: "/ordenes/nueva", icon: HandPlatter },
      { key: "ordenes", label: "Tablero", path: "/ordenes", icon: ClipboardList },
      { key: "mesas_servicio", permiso: "ordenes", label: "Mesas", path: "/ordenes/mesas", icon: LayoutGrid },
    ],
  },
  {
    // Pantalla de cocina (fase 5, 2026-10-12): la única pantalla del cocinero.
    key: "cocina",
    label: "Cocina",
    path: "/cocina",
    icon: ChefHat,
    plan: "basico",
  },
  {
    // Carta (2026-10-12): platos con receta, combos y categorías. Desde
    // Básico: sin carta no hay órdenes.
    key: "carta",
    label: "Carta",
    path: "/carta",
    icon: UtensilsCrossed,
    plan: "basico",
    hijos: [
      { key: "productos", label: "Platos", path: "/carta", icon: UtensilsCrossed },
      { key: "combos", permiso: "productos", label: "Combos", path: "/carta/combos", icon: Layers },
      { key: "categorias", label: "Categorías", path: "/carta/categorias", icon: Tags },
    ],
  },
  {
    // Inventario de INSUMOS (2026-10-12): existencias por movimientos,
    // compras a proveedores y costo que alimenta las recetas.
    key: "inventario",
    label: "Inventario",
    path: "/inventario/insumos",
    icon: Package,
    plan: "estandar",
    hijos: [
      { key: "insumos", label: "Insumos", path: "/inventario/insumos", icon: Package },
      { key: "movimientos", label: "Movimientos", path: "/inventario/movimientos", icon: History },
      { key: "conteos", permiso: "movimientos", label: "Conteos", path: "/inventario/conteos", icon: ClipboardCheck },
      { key: "compras", label: "Compras", path: "/inventario/compras", icon: ShoppingCart },
      { key: "proveedores", label: "Proveedores", path: "/inventario/proveedores", icon: Truck },
      { key: "carga_inicial", permiso: "insumos", accion: "crear", label: "Carga inicial", path: "/inventario/carga-inicial", icon: FileUp },
    ],
  },
  {
    // Caja (fase 6, 2026-10-12): cobrar, comprobantes, cierres y gastos.
    key: "ventas",
    label: "Caja",
    path: "/caja",
    icon: Receipt,
    plan: "basico",
    hijos: [
      { key: "caja", label: "Caja", path: "/caja", icon: Wallet },
      { key: "ventas", label: "Comprobantes", path: "/caja/ventas", icon: Receipt },
      { key: "cierres", permiso: "caja", label: "Cierres", path: "/caja/cierres", icon: Lock },
      { key: "gastos", label: "Gastos", path: "/gastos", icon: Banknote },
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
    // `permiso`: el módulo del catálogo que exige el hijo cuando su clave
    // no es la del permiso (Combos usa el permiso de "productos"); `accion`,
    // cuando no basta con "ver" (la carga inicial crea insumos).
    const hijos = m.hijos.filter((h) => puede(h.permiso ?? h.key, h.accion ?? "ver"));
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

/** Las pantallas sueltas del menú (módulos sin hijos y cada submódulo). */
export function hojasDe(modulos) {
  return modulos.flatMap((m) => (m.hijos ? m.hijos.map((h) => ({ ...h, grupo: m.key })) : [m]));
}

/**
 * PANTALLA DE INICIO POR ROL (fase 7, 2026-10-12). Cada rol entra directo a
 * lo suyo, en este orden: quien ve el dashboard (administrador) → "/"; quien
 * maneja la caja (cajero) → Caja; quien toma pedidos (mesero) → Tomar
 * pedido; quien está en cocina → Cocina. Un rol a la medida sin ninguno de
 * esos entra a su primera pantalla permitida. Se deriva de los PERMISOS, así
 * que un rol personalizado en Seguridad → Roles también aterriza bien.
 */
export function inicioDeRol(modulos, puede) {
  const rutas = new Set(hojasDe(modulos).map((h) => h.path));
  const prioridades = [
    ["/", () => puede("dashboard", "ver")],
    ["/caja", () => puede("caja", "ver") && puede("ventas", "crear")],
    ["/ordenes/nueva", () => puede("ordenes", "crear")],
    ["/cocina", () => puede("cocina", "ver")],
  ];
  const elegida = prioridades.find(([ruta, aplica]) => rutas.has(ruta) && aplica());
  return elegida ? elegida[0] : primeraRutaPermitida(modulos);
}
