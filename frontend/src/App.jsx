import { Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";

import ConPermiso, { InicioSegunPermiso } from "@/components/ConPermiso";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Spinner } from "@/components/ui";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { AvisoProvider } from "@/context/AvisoContext";
import { ThemeProvider } from "@/theme/ThemeContext";
import LoginPage from "@/modules/auth/LoginPage";
import RegistroPage from "@/modules/auth/RegistroPage";
import { modulo, perezoso } from "@/lib/perezoso";
import { aplicarTema, defaultTheme } from "@/theme/tokens";

/**
 * CARGA DIFERIDA POR RUTA.
 *
 * Login y registro se importan de una vez: son la puerta de entrada y hacer
 * que esperen un segundo archivo solo agregaría un viaje de ida y vuelta.
 * Todo lo demás (el layout y cada módulo) se descarga cuando se visita, así
 * quien abre la pantalla de inicio de sesión no se baja el dashboard, las
 * gráficas ni los formularios de compras.
 *
 * Los módulos que comparten archivo (por ejemplo las cuatro pantallas de
 * productos) comparten también el trozo descargado: `modulo()` envuelve un
 * solo `import()` y todas sus pantallas leen de ahí.
 *
 * PRECARGA (2026-10-01, lib/perezoso.js): con sesión guardada, el marco y la
 * pantalla de la ruta en la que se abre la app se piden EN PARALELO con
 * /seguridad/me en vez de esperar a que responda; y como `perezoso()` pinta
 * directo un módulo que ya llegó, React no suspende ni retiene la pantalla.
 * Ninguna otra ruta se descarga antes de visitarse.
 */
const modLayout = modulo(() => import("@/components/AppLayout"));
const modDashboard = modulo(() => import("@/modules/dashboard/DashboardPage"));
const modIa = modulo(() => import("@/modules/ia/IaPage"));
const AppLayout = perezoso(modLayout);
const DashboardPage = perezoso(modDashboard);
const IaPage = perezoso(modIa);

/** Azúcar para las pantallas que se exportan con nombre dentro de su módulo. */
const pantalla = perezoso;

// Documentos legales: PÚBLICOS (se leen antes de tener cuenta) y diferidos.
const modLegal = modulo(() => import("@/modules/legal/LegalPage"));
const PoliticaDatosPage = pantalla(modLegal, "PoliticaDatosPage");
const TerminosPage = pantalla(modLegal, "TerminosPage");

const modComprasPage = modulo(() => import("@/modules/compras/ComprasPage"));
const ComprasLista = pantalla(modComprasPage, "ComprasLista");
const CompraNueva = pantalla(modComprasPage, "CompraNueva");
const CompraDetalle = pantalla(modComprasPage, "CompraDetalle");

const modProductos = modulo(() => import("@/modules/compras/ProductosPage"));
const ProductosLista = pantalla(modProductos, "ProductosLista");
const ProductoNuevo = pantalla(modProductos, "ProductoNuevo");
const ProductoDetalle = pantalla(modProductos, "ProductoDetalle");
const ProductoEditar = pantalla(modProductos, "ProductoEditar");

const modCategorias = modulo(() => import("@/modules/compras/CategoriasPage"));
const CategoriasLista = pantalla(modCategorias, "CategoriasLista");
const CategoriaNueva = pantalla(modCategorias, "CategoriaNueva");
const CategoriaDetalle = pantalla(modCategorias, "CategoriaDetalle");
const CategoriaEditar = pantalla(modCategorias, "CategoriaEditar");

const modMarcas = modulo(() => import("@/modules/compras/MarcasPage"));
const MarcasLista = pantalla(modMarcas, "MarcasLista");
const MarcaNueva = pantalla(modMarcas, "MarcaNueva");
const MarcaDetalle = pantalla(modMarcas, "MarcaDetalle");
const MarcaEditar = pantalla(modMarcas, "MarcaEditar");

const modProveedores = modulo(() => import("@/modules/compras/ProveedoresPage"));
const ProveedoresLista = pantalla(modProveedores, "ProveedoresLista");
const ProveedorNuevo = pantalla(modProveedores, "ProveedorNuevo");
const ProveedorDetalle = pantalla(modProveedores, "ProveedorDetalle");
const ProveedorEditar = pantalla(modProveedores, "ProveedorEditar");

const modVentas = modulo(() => import("@/modules/ventas/VentasPage"));
const VentasLista = pantalla(modVentas, "VentasLista");
const VentaNueva = pantalla(modVentas, "VentaNueva");
const VentaDetalle = pantalla(modVentas, "VentaDetalle");

const modPedidos = modulo(() => import("@/modules/ventas/PedidosPage"));
const PedidosLista = pantalla(modPedidos, "PedidosLista");
const PedidoNuevo = pantalla(modPedidos, "PedidoNuevo");
const PedidoDetalle = pantalla(modPedidos, "PedidoDetalle");
const PedidoEditar = pantalla(modPedidos, "PedidoEditar");

