import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronDown, LogOut, Moon, Sun, X } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

import { etiquetaDePlan, modulosVisibles } from "@/config/modules";
import { useDeslizarHermanos } from "@/hooks/useDeslizarHermanos";
import {
  CURVA_SUAVE,
  RESORTE,
  RESORTE_DURACION,
  hayMovimientoReducido,
  puedeAnimar,
  trasladoVisual,
} from "@/lib/movimiento";
import { useTheme } from "@/theme/ThemeContext";
import { BRANDING } from "@/config/branding";
import { urlImagen } from "@/lib/imagenes";

// Lo que tardan los submódulos en irse al cerrar un grupo (CSS: 120 ms, con
// un margen para que el último cuadro se pinte antes de desmontar).
const SALIDA_GRUPO_MS = 130;

/**
 * SIDEBAR — rediseño monocromático (2026-10-01): fondo blanco con borde
 * derecho de 1 px, marca arriba, secciones con título en mayúsculas de 11 px
 * (los grupos desplegables), ítem activo como píldora gris con texto en 600,
 * badges numéricos redondos a la derecha y, abajo, separado por una línea,
 * el bloque de usuario (avatar, nombre y rol) con tema y cierre de sesión.
 *
 * Las rutas y los submódulos son los que ya existen: salen de
 * config/modules.js y se filtran por el plan del tenant, así que agregar un
 * módulo sigue siendo tocar ese archivo y App.jsx, nada más.
 *
 * Grupos: TODOS arrancan cerrados en cada carga (no se recuerda nada entre
 * recargas ni se abren solos al navegar) y solo hay uno abierto a la vez:
 * abrir un grupo cierra el anterior. Decisión del usuario del 2026-09-27.
 *
 * Movimiento (docs/DECISIONES.md, 2026-09-28), todo con transform y opacity:
 * - Indicador del ítem activo: UN nodo que se desliza al destino (FLIP a
 *   mano con el resorte), nunca una píldora que aparece y desaparece.
 * - Grupo: el chevron rota; los hijos entran en cascada y, al cerrar, se van
 *   antes de desmontarse; los grupos de abajo se deslizan a su sitio nuevo
 *   (useDeslizarHermanos) en vez de saltar. El alto del panel NO se anima.
 * - Al cargar, marca, ítems y pie entran en cascada (50 ms entre uno y otro).
 * - Badge numérico: destello breve (escala + opacidad, WAAPI) cuando su
 *   número CAMBIA; al montar no hace nada.
 */

/**
 * Badge numérico redondo (avisos del negocio: stock bajo, comandas demoradas en
 * cocina). El número es visual; el lector de pantalla oye "N avisos".
 */
function InsigniaNumero({ valor }) {
  const ref = useRef(null);
  const previo = useRef(valor);
  useLayoutEffect(() => {
    if (previo.current === valor) return;
    previo.current = valor;
    const nodo = ref.current;
    if (!nodo || !puedeAnimar(nodo)) return;
    nodo.animate(
      [
        { transform: "scale(1.35)", opacity: 0.55 },
        { transform: "scale(1)", opacity: 1 },
      ],
      { duration: 420, easing: `cubic-bezier(${CURVA_SUAVE.join(", ")})` }
    );
  }, [valor]);
  if (!valor) return null;
  return (
    <span className="insignia-num" ref={ref}>
      <span aria-hidden="true">{valor > 99 ? "99+" : valor}</span>
      <span className="sr-only">, {valor === 1 ? "1 aviso" : `${valor} avisos`}</span>
    </span>
  );
}

function iniciales(nombre = "") {
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return "?";
  return (partes[0][0] + (partes[1]?.[0] ?? "")).toUpperCase();
}

/**
 * ¿Dónde va el indicador? En el enlace activo de primer nivel; si la ruta es
 * de un grupo, en su submódulo si el grupo está abierto y, si no, en la
 * cabecera del grupo. Un panel que se está yendo ya no cuenta.
 */
function destinoDelIndicador(nav) {
  return (
    nav.querySelector(".sidebar__panel-interior:not(.sidebar__panel-interior--saliendo) .navsub.sidebar__activo") ??
    nav.querySelector(".navitem.sidebar__activo") ??
    nav.querySelector(".grupo-cabeza--con-ruta-activa")
  );
}

/**
 * Coloca el indicador en su destino. Con `animar`, lo desliza DESDE donde se
 * ve ahora (aunque vaya a media animación): FLIP con translate3d y la
 * diferencia de alto como scaleY. El alto real se fija de una vez.
 */
