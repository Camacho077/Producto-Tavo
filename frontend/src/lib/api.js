import axios from "axios";

export const api = axios.create({
  // Puerto 8002 (el 8001 es del Producto JS): ver "Puertos" en el README.
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8002/api/v1",
  // Cuando el backend se expone por localtunnel (demo por internet), el
  // túnel intercepta la PRIMERA petición de cada navegador con una página
  // de aviso en HTML; este header la salta para las llamadas de la API.
  // En local es inofensivo (el backend acepta cualquier header por CORS).
  headers: { "bypass-tunnel-reminder": "1" },
});

// Adjunta el token JWT (si existe) a cada request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("js_company_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Cuando el backend responde 401 (sesión expirada o token inválido), se
// notifica a quien se haya suscrito (ver AuthContext) para cerrar sesión y
// redirigir a /login, sin acoplar esta capa HTTP a React.
let onUnauthorized = null;

export function setLogoutHandler(handler) {
  onUnauthorized = handler;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);
