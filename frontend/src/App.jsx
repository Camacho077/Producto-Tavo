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

const modPlatos = modulo(() => import("@/modules/carta/PlatosPage"));
const PlatosLista = pantalla(modPlatos, "PlatosLista");
const PlatoNuevo = pantalla(modPlatos, "PlatoNuevo");
const PlatoDetalle = pantalla(modPlatos, "PlatoDetalle");
const PlatoEditar = pantalla(modPlatos, "PlatoEditar");

const modCombos = modulo(() => import("@/modules/carta/CombosPage"));
const CombosLista = pantalla(modCombos, "CombosLista");
const ComboNuevo = pantalla(modCombos, "ComboNuevo");
const ComboDetalle = pantalla(modCombos, "ComboDetalle");
const ComboEditar = pantalla(modCombos, "ComboEditar");

const modCategorias = modulo(() => import("@/modules/carta/CategoriasPage"));
const CategoriasLista = pantalla(modCategorias, "CategoriasLista");
const CategoriaNueva = pantalla(modCategorias, "CategoriaNueva");
const CategoriaDetalle = pantalla(modCategorias, "CategoriaDetalle");
const CategoriaEditar = pantalla(modCategorias, "CategoriaEditar");

const modInsumos = modulo(() => import("@/modules/inventario/InsumosPage"));
const InsumosLista = pantalla(modInsumos, "InsumosLista");
const InsumoNuevo = pantalla(modInsumos, "InsumoNuevo");
const InsumoDetalle = pantalla(modInsumos, "InsumoDetalle");
const InsumoEditar = pantalla(modInsumos, "InsumoEditar");

const modComprasPage = modulo(() => import("@/modules/inventario/ComprasPage"));
const ComprasLista = pantalla(modComprasPage, "ComprasLista");
const CompraNueva = pantalla(modComprasPage, "CompraNueva");
const CompraDetalle = pantalla(modComprasPage, "CompraDetalle");

const modMovimientos = modulo(() => import("@/modules/inventario/MovimientosPage"));
const MovimientosLista = pantalla(modMovimientos, "MovimientosLista");
const MermaNueva = pantalla(modMovimientos, "MermaNueva");
const ConteosLista = pantalla(modMovimientos, "ConteosLista");
const ConteoNuevo = pantalla(modMovimientos, "ConteoNuevo");
const ConteoDetalle = pantalla(modMovimientos, "ConteoDetalle");

const modCargaInicial = modulo(() => import("@/modules/inventario/CargaInicialPage"));
const CargaInicial = pantalla(modCargaInicial, "CargaInicial");

const modProveedores = modulo(() => import("@/modules/inventario/ProveedoresPage"));
const ProveedoresLista = pantalla(modProveedores, "ProveedoresLista");
const ProveedorNuevo = pantalla(modProveedores, "ProveedorNuevo");
const ProveedorDetalle = pantalla(modProveedores, "ProveedorDetalle");
const ProveedorEditar = pantalla(modProveedores, "ProveedorEditar");

const modVentas = modulo(() => import("@/modules/ventas/VentasPage"));
const VentasLista = pantalla(modVentas, "VentasLista");
const VentaNueva = pantalla(modVentas, "VentaNueva");
const VentaDetalle = pantalla(modVentas, "VentaDetalle");

const modOrdenes = modulo(() => import("@/modules/ordenes/OrdenesPage"));
const OrdenesLista = pantalla(modOrdenes, "OrdenesLista");
const OrdenDetalle = pantalla(modOrdenes, "OrdenDetalle");
const OrdenEditar = pantalla(modOrdenes, "OrdenEditar");
const MesasServicio = pantalla(modOrdenes, "MesasServicio");

const modTomarPedido = modulo(() => import("@/modules/ordenes/TomarPedidoPage"));
const OrdenNueva = pantalla(modTomarPedido, "OrdenNueva");
const OrdenAgregar = pantalla(modTomarPedido, "OrdenAgregar");

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

const modAjustes = modulo(() => import("@/modules/ajustes/AjustesPage"));
const AjustesDetalle = pantalla(modAjustes, "AjustesDetalle");
const NegocioEditar = pantalla(modAjustes, "NegocioEditar");
const OperacionEditar = pantalla(modAjustes, "OperacionEditar");

const modMesas = modulo(() => import("@/modules/ajustes/MesasPage"));
const MesasLista = pantalla(modMesas, "MesasLista");
const MesaNueva = pantalla(modMesas, "MesaNueva");
const MesaDetalle = pantalla(modMesas, "MesaDetalle");
const MesaEditar = pantalla(modMesas, "MesaEditar");
const ZonasLista = pantalla(modMesas, "ZonasLista");
const ZonaNueva = pantalla(modMesas, "ZonaNueva");
const ZonaDetalle = pantalla(modMesas, "ZonaDetalle");
const ZonaEditar = pantalla(modMesas, "ZonaEditar");