function colocarIndicador(nav, indicador, animar) {
  const destino = destinoDelIndicador(nav);
  if (!destino) {
    indicador.classList.remove("sidebar__indicador--visible");
    return;
  }
  const y = destino.offsetTop;
  const alto = destino.offsetHeight;
  const estabaVisible = indicador.classList.contains("sidebar__indicador--visible");

  // Posición visual actual, antes de tocar nada.
  const visual = trasladoVisual(indicador);
  const altoPrevio = parseFloat(indicador.style.height) || alto;
  const desdeY = visual.y;
  const desdeAlto = altoPrevio * visual.escalaY;

  indicador.getAnimations?.().forEach((a) => a.cancel());
  indicador.style.height = `${alto}px`;
  indicador.style.transform = `translate3d(0, ${y}px, 0)`;
  indicador.dataset.cara = destino.classList.contains("navitem") ? "fuerte" : "sutil";
  indicador.classList.add("sidebar__indicador--visible");

  const seMueve = Math.abs(desdeY - y) > 0.5 || Math.abs(desdeAlto - alto) > 0.5;
  if (animar && estabaVisible && seMueve && puedeAnimar(indicador)) {
    indicador.animate(
      [
        { transform: `translate3d(0, ${desdeY}px, 0) scaleY(${desdeAlto / alto})` },
        { transform: `translate3d(0, ${y}px, 0) scaleY(1)` },
      ],
      { duration: RESORTE_DURACION, easing: RESORTE }
    );
  }
}

/** ¿La ruta actual está dentro de este enlace? */
function coincide(pathname, path) {
  return path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(`${path}/`);
}

function EnlaceSimple({ modulo, onNavegar, orden, badges }) {
  const Icono = modulo.icon;
  return (
    <NavLink
      to={modulo.path}
      end={modulo.path === "/"}
      onClick={onNavegar}
      style={{ "--i": orden }}
      className={({ isActive }) => `navitem sidebar__cascada ${isActive ? "sidebar__activo" : ""}`}
    >
      <Icono size={17} aria-hidden="true" />
      <span>{modulo.label}</span>
      <InsigniaNumero valor={badges?.[modulo.key]} />
    </NavLink>
  );
}

