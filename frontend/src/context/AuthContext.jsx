import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setLogoutHandler } from "@/lib/api";

const TOKEN_KEY = "js_company_token";

// Exportado para los tests (src/test/sesion.jsx): permite montar una pantalla
// con una sesión y unos permisos fijos sin pasar por el backend.
export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [usuario, setUsuario] = useState(null);
  const [tenant, setTenant] = useState(null);
  // Permisos EFECTIVOS del rol ({modulo: [acciones]}), tal como los calcula el
  // backend en /seguridad/me. Solo sirven para ocultar lo que el rol no puede
  // hacer: la verificación real la hace cada endpoint (403).
  const [permisos, setPermisos] = useState({});
  const [esAdministrador, setEsAdministrador] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUsuario(null);
    setTenant(null);
    setPermisos({});
    setEsAdministrador(false);
  }, []);

  useEffect(() => {
    setLogoutHandler(logout);
  }, [logout]);

  const hidratar = useCallback(
    () =>
      api.get("/seguridad/me").then((res) => {
        setUsuario(res.data.usuario);
        setTenant(res.data.tenant);
        setPermisos(res.data.permisos ?? {});
        setEsAdministrador(Boolean(res.data.es_administrador));
      }),
    []
  );

  useEffect(() => {
    if (!token) {
      setCargando(false);
      return;
    }
    hidratar()
      .catch(() => {
        logout();
      })
      .finally(() => setCargando(false));
  }, [token, logout, hidratar]);

  /** Vuelve a pedir la sesión: tras editar los datos del negocio, el logo o
   * la configuración, el marco (nombre, logo) y la toma de pedidos (tipos
   * de orden, medios de pago) ven el cambio sin recargar la página. */
  const refrescarSesion = useCallback(() => hidratar().catch(() => {}), [hidratar]);

  const login = useCallback(async (email, password, recordarme = false) => {
    setError(null);
    try {
      // recordarme lo resuelve el backend: emite un token de 30 días en vez
      // de 8 horas (ver app/modules/seguridad/router.py).
      const { data } = await api.post("/seguridad/login", { email, password, recordarme });
      // Guardar el token dispara el efecto de arriba, que consulta /seguridad/me
      // e hidrata usuario/tenant — evita duplicar esa llamada aquí.
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      return true;
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo iniciar sesión. Intenta de nuevo.");
      return false;
    }
  }, []);

  const registro = useCallback(async (nombreEmpresa, email, password, aceptaCondiciones = false) => {
    setError(null);
    try {
      const { data } = await api.post("/seguridad/registro", {
        nombre_empresa: nombreEmpresa,
        email,
        password,
        acepta_condiciones: aceptaCondiciones,
      });
      // Igual que en login: el registro ya devuelve un token, así que
      // guardarlo alcanza para loguear automáticamente sin pedir de nuevo
      // las credenciales — el efecto de arriba hidrata usuario/tenant.
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      return true;
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo completar el registro. Intenta de nuevo.");
      return false;
    }
  }, []);

  /** ¿El rol del usuario puede hacer `accion` en `modulo`? */
  const puede = useCallback((modulo, accion = "ver") => Boolean(permisos[modulo]?.includes(accion)), [permisos]);

  const value = useMemo(
    () => ({ token, usuario, tenant, permisos, esAdministrador, puede, cargando, error, login, registro, logout, refrescarSesion }),
    [token, usuario, tenant, permisos, esAdministrador, puede, cargando, error, login, registro, logout, refrescarSesion]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth debe usarse dentro de un AuthProvider");
  }
  return ctx;
}
