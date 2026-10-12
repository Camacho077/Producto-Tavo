import { AuthContext } from "@/context/AuthContext";

/**
 * Sesión fija para las pruebas de pantallas: monta cualquier pantalla con un
 * usuario y unos permisos concretos sin pasar por /seguridad/me.
 *
 *   <ConSesion>…</ConSesion>                               -> administrador
 *   <ConSesion permisos={{ ventas: ["ver"] }}>…</ConSesion> -> rol limitado
 *
 * Espejo del catálogo del backend (app/core/catalogo_permisos.py).
 */
export const PERMISOS_ADMIN = {
  dashboard: ["ver"],
  compras: ["ver", "crear", "cambiar_estado", "anular"],
  productos: ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
  categorias: ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
  proveedores: ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
  insumos: ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
  movimientos: ["ver", "crear"],
  costos: ["ver"],
  ventas: ["ver", "crear", "cambiar_estado", "anular"],
  ordenes: ["ver", "crear", "editar", "cambiar_estado", "anular"],
  usuarios: ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
  roles: ["ver", "crear", "editar", "eliminar"],
  ia: ["ver"],
  ajustes: ["ver", "editar"],
  mesas: ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
};

export function ConSesion({ permisos = PERMISOS_ADMIN, esAdministrador, usuario, tenant, children }) {
  const esAdmin = esAdministrador ?? permisos === PERMISOS_ADMIN;
  const valor = {
    token: "token-de-prueba",
    usuario: usuario ?? { id: "u-prueba", nombre_completo: "Usuaria Prueba", rol_id: "r-prueba", rol_nombre: esAdmin ? "Administrador" : "Rol de prueba" },
    tenant: tenant ?? { plan: "pro_ia", modulos_activos: [], nombre_empresa: "Empresa Prueba" },
    permisos,
    esAdministrador: esAdmin,
    puede: (modulo, accion = "ver") => Boolean(permisos[modulo]?.includes(accion)),
    cargando: false,
    error: null,
    login: async () => true,
    registro: async () => true,
    logout: () => {},
    refrescarSesion: async () => {},
  };
  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}
