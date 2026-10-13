import { useCallback, useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import "@/components/ui/listados.css";
import "@/components/ui/movimiento.css";
import "@/components/ui/pantallas.css";

import BarraSuperior from "@/components/BarraSuperior";
import PieLegal from "@/components/PieLegal";
import Sidebar from "@/components/Sidebar";
import SinConexion from "@/components/SinConexion";
import { Aviso } from "@/components/ui";
import { hojasDe, inicioDeRol, modulosVisibles } from "@/config/modules";
import { useAuth } from "@/context/AuthContext";
import { AvisosProvider, badgesDeAvisos, useAvisos } from "@/context/AvisosContext";
import { CURVA_SUAVE, puedeAnimar } from "@/lib/movimiento";

/**
 * MARCO DE LA APLICACIÓN — rediseño monocromático (2026-10-01): sidebar
 * blanco a la izquierda a toda altura, barra superior blanca y el contenido
 * sobre el gris de la aplicación. Sin panel flotante, sin degradados.
 *
 * En pantallas angostas el sidebar se convierte en cajón (entra con transform,
 * nunca con `left`) y aparece una barra inferior con los accesos que más se
 * usan, construida con los módulos que el plan del tenant deja ver.
 *
 * VISTAS POR ROL (fase 7, 2026-10-12): la barra inferior empieza por la
 * pantalla de inicio DEL ROL (el mesero ve Tomar pedido, Tablero y Mesas al
 * alcance del pulgar). Y un rol con UNA sola pantalla (el cocinero) entra en
 * MODO ENFOCADO: sin sidebar ni barra inferior, toda la tablet para la
 * cocina, con su nombre, el tema y cerrar sesión arriba.
 */

// Cuántos accesos caben en la barra inferior además de Menú.
const ACCESOS_EN_BARRA = 3;

/**
 * SALIDA DE VISTA — la pantalla que se va SIEMPRE sale animada.
 *
 * React desmonta la pantalla vieja y monta la nueva en el mismo commit, así
 * que no hay "después" en el que animar la vieja. Lo que se hace: en la
 * limpieza del ref (React la llama con el nodo todavía en el documento) se
 * CLONA el DOM de la pantalla que sale, se deja encima en su mismo sitio,
 * inerte, y se desvanece subiendo 6 px en 180 ms con la curva del producto.
 *
 * Es un clon de DOM y no un árbol de React a propósito: no puede volver a
 * pedir datos, no reacciona a la ruta nueva y no pelea con Suspense. Con
 * `prefers-reduced-motion`, o sin WAAPI, no hay clon: el cambio es directo.
 */
function despedirVista(nodo, geometria) {
  const contenedor = nodo.parentElement;
  if (!contenedor || !nodo.isConnected || !geometria || !puedeAnimar(nodo)) return;

  // CERO lecturas de layout aquí: esto corre en MEDIO del commit de React,
  // con el DOM a medio cambiar, y leer offsetTop/getBoundingClientRect
  // forzaría un layout síncrono de la página entera (medido: un cuadro de
  // más al navegar). La posición y el ancho vienen ya medidos (`geometria`).
  const clon = nodo.cloneNode(true);
  clon.classList.remove("vista");
  clon.classList.add("vista-fantasma");
  clon.setAttribute("aria-hidden", "true");
  clon.setAttribute("inert", "");
  clon.removeAttribute("id");
  clon.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
  clon.style.top = `${geometria.top}px`;
  clon.style.left = `${geometria.left}px`;
  clon.style.width = `${geometria.width}px`;

  // ¿La pantalla se va DE VERDAD? En desarrollo, StrictMode suelta y vuelve a
  // enganchar los refs al montar (para detectar errores): esta limpieza corre
  // sin que la pantalla salga, y el clon se veía desvanecerse ENCIMA de la
  // misma pantalla (doble exposición en cada montaje). Cuando la salida es
  // real, React quita el nodo del documento en este mismo commit; con
  // StrictMode el nodo se queda. Se decide en una microtarea: corre después
  // del commit y ANTES del pintado, así que el clon aparece en el mismo cuadro.
  queueMicrotask(() => {
    if (nodo.isConnected || !contenedor.isConnected) return;
    contenedor.appendChild(clon);
    animarSalida(clon);
  });
}

function animarSalida(clon) {
  const salida = clon.animate(
    [
      { opacity: 1, transform: "translate3d(0, 0, 0)" },
      { opacity: 0, transform: "translate3d(0, -6px, 0)" },
    ],
    { duration: 180, easing: `cubic-bezier(${CURVA_SUAVE.join(", ")})`, fill: "forwards" },
  );
  const quitar = () => clon.remove();
  salida.onfinish = quitar;
  salida.oncancel = quitar;
}

export default function AppLayout() {
  const { puede } = useAuth();
  // Una sola petición de avisos para barra, sidebar y panel del dashboard.
  return (
    <AvisosProvider habilitado={puede("dashboard", "ver")}>
      <Marco />
    </AvisosProvider>
  );
}

function Marco() {
  const { tenant, usuario, logout, puede } = useAuth();
  const avisos = useAvisos()?.data?.avisos ?? [];
  const { pathname } = useLocation();
  // El cajón se abre "en" una ruta: al navegar a otra queda cerrado solo
  // (derivado en el render, sin un efecto que lo cierre después).
  const [abiertoEn, setAbiertoEn] = useState(null);
  const menuAbierto = abiertoEn === pathname;
  const abrirMenu = useCallback(() => setAbiertoEn(pathname), [pathname]);
  const cerrarMenu = useCallback(() => setAbiertoEn(null), []);

  // Ref con limpieza (React 19): corre cuando la pantalla de esta ruta se va.
  // La geometría de la vista se mide ANTES, en un ResizeObserver (corre con
  // el layout ya limpio), para que la despedida no tenga que leer nada.
  const refVista = useCallback((nodo) => {
    if (!nodo) return undefined;
    const geometria = { top: nodo.offsetTop, left: nodo.offsetLeft, width: nodo.offsetWidth };
    const observador =
      typeof ResizeObserver === "function"
        ? new ResizeObserver(() => {
            geometria.top = nodo.offsetTop;
            geometria.left = nodo.offsetLeft;
            geometria.width = nodo.offsetWidth;
          })
        : null;
    observador?.observe(nodo);
    return () => {
      observador?.disconnect();
      despedirVista(nodo, geometria);
    };
  }, []);


  // Con el cajón abierto la página de fondo no se desplaza, y Escape lo cierra.
  useEffect(() => {
    const raiz = document.documentElement;
    raiz.classList.toggle("sin-scroll", menuAbierto);
    if (!menuAbierto) return undefined;
    const alTeclear = (evento) => {
      if (evento.key === "Escape") cerrarMenu();
    };
    document.addEventListener("keydown", alTeclear);
    return () => {
      document.removeEventListener("keydown", alTeclear);
      raiz.classList.remove("sin-scroll");
    };
  }, [menuAbierto, cerrarMenu]);

  const modulos = modulosVisibles(tenant?.plan, tenant?.modulos_activos, puede);
  const hojas = hojasDe(modulos);
  const rutaInicio = inicioDeRol(modulos, puede);
  const enfocado = hojas.length === 1;
  const accesos = [...hojas.filter((h) => h.path === rutaInicio), ...hojas.filter((h) => h.path !== rutaInicio)].slice(0, ACCESOS_EN_BARRA);

  return (
    <>
      {/* Pila de alertas: fija arriba a la derecha, fuera del flujo y fuera del
          div con key por ruta, para que no se remonte al navegar. */}
      <Aviso />
      <SinConexion />

      <div className={`shell ${enfocado ? "shell--enfocado" : ""}`}>
        <div className="app">
          {!enfocado && (
            <Sidebar
              plan={tenant?.plan}
              modulosActivos={tenant?.modulos_activos}
              nombreEmpresa={tenant?.nombre_empresa}
              logoId={tenant?.logo_id}
              usuario={usuario}
              onLogout={logout}
              abierto={menuAbierto}
              onCerrar={cerrarMenu}
              puede={puede}
              badges={badgesDeAvisos(avisos)}
            />
          )}

          <main className="main">
            {/* Barra superior: el botón del cajón vive aquí y no en el
                encabezado de cada pantalla porque el sidebar se vuelve cajón
                desde 1100 px: así se puede abrir el menú en todas. */}
            <BarraSuperior
              modulos={modulos}
              avisos={avisos}
              menuAbierto={menuAbierto}
              onAbrirMenu={abrirMenu}
              nombreEmpresa={tenant?.nombre_empresa}
              enfocado={enfocado ? { usuario, onLogout: logout } : null}
            />

            {/* Vista: entra con fade + 8 px desde abajo (CSS .vista) y sale
                con despedirVista. La key por ruta hace que cada pantalla nueva
                la corra UNA vez; StrictMode no remonta nodos del DOM, así que
                no se repite. Es un div con caja propia a propósito: con
                `display: contents` no habría nada que animar. */}
            <div key={pathname} ref={refVista} className="vista main__contenido">
              <Outlet />
            </div>
            {/* Pie legal FUERA de .vista: no entra ni sale con cada pantalla. */}
            <PieLegal className="main__pie" />
          </main>
        </div>
      </div>

      {/* Velo del cajón: solo opacidad, y sin capturar clics cuando está oculto. */}
      <div className={`velo ${menuAbierto ? "velo--visible" : ""}`} onClick={cerrarMenu} role="presentation" />

      {!enfocado && (
        <nav className="tabbar" aria-label="Navegación rápida">
          {accesos.map((hoja) => (
            <NavLink key={hoja.path} to={hoja.path} end className={({ isActive }) => `tab ${isActive ? "tab--activo" : ""}`}>
              <hoja.icon size={20} aria-hidden="true" />
              {hoja.path === "/" ? "Inicio" : hoja.label}
            </NavLink>
          ))}
          <button type="button" className="tab" onClick={abrirMenu} aria-label="Abrir menú">
            <Menu size={20} aria-hidden="true" />
            Menú
          </button>
        </nav>
      )}
    </>
  );
}
