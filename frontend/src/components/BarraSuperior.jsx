import { Menu } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { avisosDeEstado } from "@/context/AvisosContext";
import { enlaceDeAviso } from "@/modules/dashboard/avisos";
import { BRANDING } from "@/config/branding";

// Píldoras de estado que caben a la derecha: las demás viven en el panel de
// avisos del dashboard.
const MAXIMO_PILDORAS = 2;

/** ¿La ruta actual está dentro de este enlace? */
function coincide(pathname, path) {
  return path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(`${path}/`);
}

/** "Compras · Productos" para la ruta actual, con los módulos que ya ve el usuario. */
function seccionActual(modulos, pathname) {
  for (const modulo of modulos) {
    if (modulo.hijos) {
      // El hijo más específico gana: /compras/productos no es "Compras".
      const hijo = [...modulo.hijos].sort((a, b) => b.path.length - a.path.length).find((h) => coincide(pathname, h.path));
      if (hijo) return hijo.label === modulo.label ? [modulo.label] : [modulo.label, hijo.label];
    } else if (coincide(pathname, modulo.path)) {
      return [modulo.label];
    }
  }
  return [];
}

/**
 * BARRA SUPERIOR (2026-10-01): fondo blanco con borde inferior de 1 px. A la
 * izquierda, el botón del cajón (solo cuando el sidebar está oculto) y la
 * sección en la que se está; a la derecha, píldoras de estado con borde fino
 * y punto indicador ("1 producto bajo el mínimo"), que llevan a lo que
 * avisan. Los avisos son los del panel del dashboard (AvisosProvider): no
 * cuestan ninguna petición extra.
 */
export default function BarraSuperior({ modulos, avisos, menuAbierto, onAbrirMenu, nombreEmpresa }) {
  const { pathname } = useLocation();
  const seccion = seccionActual(modulos, pathname);
  const estado = avisosDeEstado(avisos).slice(0, MAXIMO_PILDORAS);

  return (
    <header className="barra-superior">
      <button
        type="button"
        className="iconbtn menu-btn"
        onClick={onAbrirMenu}
        aria-label="Abrir menú"
        aria-expanded={menuAbierto}
      >
        <Menu size={18} aria-hidden="true" />
      </button>

      <p className="barra-superior__seccion">
        <span className="barra-superior__empresa">{nombreEmpresa ?? BRANDING.nombre}</span>
        {seccion.map((parte) => (
          <span key={parte} className="barra-superior__parte">
            {parte}
          </span>
        ))}
      </p>

      {estado.length > 0 && (
        <ul className="barra-superior__estado" aria-label="Estado del negocio">
          {estado.map((aviso) => {
            const enlace = enlaceDeAviso(aviso.enlace);
            const contenido = (
              <>
                <span className={`pildora-estado__punto pildora-estado__punto--${aviso.nivel}`} aria-hidden="true" />
                {aviso.titulo}
              </>
            );
            return (
              <li key={aviso.clave}>
                {enlace ? (
                  <Link to={enlace.a} className="pildora-estado" title={aviso.texto}>
                    {contenido}
                  </Link>
                ) : (
                  <span className="pildora-estado" title={aviso.texto}>
                    {contenido}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </header>
  );
}