const modUsuarios = modulo(() => import("@/modules/seguridad/UsuariosPage"));
const UsuariosLista = pantalla(modUsuarios, "UsuariosLista");
const UsuarioNuevo = pantalla(modUsuarios, "UsuarioNuevo");
const UsuarioDetalle = pantalla(modUsuarios, "UsuarioDetalle");
const UsuarioEditar = pantalla(modUsuarios, "UsuarioEditar");

const modRoles = modulo(() => import("@/modules/seguridad/RolesPage"));
const RolesLista = pantalla(modRoles, "RolesLista");
const RolNuevo = pantalla(modRoles, "RolNuevo");
const RolDetalle = pantalla(modRoles, "RolDetalle");
const RolEditar = pantalla(modRoles, "RolEditar");

/** Qué módulo pinta cada ruta, del prefijo más específico al más general. */
const MODULO_POR_RUTA = [
  ["/compras/productos", modProductos],
  ["/compras/categorias", modCategorias],
  ["/compras/marcas", modMarcas],
  ["/compras/proveedores", modProveedores],
  ["/compras", modComprasPage],
  ["/ventas/pedidos", modPedidos],
  ["/ventas", modVentas],
  ["/seguridad/roles", modRoles],
  ["/seguridad", modUsuarios],
  ["/ia", modIa],
];

/** Con sesión guardada, adelanta el marco y la pantalla de la ruta inicial. */
function precargarRutaInicial() {
  let haySesion = false;
  try {
    haySesion = Boolean(localStorage.getItem("js_company_token"));
  } catch {
    // localStorage bloqueado: sin precarga, la app carga igual que siempre.
  }
  if (!haySesion || typeof window === "undefined") return;
  const ruta = window.location.pathname;
  if (ruta === "/login" || ruta === "/registro" || ruta.startsWith("/legal/")) return;
  modLayout.cargar();
  const pantallaInicial = MODULO_POR_RUTA.find(([prefijo]) => ruta === prefijo || ruta.startsWith(`${prefijo}/`));
  (pantallaInicial?.[1] ?? modDashboard).cargar();
}
precargarRutaInicial();

/**
 * Aplica la personalización del tenant sobre la capa de acento. El sistema de
 * diseño base (mármol, pizarra, tipografía) no se personaliza; el color de
 * marca del cliente sí, y repinta todo el producto.
 */
function TemaDelTenant() {
  const { tenant } = useAuth();

  useEffect(() => {
    aplicarTema(tenant?.theme_config ?? defaultTheme);
  }, [tenant]);

  return null;
}

/**
 * Lo que se ve mientras se descarga el trozo de una ruta. Es el mismo
 * indicador que ya usa ProtectedRoute mientras valida la sesión, para que
 * la espera se vea igual venga de donde venga y no aparezca una forma nueva.
 */
function CargandoRuta() {
  return (
    <div className="flex h-screen w-full items-center justify-center gap-2 bg-[var(--fondo)] text-[13px] text-[var(--texto-secundario)]">
      <Spinner tamano="sm" />
      Cargando...
    </div>
  );
}

