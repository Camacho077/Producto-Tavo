import { useEffect, useId, useRef } from "react";

import { formatearMoneda } from "@/lib/formato";
import { curvaSuave, hayMovimientoReducido, lerp } from "@/lib/movimiento";
import { useTokensGrafica } from "@/hooks/useTokensGrafica";

import "./charts.css";

/**
 * GRÁFICA DE RENDIMIENTO — ventas del periodo, comparativa del periodo
 * anterior y proyección, con línea guía, punto y tooltip que siguen al cursor.
 *
 * Cómo está hecha y POR QUÉ (son las reglas de rendimiento de la maqueta,
 * docs/dashboard-referencia.html; no deshacer sin volver a medir):
 *
 * 1. NO se animan atributos SVG por CSS (`d`, `cx`, `x1`, `r`). Eso solo
 *    funciona en Chrome; en Firefox el valor salta de golpe al final. Al
 *    cambiar de rango, los puntos se INTERPOLAN en JavaScript con
 *    requestAnimationFrame y se escribe el `d` ya calculado en cada cuadro.
 *
 * 2. El punto, el halo, la línea guía y el tooltip NO van dentro del SVG: son
 *    cuatro divs en una capa HTML por encima, movidos con `translate3d`. Así
 *    los mueve el compositor sin repintar el SVG entero en cada mousemove.
 *
 * 3. Nada de esto pasa por el estado de React. Un tooltip que siguiera al
 *    cursor con `useState` provocaría un render del dashboard completo por
 *    cuadro; aquí se escriben tres `style.transform` y dos `textContent`.
 *
 * 4. `pointermove` se limita a UN cálculo por cuadro con requestAnimationFrame.
 *
 * 5. Las animaciones de entrada (el trazo que se dibuja, el área que sube)
 *    corren UNA vez al montar y se quedan quietas. Los únicos bucles son el
 *    halo del punto y la flotación de las miniaturas del inventario.
 *
 * 6. Con `prefers-reduced-motion` no hay interpolación: el rango nuevo se
 *    dibuja de una vez.
 *
 * 7. Mientras la curva morfea, la capa HTML lleva `grafica__capa--morfeo`, que
 *    le QUITA su transición: el punto se escribe en cada cuadro exactamente
 *    sobre la curva. Con la transición puesta, cada escritura la reiniciaba y
 *    el punto y el tooltip se quedaban detrás de la línea. La transición
 *    (el resorte) solo actúa en el hover, para que el tooltip se deslice de
 *    un punto al siguiente.
 */

// Geometría. `HUECO_PROYECCION` es cuánto sobresale el tramo punteado de la
// proyección más allá del último dato real, medido en pasos entre puntos.
const PAD_ARRIBA = 16; // sitio para que el punto y su halo no se corten
const PAD_ABAJO = 10;
const HUECO_PROYECCION = 0.7;
const LINEAS_GRID = 4;
const ETIQUETAS_EJE = 5;
// Movimiento de dato: --dur-dato en index.css.
const DURACION_MORFEO = 700;
const ALTURA_POR_DEFECTO = 260;


/**
 * Remuestrea una serie a `n` puntos conservando su forma. Hace falta porque
 * los rangos tienen distinto número de puntos (24 horas, 7 días, 12 meses) y
 * para interpolar entre dos series hay que compararlas punto a punto.
 */
function remuestrear(origen, n) {
  if (n <= 0) return [];
  if (!origen.length) return new Array(n).fill(0);
  if (origen.length === n) return origen.slice();
  if (origen.length === 1 || n === 1) return new Array(n).fill(origen[0]);
  const destino = new Array(n);
  for (let i = 0; i < n; i += 1) {
    const posicion = (i / (n - 1)) * (origen.length - 1);
    const base = Math.floor(posicion);
    const resto = posicion - base;
    destino[i] = base + 1 < origen.length ? lerp(origen[base], origen[base + 1], resto) : origen[base];
  }
  return destino;
}

/** El techo de la escala. Nunca 0: con todo en cero la división reventaría y
 *  la línea se iría al infinito. */
function techo({ actual, anterior, proyeccion }) {
  const maximo = Math.max(0, ...actual, ...anterior, proyeccion);
  return maximo > 0 ? maximo * 1.12 : 1;
}