function GrupoDesplegable({ modulo, abierto, onAlternar, onNavegar, orden, badges }) {
  const { pathname } = useLocation();
  const contieneRutaActiva = modulo.hijos.some((h) => coincide(pathname, h.path));
  const idPanel = `sidebar-grupo-${modulo.key}`;

  // El panel sigue montado mientras sus hijos se van (SALIDA_GRUPO_MS). En
  // ese rato ya no es navegable: aria-hidden + inert desde el mismo clic.
  const [montado, setMontado] = useState(abierto);
  if (abierto && !montado) setMontado(true);
  useEffect(() => {
    if (abierto || !montado) return undefined;
    if (hayMovimientoReducido()) {
      setMontado(false);
      return undefined;
    }
    const salida = setTimeout(() => setMontado(false), SALIDA_GRUPO_MS);
    return () => clearTimeout(salida);
  }, [abierto, montado]);
  const saliendo = montado && !abierto;
  // Cerrado, el título de la sección suma los badges de sus submódulos.
  const totalGrupo = modulo.hijos.reduce((suma, h) => suma + (badges?.[h.key] ?? 0), 0);

  return (
    <div className="sidebar__grupo sidebar__cascada" style={{ "--i": orden }}>
      <button
        type="button"
        onClick={onAlternar}
        aria-expanded={abierto}
        aria-controls={idPanel}
        className={`grupo-cabeza ${contieneRutaActiva ? "grupo-cabeza--con-ruta-activa" : ""}`}
      >
        <span>{modulo.label}</span>
        {!abierto && <InsigniaNumero valor={totalGrupo} />}
        <ChevronDown
          size={12}
          className={`sidebar__chevron ${abierto ? "sidebar__chevron--abierto" : ""}`}
          aria-hidden="true"
        />
      </button>

      {montado && (
        <div
          id={idPanel}
          className={`sidebar__panel-interior ${saliendo ? "sidebar__panel-interior--saliendo" : ""}`}
          aria-hidden={saliendo || undefined}
          inert={saliendo || undefined}
        >
          {modulo.hijos.map((hijo, i) => (
            <NavLink
              key={hijo.key}
              to={hijo.path}
              end={hijo.path === modulo.path}
              onClick={onNavegar}
              // El retardo escalonado se pasa como token, no como estilo
              // calculado en JS por cuadro: lo aplica CSS una sola vez.
              style={{ "--d": `${i * 0.04}s` }}
              className={({ isActive }) => `navsub ${isActive ? "sidebar__activo" : ""}`}
            >
              <span>{hijo.label}</span>
              <InsigniaNumero valor={badges?.[hijo.key]} />
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Sidebar({
  plan = "basico",
  modulosActivos = [],
  nombreEmpresa = BRANDING.nombre,
  logoId = null,
  usuario,
  onLogout,
  abierto = false,
  onCerrar,
  puede = null,
  badges = null,
}) {
  // `puede` (del rol) oculta lo que el usuario no puede ver; sin él, todo lo del plan.
  const modulos = modulosVisibles(plan, modulosActivos, puede);
  const { esOscuro, alternarModo } = useTheme();
  // Clave del ÚNICO grupo abierto, o null. Nace siempre en null.
  const [grupoAbierto, setGrupoAbierto] = useState(null);

  const alternarGrupo = useCallback((key) => {
    setGrupoAbierto((actual) => (actual === key ? null : key));
  }, []);

  // Indicador deslizante: se recoloca al cambiar de ruta o de grupo, y cada
  // vez que la lista se reacomoda (con la misma curva que los hermanos).
  const { pathname } = useLocation();
  const refNav = useRef(null);
  const refIndicador = useRef(null);
  const yaColocado = useRef(false);
  const recolocar = useCallback(() => {
    if (refNav.current && refIndicador.current) colocarIndicador(refNav.current, refIndicador.current, true);
  }, []);
  useLayoutEffect(() => {
    if (!refNav.current || !refIndicador.current) return;
    // La primera vez se coloca sin deslizar: entra con la cascada del marco.
    colocarIndicador(refNav.current, refIndicador.current, yaColocado.current);
    yaColocado.current = true;
  }, [pathname, grupoAbierto]);
  useDeslizarHermanos(refNav, recolocar);

  const inicial = (nombreEmpresa || "JS").trim().charAt(0).toUpperCase() || "J";

  return (
    <aside
      className={`sidebar ${abierto ? "sidebar--abierto" : ""}`}
      aria-label="Navegación principal"
    >
      <div className="sidebar__interior">
        <div className="marca sidebar__cascada" style={{ "--i": 0 }}>
          <span className={`marca__sello${logoId ? " marca__sello--logo" : ""}`} aria-hidden="true">
            {logoId ? <img src={urlImagen(logoId)} alt="" width={34} height={34} /> : inicial}
          </span>
          <div className="min-w-0">
            <p className="marca__nombre truncate">{nombreEmpresa}</p>
            <p className="marca__sub">{BRANDING.nombre}</p>
          </div>
          <button type="button" className="iconbtn menu-btn ml-auto" onClick={onCerrar} aria-label="Cerrar menú">
            <X size={15} aria-hidden="true" />
          </button>
        </div>

        <nav aria-label="Módulos" className="sidebar__nav" ref={refNav}>
          <span className="sidebar__indicador" ref={refIndicador} aria-hidden="true" data-sin-deslizar="">
            <span className="sidebar__indicador-cara sidebar__indicador-cara--fuerte" />
            <span className="sidebar__indicador-cara sidebar__indicador-cara--sutil" />
          </span>
          {modulos.map((modulo, i) =>
            modulo.hijos ? (
              <GrupoDesplegable
                key={modulo.key}
                modulo={modulo}
                orden={i + 1}
                abierto={grupoAbierto === modulo.key}
                onAlternar={() => alternarGrupo(modulo.key)}
                onNavegar={onCerrar}
                badges={badges}
              />
            ) : (
              <EnlaceSimple key={modulo.key} modulo={modulo} orden={i + 1} onNavegar={onCerrar} badges={badges} />
            )
          )}
        </nav>

        <div className="sidebar__pie sidebar__cascada" style={{ "--i": modulos.length + 1 }}>
          {usuario && (
            <div className="sidebar__usuario">
              <span className="sidebar__avatar" aria-hidden="true">
                {iniciales(usuario.nombre_completo)}
              </span>
              <span className="sidebar__usuario-texto">
                <span className="sidebar__usuario-nombre truncate">{usuario.nombre_completo}</span>
                <span className="sidebar__usuario-rol truncate">
                  {usuario.rol_nombre ?? "Sin rol"} · Plan {etiquetaDePlan(plan)}
                </span>
              </span>
            </div>
          )}
          <div className="sidebar__pie-acciones">
            <button
              type="button"
              className="iconbtn iconbtn--plano"
              onClick={alternarModo}
              aria-label={esOscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
              title={esOscuro ? "Modo claro" : "Modo oscuro"}
            >
              {esOscuro ? <Sun size={15} aria-hidden="true" /> : <Moon size={15} aria-hidden="true" />}
            </button>
            {usuario && (
              <button
                type="button"
                className="iconbtn iconbtn--plano"
                onClick={onLogout}
                aria-label="Cerrar sesión"
                title="Cerrar sesión"
              >
                <LogOut size={15} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