// Rutas de la app. Cada submódulo del sidebar (config/modules.js) tiene su
// ruta propia; los módulos se registran en modules.js y aquí.
export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AvisoProvider>
            <TemaDelTenant />
            <Suspense fallback={<CargandoRuta />}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/registro" element={<RegistroPage />} />
                <Route path="/legal/privacidad" element={<PoliticaDatosPage />} />
                <Route path="/legal/terminos" element={<TerminosPage />} />
                <Route element={<ProtectedRoute />}>
                  <Route element={<AppLayout />}>
                    <Route path="/" element={<InicioSegunPermiso><DashboardPage /></InicioSegunPermiso>} />

                    {/* Cada acción es una pantalla con ruta propia:
                        listado → /x, crear → /x/nuevo, detalle → /x/:id, editar → /x/:id/editar.
                        React Router prioriza los segmentos estáticos (/compras/productos)
                        sobre los dinámicos (/compras/:id), así que el orden no importa. */}
                    <Route path="/compras" element={<ConPermiso modulo="compras" accion="ver"><ComprasLista /></ConPermiso>} />
                    <Route path="/compras/nuevo" element={<ConPermiso modulo="compras" accion="crear"><CompraNueva /></ConPermiso>} />
                    <Route path="/compras/:id" element={<ConPermiso modulo="compras" accion="ver"><CompraDetalle /></ConPermiso>} />

                    <Route path="/compras/productos" element={<ConPermiso modulo="productos" accion="ver"><ProductosLista /></ConPermiso>} />
                    <Route path="/compras/productos/nuevo" element={<ConPermiso modulo="productos" accion="crear"><ProductoNuevo /></ConPermiso>} />
                    <Route path="/compras/productos/:id" element={<ConPermiso modulo="productos" accion="ver"><ProductoDetalle /></ConPermiso>} />
                    <Route path="/compras/productos/:id/editar" element={<ConPermiso modulo="productos" accion="editar"><ProductoEditar /></ConPermiso>} />

                    <Route path="/compras/categorias" element={<ConPermiso modulo="categorias" accion="ver"><CategoriasLista /></ConPermiso>} />
                    <Route path="/compras/categorias/nuevo" element={<ConPermiso modulo="categorias" accion="crear"><CategoriaNueva /></ConPermiso>} />
                    <Route path="/compras/categorias/:id" element={<ConPermiso modulo="categorias" accion="ver"><CategoriaDetalle /></ConPermiso>} />
                    <Route path="/compras/categorias/:id/editar" element={<ConPermiso modulo="categorias" accion="editar"><CategoriaEditar /></ConPermiso>} />

                    <Route path="/compras/marcas" element={<ConPermiso modulo="marcas" accion="ver"><MarcasLista /></ConPermiso>} />
                    <Route path="/compras/marcas/nuevo" element={<ConPermiso modulo="marcas" accion="crear"><MarcaNueva /></ConPermiso>} />
                    <Route path="/compras/marcas/:id" element={<ConPermiso modulo="marcas" accion="ver"><MarcaDetalle /></ConPermiso>} />
                    <Route path="/compras/marcas/:id/editar" element={<ConPermiso modulo="marcas" accion="editar"><MarcaEditar /></ConPermiso>} />

                    <Route path="/compras/proveedores" element={<ConPermiso modulo="proveedores" accion="ver"><ProveedoresLista /></ConPermiso>} />
                    <Route path="/compras/proveedores/nuevo" element={<ConPermiso modulo="proveedores" accion="crear"><ProveedorNuevo /></ConPermiso>} />
                    <Route path="/compras/proveedores/:id" element={<ConPermiso modulo="proveedores" accion="ver"><ProveedorDetalle /></ConPermiso>} />
                    <Route path="/compras/proveedores/:id/editar" element={<ConPermiso modulo="proveedores" accion="editar"><ProveedorEditar /></ConPermiso>} />

                    <Route path="/ventas" element={<ConPermiso modulo="ventas" accion="ver"><VentasLista /></ConPermiso>} />
                    <Route path="/ventas/nuevo" element={<ConPermiso modulo="ventas" accion="crear"><VentaNueva /></ConPermiso>} />
                    <Route path="/ventas/:id" element={<ConPermiso modulo="ventas" accion="ver"><VentaDetalle /></ConPermiso>} />

                    <Route path="/ventas/pedidos" element={<ConPermiso modulo="pedidos" accion="ver"><PedidosLista /></ConPermiso>} />
                    <Route path="/ventas/pedidos/nuevo" element={<ConPermiso modulo="pedidos" accion="crear"><PedidoNuevo /></ConPermiso>} />
                    <Route path="/ventas/pedidos/:id" element={<ConPermiso modulo="pedidos" accion="ver"><PedidoDetalle /></ConPermiso>} />
                    <Route path="/ventas/pedidos/:id/editar" element={<ConPermiso modulo="pedidos" accion="editar"><PedidoEditar /></ConPermiso>} />

                    <Route path="/seguridad" element={<Navigate to="/seguridad/usuarios" replace />} />
                    <Route path="/seguridad/usuarios" element={<ConPermiso modulo="usuarios" accion="ver"><UsuariosLista /></ConPermiso>} />
                    <Route path="/seguridad/usuarios/nuevo" element={<ConPermiso modulo="usuarios" accion="crear"><UsuarioNuevo /></ConPermiso>} />
                    <Route path="/seguridad/usuarios/:id" element={<ConPermiso modulo="usuarios" accion="ver"><UsuarioDetalle /></ConPermiso>} />
                    <Route path="/seguridad/usuarios/:id/editar" element={<ConPermiso modulo="usuarios" accion="editar"><UsuarioEditar /></ConPermiso>} />
                    <Route path="/seguridad/roles" element={<ConPermiso modulo="roles" accion="ver"><RolesLista /></ConPermiso>} />
                    <Route path="/seguridad/roles/nuevo" element={<ConPermiso modulo="roles" accion="crear"><RolNuevo /></ConPermiso>} />
                    <Route path="/seguridad/roles/:id" element={<ConPermiso modulo="roles" accion="ver"><RolDetalle /></ConPermiso>} />
                    <Route path="/seguridad/roles/:id/editar" element={<ConPermiso modulo="roles" accion="editar"><RolEditar /></ConPermiso>} />

                    <Route path="/ia" element={<ConPermiso modulo="ia" accion="ver"><IaPage /></ConPermiso>} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Route>
                </Route>
              </Routes>
            </Suspense>
          </AvisoProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