function estadoDeSerie(serie) {
  const puntos = serie?.puntos ?? [];
  const base = {
    actual: puntos.map((p) => Number(p.actual) || 0),
    anterior: puntos.map((p) => Number(p.anterior) || 0),
    proyeccion: Number(serie?.proyeccion?.valor) || 0,
  };
  return { ...base, maximo: techo(base) };
}

export default function GraficaRendimiento({
  serie,
  etiquetaDe = (iso) => iso,
  etiquetaActual = "Periodo actual",
  etiquetaAnterior = "Periodo anterior",
  etiquetaProyeccion = "Proy.",
  altura = ALTURA_POR_DEFECTO,
}) {
  const idArea = `area-${useId().replace(/:/g, "")}`;
  const color = useTokensGrafica();

  // Nodos que se escriben a mano, fuera del ciclo de render de React.
  const caja = useRef(null);
  const svg = useRef(null);
  const refArea = useRef(null);
  const refAnterior = useRef(null);
  const refLinea = useRef(null);
  const refProyeccion = useRef(null);
  const refEtiquetaProy = useRef(null);
  const refGrid = useRef(null);
  const refGuia = useRef(null);
  const refHalo = useRef(null);
  const refPunto = useRef(null);
  const refTip = useRef(null);
  const refTipCaja = useRef(null);
  const refTipEtiqueta = useRef(null);
  const refTipActual = useRef(null);
  const refTipAnterior = useRef(null);
  const refEje = useRef(null);
  const refCapa = useRef(null);

  // Estado de dibujo. Vive en refs a propósito: cambia 60 veces por segundo
  // durante la transición y no debe provocar ni un render.
  const estado = useRef(estadoDeSerie(serie));
  const medidas = useRef({ ancho: 0, alto: altura });
  const hover = useRef(null);
  const morfeo = useRef(0);
  const morfar = useRef(null);
  // La serie inicial ya está pintada por el efecto de montaje: la primera
  // llamada no tiene nada que interpolar.
  const yaMontado = useRef(false);
  const cuadroHover = useRef(0);
  const ultimoX = useRef(0);
  const mitadTip = useRef(64);
  const altoTip = useRef(64);
  // Las etiquetas del eje y los textos del tooltip se leen de aquí, no del
  // cierre: así el efecto de dibujo no depende de las props y no se reinstala.
  const datos = useRef({ serie, etiquetaDe });
  datos.current = { serie, etiquetaDe };

  useEffect(() => {
    const contenedor = caja.current;
    if (!contenedor) return undefined;

    const paso = () => {
      const { ancho } = medidas.current;
      const n = estado.current.actual.length;
      // Con un solo punto no hay paso que calcular; se deja el ancho entero.
      return ancho / Math.max(1, n - 1 + HUECO_PROYECCION);
    };

    const y = (valor) => {
      const { alto } = medidas.current;
      const util = Math.max(1, alto - PAD_ARRIBA - PAD_ABAJO);
      const proporcion = Math.min(1, Math.max(0, valor / estado.current.maximo));
      return alto - PAD_ABAJO - proporcion * util;
    };

    const trazo = (valores) => {
      const s = paso();
      return `M${valores.map((v, i) => `${(i * s).toFixed(1)},${y(v).toFixed(1)}`).join(" L")}`;
    };

    const mover = (nodo, x, alturaY) => {
      if (nodo) nodo.style.transform = `translate3d(${x.toFixed(1)}px,${alturaY.toFixed(1)}px,0)`;
    };

    /** Coloca la capa HTML (guía, halo, punto, tooltip). Solo transform y texto. */
    const colocarCapa = () => {
      const { actual, anterior } = estado.current;
      if (!actual.length) return;
      const s = paso();
      const i = hover.current == null ? actual.length - 1 : Math.min(hover.current, actual.length - 1);
      const x = i * s;
      const alturaY = y(actual[i]);

      const { serie: serieActiva, etiquetaDe: formatear } = datos.current;
      const punto = serieActiva?.puntos?.[i];
      if (punto && refTipEtiqueta.current) {
        refTipEtiqueta.current.textContent = formatear(punto.inicio);
      }
      if (refTipActual.current) refTipActual.current.textContent = formatearMoneda(actual[i]);
      if (refTipAnterior.current) refTipAnterior.current.textContent = formatearMoneda(anterior[i] ?? 0);

      // Las medidas del tooltip solo se leen cuando está quieto: hacerlo
      // durante la transición forzaría un cálculo de estilo por cuadro.
      if (!morfeo.current && refTipCaja.current) {
        mitadTip.current = refTipCaja.current.offsetWidth / 2 || mitadTip.current;
        altoTip.current = refTipCaja.current.offsetHeight || altoTip.current;
      }
      const { ancho } = medidas.current;
      const xTip = Math.min(Math.max(x, mitadTip.current - 18), Math.max(0, ancho - mitadTip.current + 18));
      // Si el punto está tan arriba que el tooltip se saldría del panel (un
      // pico al final de la serie tapaba las píldoras de rango), se voltea.
      refTipCaja.current?.classList.toggle("grafica__tip--abajo", alturaY - altoTip.current - 16 < 0);

      mover(refGuia.current, x, 0);
      mover(refPunto.current, x, alturaY);
      mover(refHalo.current, x, alturaY);
      mover(refTip.current, xTip, alturaY);
      if (refPunto.current) {
        refPunto.current.firstChild?.classList.toggle("grafica__punto--activo", hover.current != null);
      }
    };

    /** Escribe los `d` del cuadro actual. Nunca hay CSS animando estos atributos. */
    const dibujar = () => {
      const { ancho, alto } = medidas.current;
      if (!ancho || !alto) return;
      const { actual, anterior, proyeccion } = estado.current;
      if (!actual.length) return;

      svg.current?.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);

      const s = paso();
      const finX = (actual.length - 1) * s;
      const finY = y(actual[actual.length - 1]);
      const linea = trazo(actual);
      const base = (alto - PAD_ABAJO).toFixed(1);

      refLinea.current?.setAttribute("d", linea);
      refArea.current?.setAttribute("d", `${linea} L${finX.toFixed(1)},${base} L0,${base} Z`);
      refAnterior.current?.setAttribute("d", trazo(anterior));

      // Proyección: un tramo corto que nace en el último dato real y sale del
      // área de la serie, siempre punteado y con su etiqueta.
      const proyX = finX + s * HUECO_PROYECCION;
      const proyY = y(proyeccion);
      refProyeccion.current?.setAttribute("d", `M${finX.toFixed(1)},${finY.toFixed(1)} L${proyX.toFixed(1)},${proyY.toFixed(1)}`);
      if (refEtiquetaProy.current) {
        refEtiquetaProy.current.setAttribute("x", (proyX - 2).toFixed(1));
        refEtiquetaProy.current.setAttribute("y", Math.max(12, proyY - 10).toFixed(1));
      }

      // Rejilla: cuatro líneas repartidas en el área útil, cortadas donde
      // termina el dato real para que no invadan la proyección.
      const lineas = refGrid.current?.children ?? [];
      for (let i = 0; i < lineas.length; i += 1) {
        const gy = (PAD_ARRIBA + ((alto - PAD_ARRIBA - PAD_ABAJO) / LINEAS_GRID) * i).toFixed(1);
        lineas[i].setAttribute("x1", "0");
        lineas[i].setAttribute("x2", finX.toFixed(1));
        lineas[i].setAttribute("y1", gy);
        lineas[i].setAttribute("y2", gy);
      }

      colocarCapa();
    };

    /** Etiquetas del eje: cinco, repartidas. Se escriben como texto, sin render. */
    const escribirEje = () => {
      const spans = refEje.current?.children ?? [];
      const { serie: serieActiva, etiquetaDe: formatear } = datos.current;
      const puntos = serieActiva?.puntos ?? [];
      for (let i = 0; i < spans.length; i += 1) {
        const indice = puntos.length
          ? Math.round((i / (ETIQUETAS_EJE - 1)) * (puntos.length - 1))
          : 0;
        spans[i].textContent = puntos[indice] ? formatear(puntos[indice].inicio) : "";
      }
    };

    /** Transición entre rangos: se interpolan los VALORES y también la escala,
     *  porque un rango anual y uno diario no tienen el mismo techo. */
    const morfarHacia = (destino) => {
      cancelAnimationFrame(morfeo.current);
      morfeo.current = 0;
      const capa = refCapa.current;

      if (hayMovimientoReducido()) {
        estado.current = destino;
        dibujar();
        return;
      }

      const n = destino.actual.length;
      const desde = {
        actual: remuestrear(estado.current.actual, n),
        anterior: remuestrear(estado.current.anterior, n),
        proyeccion: estado.current.proyeccion,
        maximo: estado.current.maximo,
      };

      capa?.classList.add("grafica__capa--morfeo");
      let inicio;
      const cuadro = (marca) => {
        if (inicio === undefined) inicio = marca;
        const avance = Math.min(1, (marca - inicio) / DURACION_MORFEO);
        const t = curvaSuave(avance);
        estado.current = {
          actual: desde.actual.map((v, i) => lerp(v, destino.actual[i], t)),
          anterior: desde.anterior.map((v, i) => lerp(v, destino.anterior[i], t)),
          proyeccion: lerp(desde.proyeccion, destino.proyeccion, t),
          maximo: lerp(desde.maximo, destino.maximo, t),
        };
        dibujar();
        if (avance < 1) {
          morfeo.current = requestAnimationFrame(cuadro);
        } else {
          morfeo.current = 0;
          estado.current = destino;
          dibujar();
          capa?.classList.remove("grafica__capa--morfeo");
        }
      };
      morfeo.current = requestAnimationFrame(cuadro);
    };

    // ---- Medida del contenedor: redibuja sin animar y sin cortar un morfeo ----
    const medir = () => {
      const ancho = Math.round(contenedor.clientWidth);
      const alto = Math.round(contenedor.clientHeight) || altura;
      if (!ancho || (ancho === medidas.current.ancho && alto === medidas.current.alto)) return false;
      medidas.current = { ancho, alto };
      return true;
    };

    medir();
    escribirEje();
    dibujar();

    const observador =
      typeof ResizeObserver === "function"
        ? new ResizeObserver(() => {
            if (medir()) dibujar();
          })
        : null;
    observador?.observe(contenedor);

    // ---- Hover: un cálculo por cuadro, jamás uno por evento ----
    const alMover = (evento) => {
      ultimoX.current = evento.clientX;
      if (cuadroHover.current) return;
      cuadroHover.current = requestAnimationFrame(() => {
        cuadroHover.current = 0;
        const n = estado.current.actual.length;
        if (!n) return;
        const caja2 = contenedor.getBoundingClientRect();
        const s = paso();
        const i = Math.max(0, Math.min(n - 1, Math.round((ultimoX.current - caja2.left) / (s || 1))));
        if (i !== hover.current) {
          hover.current = i;
          colocarCapa();
        }
      });
    };
    const alSalir = () => {
      cancelAnimationFrame(cuadroHover.current);
      cuadroHover.current = 0;
      hover.current = null;
      colocarCapa();
    };

    contenedor.addEventListener("pointermove", alMover);
    contenedor.addEventListener("pointerleave", alSalir);

    // El efecto se instala una sola vez; los cambios de serie entran por aquí.
    morfar.current = (destino) => {
      escribirEje();
      morfarHacia(destino);
    };

    return () => {
      cancelAnimationFrame(morfeo.current);
      cancelAnimationFrame(cuadroHover.current);
      observador?.disconnect();
      contenedor.removeEventListener("pointermove", alMover);
      contenedor.removeEventListener("pointerleave", alSalir);
      morfar.current = null;
    };
    // altura no cambia en vida del componente; el resto se lee por refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cada rango nuevo dispara la interpolación. Un solo efecto, una sola
  // dependencia: la serie. No hay estado de React involucrado en la animación.
  useEffect(() => {
    if (!yaMontado.current) {
      yaMontado.current = true;
      return;
    }
    hover.current = null;
    morfar.current?.(estadoDeSerie(serie));
  }, [serie]);

  const hayDatos = (serie?.puntos ?? []).some((p) => p.actual > 0 || p.anterior > 0);

  return (
    <div className="grafica">
      <div
        className="grafica__lienzo"
        ref={caja}
        style={{ height: altura }}
        role="img"
        aria-label={`Ventas por periodo: ${etiquetaActual} frente a ${etiquetaAnterior}, con la proyección del periodo siguiente.`}
      >
        <svg ref={svg} className="grafica__svg" aria-hidden="true" preserveAspectRatio="none">
          <defs>
            <linearGradient id={idArea} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color.acento} stopOpacity="0.26" />
              <stop offset="50%" stopColor={color.acento} stopOpacity="0.09" />
              <stop offset="100%" stopColor={color.acento} stopOpacity="0" />
            </linearGradient>
            {/* Serie actual: la luz entra por la derecha. En unidades del
                lienzo (userSpaceOnUse) y no de la caja del trazo: una serie
                plana tiene caja de alto 0 y con objectBoundingBox el navegador
                no pintaría la línea. */}
            <linearGradient id={`${idArea}-linea`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="100%" y2="0">
              <stop offset="0%" stopColor={color.serieInicio} />
              <stop offset="50%" stopColor={color.serieMedio} />
              <stop offset="100%" stopColor={color.serieFin} />
            </linearGradient>
          </defs>

          <g ref={refGrid} className="grafica__grid" stroke={color.grid} strokeWidth="1" fill="none">
            {Array.from({ length: LINEAS_GRID + 1 }, (_, i) => (
              <line key={i} x1="0" x2="0" y1="0" y2="0" />
            ))}
          </g>

          <path ref={refArea} className="grafica__area" fill={`url(#${idArea})`} />
          <path
            ref={refAnterior}
            className="grafica__anterior"
            fill="none"
            stroke={color.comparacion}
            strokeWidth="2"
            strokeDasharray="5 6"
            strokeLinecap="round"
          />
          {/* pathLength="1" hace que el dibujado del trazo sea independiente
              del largo real del camino, así se ve igual en cualquier ancho y
              en cualquier navegador. */}
          <path
            ref={refLinea}
            className="grafica__linea"
            pathLength="1"
            fill="none"
            stroke={`url(#${idArea}-linea)`}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            ref={refProyeccion}
            className="grafica__proyeccion"
            fill="none"
            stroke={color.acentoLuz}
            strokeWidth="1.8"
            strokeDasharray="2 5"
            strokeLinecap="round"
          />
          <text
            ref={refEtiquetaProy}
            className="grafica__proyeccion-texto"
            fill={color.acentoLuz}
            fontSize="11"
            textAnchor="end"
          >
            {etiquetaProyeccion}
          </text>
        </svg>

        {/* Capa HTML: se mueve con translate3d, nunca repinta el SVG. */}
        <div className="grafica__capa" ref={refCapa} aria-hidden="true">
          <div className="grafica__pos grafica__pos--tarde grafica__pos--columna" ref={refGuia}>
            <div className="grafica__guia" />
          </div>
          <div className="grafica__pos grafica__pos--tarde" ref={refHalo}>
            <div className="grafica__halo" />
          </div>
          <div className="grafica__pos grafica__pos--tarde" ref={refPunto}>
            <div className="grafica__punto" />
          </div>
          <div className="grafica__pos grafica__pos--tarde" ref={refTip}>
            <div className="grafica__tip" ref={refTipCaja}>
              <p className="grafica__tip-fecha" ref={refTipEtiqueta} />
              <p className="grafica__tip-valor cifra" ref={refTipActual} />
              <p className="grafica__tip-anterior">
                {etiquetaAnterior}: <span className="cifra" ref={refTipAnterior} />
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Eje: cinco etiquetas escritas a mano en el efecto de dibujo. */}
      <div className="grafica__eje" ref={refEje}>
        {Array.from({ length: ETIQUETAS_EJE }, (_, i) => (
          <span key={i} />
        ))}
      </div>

      <ul className="grafica__leyenda">
        <li>
          <span className="grafica__muestra grafica__muestra--actual" aria-hidden="true" />
          {etiquetaActual}
        </li>
        <li>
          <span className="grafica__muestra grafica__muestra--anterior" aria-hidden="true" />
          {etiquetaAnterior}
        </li>
        <li>
          <span className="grafica__muestra grafica__muestra--proyeccion" aria-hidden="true" />
          Proyección (estimada)
        </li>
      </ul>

      {/* Estado vacío útil: la gráfica queda dibujada en su línea base y el
          mensaje explica qué falta, en vez de dejar un rectángulo mudo. */}
      {!hayDatos && (
        <p className="grafica__vacio">
          Todavía no hay ventas completadas en este rango. En cuanto registres la primera, la curva aparece aquí.
        </p>
      )}
    </div>
  );
}

export { remuestrear, techo };
