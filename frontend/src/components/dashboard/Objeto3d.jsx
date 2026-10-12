import { useId } from "react";

/**
 * OBJETOS 3D del dashboard — los mismos SVG de la maqueta
 * (docs/dashboard-referencia.html): una esfera, un cubo, un cilindro y un cono
 * con sombreado y sombra proyectada. Son vectores locales, sin enlaces
 * externos y sin librería 3D: el volumen lo da el degradado, no una malla.
 *
 * Los colores NO van en atributos: un atributo de presentación SVG no resuelve
 * `var(--x)` (solo funciona cuando el color se aplica por CSS). Cada pieza
 * lleva una clase y el color sale de los tokens en dashboard.css, así los
 * objetos siguen el modo claro/oscuro y el color de marca del tenant.
 *
 * Cada objeto es estático salvo la flotación suave, que es una de las dos
 * únicas animaciones en bucle que el producto permite (la otra es el halo del
 * punto de la gráfica). El desfase se pasa como `--retardo` para que no suban
 * y bajen a la vez.
 */

// Cuatro formas, cada una con su paleta, igual que en la maqueta. Se reparten
// por posición en la rejilla: la primera categoría lleva la esfera, la segunda
// el cubo, y así. Al no depender del nombre de la categoría, un tenant con
// categorías distintas ve exactamente la misma composición.
export const FORMAS_3D = ["esfera", "cubo", "cilindro", "cono"];

export function formaPorIndice(indice = 0) {
  return FORMAS_3D[indice % FORMAS_3D.length];
}

function Esfera({ id }) {
  return (
    <>
      <defs>
        <radialGradient id={id} cx="38%" cy="32%" r="70%">
          <stop className="objeto3d__luz" offset="0%" />
          <stop className="objeto3d__medio" offset="35%" />
          <stop className="objeto3d__sombra-tono" offset="75%" />
          <stop className="objeto3d__fondo-tono" offset="100%" />
        </radialGradient>
      </defs>
      <ellipse className="objeto3d__piso" cx="32" cy="46" rx="15" ry="3" />
      <circle cx="32" cy="24" r="17" fill={`url(#${id})`} />
    </>
  );
}

function Cubo() {
  return (
    <>
      <ellipse className="objeto3d__piso" cx="32" cy="46" rx="16" ry="3" />
      <polygon className="objeto3d__cara-alta" points="32,6 50,15 32,24 14,15" />
      <polygon className="objeto3d__cara-frente" points="14,15 32,24 32,42 14,33" />
      <polygon className="objeto3d__cara-lado" points="50,15 32,24 32,42 50,33" />
    </>
  );
}

function Cilindro({ id }) {
  return (
    <>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
          <stop className="objeto3d__sombra-tono" offset="0%" />
          <stop className="objeto3d__luz" offset="45%" />
          <stop className="objeto3d__fondo-tono" offset="100%" />
        </linearGradient>
      </defs>
      <ellipse className="objeto3d__piso" cx="32" cy="46" rx="14" ry="3" />
      <path d="M19 12v26a13 4.5 0 0026 0V12Z" fill={`url(#${id})`} />
      <ellipse className="objeto3d__cara-alta" cx="32" cy="12" rx="13" ry="4.5" />
    </>
  );
}

function Cono() {
  return (
    <>
      <ellipse className="objeto3d__piso" cx="32" cy="46" rx="16" ry="3" />
      <polygon className="objeto3d__cara-lado" points="32,5 50,40 32,44" />
      <polygon className="objeto3d__cara-alta" points="32,5 32,44 14,40" />
    </>
  );
}

const CUERPOS = { esfera: Esfera, cubo: Cubo, cilindro: Cilindro, cono: Cono };

/**
 * @param forma    esfera | cubo | cilindro | cono
 * @param retardo  desfase de la flotación, en segundos
 * @param flotar   false para dejarlo completamente quieto
 */
export default function Objeto3d({ forma = "esfera", retardo = 0, flotar = true }) {
  const id = `o3d-${forma}-${useId().replace(/:/g, "")}`;
  const Cuerpo = CUERPOS[forma] ?? Esfera;

  return (
    <span className={`lienzo-3d lienzo-3d--${forma}`} aria-hidden="true">
      <svg
        className={`objeto3d objeto3d--${forma} ${flotar ? "objeto3d--flota" : ""}`}
        style={{ "--retardo": `${retardo}s` }}
        width="64"
        height="52"
        viewBox="0 0 64 52"
        focusable="false"
      >
        <Cuerpo id={id} />
      </svg>
    </span>
  );
}

/**
 * Miniaturas de la lista de más vendidos: los cuatro iconos de línea de la
 * maqueta, sobre un fondo con volumen. El trazo usa `currentColor`, así que el
 * color lo pone la clase del marco (`.dash-miniatura--n`) desde dashboard.css.
 */
const TRAZOS_MINIATURA = [
  // Caja isométrica
  <path
    key="caja"
    d="M4 8l8-4 8 4-8 4-8-4Zm0 0v8l8 4m0-12v12m8-12v8l-8 4"
    stroke="currentColor"
    strokeWidth="1.3"
    strokeLinejoin="round"
  />,
  // Bolsa / envase
  <g key="bolsa">
    <path d="M9 3h6l1 4H8l1-4Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    <path
      d="M6 7h12l-1.2 13.2a2 2 0 01-2 1.8H9.2a2 2 0 01-2-1.8L6 7Z"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinejoin="round"
    />
  </g>,
  // Panel / superficie
  <g key="panel">
    <rect x="4" y="6" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.3" />
    <path d="M4 10h16" stroke="currentColor" strokeWidth="1.3" />
  </g>,
  // Estrella / destacado
  <path
    key="estrella"
    d="M12 3l2.6 5.4 5.9.8-4.3 4.2 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.2l5.9-.8L12 3Z"
    stroke="currentColor"
    strokeWidth="1.2"
    strokeLinejoin="round"
  />,
];

export function MiniaturaProducto({ indice = 0, retardo = 0 }) {
  const tono = indice % TRAZOS_MINIATURA.length;
  return (
    <span className={`dash-miniatura dash-miniatura--${tono}`} aria-hidden="true">
      <svg
        className="dash-miniatura__icono objeto3d--flota"
        style={{ "--retardo": `${retardo}s` }}
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        focusable="false"
      >
        {TRAZOS_MINIATURA[tono]}
      </svg>
    </span>
  );
}