/** Qué módulo pinta cada ruta, del prefijo más específico al más general. */
const MODULO_POR_RUTA = [
  ["/carta/combos", modCombos],
  ["/carta/categorias", modCategorias],
  ["/carta", modPlatos],
  ["/inventario/compras", modComprasPage],
  ["/inventario/proveedores", modProveedores],
  ["/inventario/movimientos", modMovimientos],
  ["/inventario/conteos", modMovimientos],
  ["/inventario/carga-inicial", modCargaInicial],
  ["/inventario", modInsumos],
  ["/ordenes/nueva", modTomarPedido],
  ["/ordenes", modOrdenes],
  ["/ventas", modVentas],
  ["/seguridad/roles", modRoles],
  ["/seguridad", modUsuarios],
  ["/ia", modIa],
  ["/ajustes/mesas", modMesas],
  ["/ajustes/zonas", modMesas],
  ["/ajustes", modAjustes],
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
                        React Router prioriza los segmentos estáticos (/carta/combos)
                        sobre los dinámicos (/carta/:id), así que el orden no importa. */}
                    <Route path="/carta" element={<ConPermiso modulo="productos" accion="ver"><PlatosLista /></ConPermiso>} />
                    <Route path="/carta/nuevo" element={<ConPermiso modulo="productos" accion="crear"><PlatoNuevo /></ConPermiso>} />
                    <Route path="/carta/:id" element={<ConPermiso modulo="productos" accion="ver"><PlatoDetalle /></ConPermiso>} />
                    <Route path="/carta/:id/editar" element={<ConPermiso modulo="productos" accion="editar"><PlatoEditar /></ConPermiso>} />
                    <Route path="/carta/combos" element={<ConPermiso modulo="productos" accion="ver"><CombosLista /></ConPermiso>} />
                    <Route path="/carta/combos/nuevo" element={<ConPermiso modulo="productos" accion="crear"><ComboNuevo /></ConPermiso>} />
                    <Route path="/carta/combos/:id" element={<ConPermiso modulo="productos" accion="ver"><ComboDetalle /></ConPermiso>} />
                    <Route path="/carta/combos/:id/editar" element={<ConPermiso modulo="productos" accion="editar"><ComboEditar /></ConPermiso>} />
                    <Route path="/carta/categorias" element={<ConPermiso modulo="categorias" accion="ver"><CategoriasLista /></ConPermiso>} />
                    <Route path="/carta/categorias/nuevo" element={<ConPermiso modulo="categorias" accion="crear"><CategoriaNueva /></ConPermiso>} />
                    <Route path="/carta/categorias/:id" element={<ConPermiso modulo="categorias" accion="ver"><CategoriaDetalle /></ConPermiso>} />
                    <Route path="/carta/categorias/:id/editar" element={<ConPermiso modulo="categorias" accion="editar"><CategoriaEditar /></ConPermiso>} />

                    <Route path="/inventario" element={<Navigate to="/inventario/insumos" replace />} />
                    <Route path="/inventario/insumos" element={<ConPermiso modulo="insumos" accion="ver"><InsumosLista /></ConPermiso>} />
                    <Route path="/inventario/insumos/nuevo" element={<ConPermiso modulo="insumos" accion="crear"><InsumoNuevo /></ConPermiso>} />
                    <Route path="/inventario/insumos/:id" element={<ConPermiso modulo="insumos" accion="ver"><InsumoDetalle /></ConPermiso>} />
                    <Route path="/inventario/insumos/:id/editar" element={<ConPermiso modulo="insumos" accion="editar"><InsumoEditar /></ConPermiso>} />
                    <Route path="/inventario/insumos/:id/merma" element={<ConPermiso modulo="movimientos" accion="crear"><MermaNueva /></ConPermiso>} />
                    <Route path="/inventario/movimientos" element={<ConPermiso modulo="movimientos" accion="ver"><MovimientosLista /></ConPermiso>} />
                    <Route path="/inventario/conteos" element={<ConPermiso modulo="movimientos" accion="ver"><ConteosLista /></ConPermiso>} />
                    <Route path="/inventario/conteos/nuevo" element={<ConPermiso modulo="movimientos" accion="crear"><ConteoNuevo /></ConPermiso>} />
                    <Route path="/inventario/conteos/:id" element={<ConPermiso modulo="movimientos" accion="ver"><ConteoDetalle /></ConPermiso>} />
                    <Route path="/inventario/carga-inicial" element={<ConPermiso modulo="insumos" accion="crear"><CargaInicial /></ConPermiso>} />
                    <Route path="/inventario/compras" element={<ConPermiso modulo="compras" accion="ver"><ComprasLista /></ConPermiso>} />
                    <Route path="/inventario/compras/nuevo" element={<ConPermiso modulo="compras" accion="crear"><CompraNueva /></ConPermiso>} />
                    <Route path="/inventario/compras/:id" element={<ConPermiso modulo="compras" accion="ver"><CompraDetalle /></ConPermiso>} />
                    <Route path="/inventario/proveedores" element={<ConPermiso modulo="proveedores" accion="ver"><ProveedoresLista /></ConPermiso>} />
                    <Route path="/inventario/proveedores/nuevo" element={<ConPermiso modulo="proveedores" accion="crear"><ProveedorNuevo /></ConPermiso>} />
                    <Route path="/inventario/proveedores/:id" element={<ConPermiso modulo="proveedores" accion="ver"><ProveedorDetalle /></ConPermiso>} />
                    <Route path="/inventario/proveedores/:id/editar" element={<ConPermiso modulo="proveedores" accion="editar"><ProveedorEditar /></ConPermiso>} />

                    <Route path="/ordenes" element={<ConPermiso modulo="ordenes" accion="ver"><OrdenesLista /></ConPermiso>} />
                    <Route path="/ordenes/nueva" element={<ConPermiso modulo="ordenes" accion="crear"><OrdenNueva /></ConPermiso>} />
                    <Route path="/ordenes/mesas" element={<ConPermiso modulo="ordenes" accion="ver"><MesasServicio /></ConPermiso>} />
                    <Route path="/ordenes/:id" element={<ConPermiso modulo="ordenes" accion="ver"><OrdenDetalle /></ConPermiso>} />
                    <Route path="/ordenes/:id/editar" element={<ConPermiso modulo="ordenes" accion="editar"><OrdenEditar /></ConPermiso>} />
                    <Route path="/ordenes/:id/agregar" element={<ConPermiso modulo="ordenes" accion="editar"><OrdenAgregar /></ConPermiso>} />
                    <Route path="/ventas" element={<ConPermiso modulo="ventas" accion="ver"><VentasLista /></ConPermiso>} />
                    <Route path="/ventas/nuevo" element={<ConPermiso modulo="ventas" accion="crear"><VentaNueva /></ConPermiso>} />
                    <Route path="/ventas/:id" element={<ConPermiso modulo="ventas" accion="ver"><VentaDetalle /></ConPermiso>} />


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

                    <Route path="/ajustes" element={<ConPermiso modulo="ajustes" accion="ver"><AjustesDetalle /></ConPermiso>} />
                    <Route path="/ajustes/negocio" element={<Navigate to="/ajustes" replace />} />
                    <Route path="/ajustes/negocio/editar" element={<ConPermiso modulo="ajustes" accion="editar"><NegocioEditar /></ConPermiso>} />
                    <Route path="/ajustes/operacion" element={<Navigate to="/ajustes" replace />} />
                    <Route path="/ajustes/operacion/editar" element={<ConPermiso modulo="ajustes" accion="editar"><OperacionEditar /></ConPermiso>} />
                    <Route path="/ajustes/mesas" element={<ConPermiso modulo="mesas" accion="ver"><MesasLista /></ConPermiso>} />
                    <Route path="/ajustes/mesas/nuevo" element={<ConPermiso modulo="mesas" accion="crear"><MesaNueva /></ConPermiso>} />
                    <Route path="/ajustes/mesas/:id" element={<ConPermiso modulo="mesas" accion="ver"><MesaDetalle /></ConPermiso>} />
                    <Route path="/ajustes/mesas/:id/editar" element={<ConPermiso modulo="mesas" accion="editar"><MesaEditar /></ConPermiso>} />
                    <Route path="/ajustes/zonas" element={<ConPermiso modulo="mesas" accion="ver"><ZonasLista /></ConPermiso>} />
                    <Route path="/ajustes/zonas/nuevo" element={<ConPermiso modulo="mesas" accion="crear"><ZonaNueva /></ConPermiso>} />
                    <Route path="/ajustes/zonas/:id" element={<ConPermiso modulo="mesas" accion="ver"><ZonaDetalle /></ConPermiso>} />
                    <Route path="/ajustes/zonas/:id/editar" element={<ConPermiso modulo="mesas" accion="editar"><ZonaEditar /></ConPermiso>} />
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
