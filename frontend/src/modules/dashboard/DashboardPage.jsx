import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, BarChart3, Package, Search, ShoppingCart, Users, Wallet } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import CifraAnimada from "@/components/dashboard/CifraAnimada";
import Objeto3d, { MiniaturaProducto, formaPorIndice } from "@/components/dashboard/Objeto3d";
import PanelAvisos from "@/modules/dashboard/PanelAvisos";
import TarjetaLuz from "@/components/dashboard/TarjetaLuz";
import Variacion from "@/components/dashboard/Variacion";
import { Pildoras, Skeleton } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useApiResource } from "@/hooks/useApiResource";
import { useContadoresAnimados } from "@/hooks/useContadoresAnimados";
import { formatearCompacto, formatearMoneda, formatearNumero } from "@/lib/formato";

import "./dashboard.css";

// La gráfica va en su propio paquete: se descarga cuando hay dashboard que
// pintar, no al abrir la aplicación (la pantalla de acceso no la necesita).
const GraficaRendimiento = lazy(() => import("@/components/charts/GraficaRendimiento"));

/**
 * DASHBOARD — la maqueta aprobada (docs/dashboard-referencia.html) con los
 * datos reales del tenant.
 *
 * Dos controles independientes, y por eso dos peticiones independientes:
 *   - Hoy / Mes / Año  →  /dashboard/panel?periodo=   (las cifras)
 *   - 1D…1A            →  /dashboard/serie?rango=     (la gráfica)
 * Mover la gráfica no vuelve a pedir las cifras, ni al revés. El panel de
 * avisos tiene la suya, así que las tres salen en paralelo.
 *
 * Rendimiento (reglas de la sección 2 del encargo):
 *   - Las cifras se animan escribiendo el texto de su nodo, no con estado de
 *     React (useContadoresAnimados): un contador con useState re-renderizaría
 *     el dashboard entero 60 veces por segundo.
 *   - Las barras de la lista de más vendidos usan scaleX con origen a la
 *     izquierda, nunca width.
 *   - El indicador de las píldoras se desliza con translateX, nunca con left.
 *   - La luz que sigue al cursor en las tarjetas se limita a un cálculo por
 *     cuadro con requestAnimationFrame (TarjetaLuz).
 *   - Ningún backdrop-filter: las superficies son degradados semiopacos.
 */

const PERIODOS = [
  { clave: "hoy", etiqueta: "Hoy", titulo: "Hoy frente a ayer" },
  { clave: "mes", etiqueta: "Mes", titulo: "Lo que va del mes frente al mismo tramo del mes anterior" },
  { clave: "anio", etiqueta: "Año", titulo: "Lo que va del año frente al mismo tramo del año anterior" },
];

const RANGOS = [
  { clave: "1d", etiqueta: "1D", titulo: "Últimas 24 horas, por hora" },
  { clave: "1s", etiqueta: "1S", titulo: "Últimos 7 días" },
  { clave: "1m", etiqueta: "1M", titulo: "Últimos 30 días" },
  { clave: "6m", etiqueta: "6M", titulo: "Últimos 6 meses" },
  { clave: "1a", etiqueta: "1A", titulo: "Últimos 12 meses" },
];

const TEXTO_PERIODO = {
  hoy: { actual: "Hoy", anterior: "Ayer", en: "hoy" },
  mes: { actual: "Este mes", anterior: "Mismo tramo del mes anterior", en: "en este mes" },
  anio: { actual: "Este año", anterior: "Mismo tramo del año anterior", en: "en este año" },
};

const TEXTO_RANGO = {
  "1d": { actual: "Últimas 24 h", anterior: "24 h anteriores" },
  "1s": { actual: "Últimos 7 días", anterior: "7 días anteriores" },
  "1m": { actual: "Últimos 30 días", anterior: "30 días anteriores" },
  "6m": { actual: "Últimos 6 meses", anterior: "6 meses anteriores" },
  "1a": { actual: "Últimos 12 meses", anterior: "12 meses anteriores" },
};

// Los conteos (clientes, unidades) se REDONDEAN mientras cuentan: el contador
// pasa por valores intermedios y "1,343 clientes" no existe.
const formatearEntero = (n) => formatearNumero(Math.round(n));

// Constante de módulo: de aquí salen las refs de los contadores, así que tiene
// que ser el MISMO objeto en cada render.
const FORMATOS = {
  ventas: formatearMoneda,
  compras: formatearMoneda,
  proyeccion: formatearMoneda,
  clientes: formatearEntero,
  productos: formatearEntero,
};

const fmtHora = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false });
const fmtDia = new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "short" });
const fmtMes = new Intl.DateTimeFormat("es-CO", { month: "short", year: "2-digit" });
const fmtMesLargo = new Intl.DateTimeFormat("es-CO", { month: "long", year: "numeric" });
const fmtFechaCorta = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "long" });

/** El backend manda instantes en ISO; la etiqueta legible se arma acá. */
function etiquetaDeInstante(iso, unidad) {
  const fecha = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(fecha.getTime())) return iso;
  if (unidad === "hora") return fmtHora.format(fecha);
  if (unidad === "month") return fmtMes.format(fecha);
  return fmtDia.format(fecha);
}

function saludoSegunHora() {
  const h = new Date().getHours();
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

/* ==========================================================================
   Marcadores de carga: la misma forma y el mismo alto que el contenido final,
   sin brillo. Van DENTRO de la misma tarjeta que luego tendrá los datos: la
   tarjeta entra una vez (con su escalón) y al llegar la respuesta el
   contenido se reemplaza en su sitio, sin volver a entrar desde opacidad 0.
   ========================================================================== */
/**
 * TARJETA KPI — la "capa doble" del rediseño monocromático (2026-10-01):
 * tarjeta blanca con 6 px de relleno; dentro, un bloque gris (`--relleno`,
 * radio 12) con el icono, la etiqueta y la cifra; debajo, FUERA del bloque,
 * la línea de tendencia.
 *
 * Es el MISMO nodo con esqueleto y con datos (entra una vez con `.reveal`).
 * El icono y la etiqueta no dependen de la respuesta, así que se pintan
 * desde el principio; la cifra y la tendencia tienen un marcador que mide
 * exactamente lo mismo (alto de línea de la cifra en `em` y alto mínimo de
 * la tendencia), así nada se desplaza cuando llegan los datos.
 */
function TarjetaKpi({ icono: Icono, etiqueta, retardo, cargando, valor, tendencia }) {
  return (
    <TarjetaLuz className="kpi reveal" estilo={{ "--d": retardo }}>
      <div className="kpi__bloque">
        <div className="kpi__cabeza">
          <span className="kpi__icono" aria-hidden="true">
            <Icono size={16} strokeWidth={1.75} />
          </span>
          <p className="kpi__etiqueta">{etiqueta}</p>
        </div>
        {cargando ? (
          <div className="kpi__valor" aria-hidden="true">
            <Skeleton ancho="68%" alto="1.2em" />
          </div>
        ) : (
          valor
        )}
      </div>
      <div className="kpi__tendencia">{cargando ? <Skeleton ancho="62%" alto="12px" /> : tendencia}</div>
    </TarjetaLuz>
  );
}

/** Variación frente al tramo anterior; sin base de comparación, el periodo. */
function Tendencia({ variacion, textos }) {
  if (variacion == null) {
    return <span className="kpi__contexto">Sin comparativa {textos.en}</span>;
  }
  return (
    <>
      <Variacion valor={variacion} />
      <span className="kpi__contexto">vs. {textos.anterior.toLowerCase()}</span>
    </>
  );
}

function EsqueletoProyeccion() {
  return (
    <>
      <Skeleton ancho="60%" alto="11px" style={{ margin: "3px 0" }} />
      <Skeleton ancho="55%" alto="27.4px" style={{ marginTop: 7 }} />
      <Skeleton ancho="95%" alto="11px" style={{ marginTop: 9 }} />
      <Skeleton ancho="70%" alto="11px" style={{ marginTop: 6 }} />
    </>
  );
}

function EsqueletoAcento() {
  return (
    <>
      <Skeleton ancho="22px" alto="22px" />
      <Skeleton ancho="60%" alto="22px" style={{ marginTop: 12 }} />
      <Skeleton ancho="95%" alto="12px" style={{ marginTop: 9 }} />
      <Skeleton ancho="80%" alto="12px" style={{ marginTop: 6 }} />
      <Skeleton ancho="110px" alto="37px" style={{ marginTop: 12, borderRadius: 12 }} />
    </>
  );
}

/** La gráfica completa: lienzo de 260 px + eje (6 + 15,75) + leyenda (14 +
 *  17,25). Con solo el lienzo, al llegar la serie el panel crecía 53 px. */
function EsqueletoGrafica() {
  return (
    <div aria-hidden="true">
      <Skeleton alto="260px" style={{ borderRadius: 8 }} />
      <Skeleton ancho="100%" alto="10.5px" style={{ margin: "8.6px 0 2.6px" }} />
      <Skeleton ancho="45%" alto="11.5px" style={{ margin: "16.9px 0 5.5px" }} />
    </div>
  );
}

function EsqueletoMasVendidos() {
  return (
    <div className="lista-productos">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="producto">
          <Skeleton ancho="48px" alto="48px" style={{ borderRadius: 12 }} />
          <div className="producto__cuerpo">
            {/* Solo márgenes superiores: entre bloques los verticales se
                colapsan y el alto no sumaría lo que parece. */}
            <Skeleton ancho={`${70 - i * 8}%`} alto="13px" style={{ marginTop: 3 }} />
            <Skeleton ancho="40%" alto="12.5px" style={{ marginTop: 8 }} />
            <Skeleton ancho="100%" alto="6px" style={{ marginTop: 10, borderRadius: 999 }} />
          </div>
          <div className="producto__fin">
            <Skeleton ancho="72px" alto="13px" />
            <Skeleton ancho="48px" alto="18px" style={{ marginTop: 6, marginLeft: "auto" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function EsqueletoInventario() {
  return [0, 1, 2, 3].map((i) => (
    <div key={i} className="tarjeta tarjeta--mini">
      <Skeleton ancho="100%" alto="64px" style={{ borderRadius: 12, marginBottom: 12 }} />
      <Skeleton ancho="50%" alto="11px" style={{ margin: "3px 0" }} />
      <Skeleton ancho="70%" alto="15px" style={{ marginTop: 5 }} />
      <Skeleton ancho="60%" alto="24.75px" style={{ marginTop: 9 }} />
    </div>
  ));
}

/**
 * Marca el contenedor como "vivo" después de su primer pintado. Lo usa el
 * CSS (@starting-style en dashboard.css) para animar SOLO lo que entra
 * después —un producto nuevo en el ranking al cambiar de periodo—, nunca lo
 * que reemplaza al esqueleto en la primera carga.
 */
function useVivoTrasMontar() {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.setAttribute("data-vivo", "");
  }, []);
  return ref;
}

/* ==========================================================================
   Piezas de la rejilla
   ========================================================================== */
function ListaMasVendidos({ productos, maximo }) {
  const refLista = useVivoTrasMontar();

  if (!productos.length) {
    return (
      <p className="dash-vacio">
        Todavía no hay ventas completadas en este periodo. Cuando registres la primera, el ranking aparece aquí con su
        participación.
      </p>
    );
  }

  return (
    <div className="lista-productos" ref={refLista}>
      {productos.map((producto, i) => (
        <Link key={producto.producto_id} to={`/compras/productos/${producto.producto_id}`} className="producto">
          <MiniaturaProducto indice={i} retardo={i * 1.2} />
          <div className="producto__cuerpo">
            <p className="producto__nombre" title={producto.nombre}>
              {producto.nombre}
            </p>
            <p className="producto__categoria">{producto.categoria ?? "Sin categoría"}</p>
            {/* La barra escala con scaleX desde la izquierda: animar `width`
                obliga a recalcular el layout de la fila en cada cuadro. La
                proporción es estado (transición), así al cambiar de periodo
                la barra se transforma al valor nuevo. Desfase de 60 ms. */}
            <span className="barra" aria-hidden="true">
              <span
                className="barra__relleno"
                style={{ "--proporcion": maximo ? producto.unidades / maximo : 0, "--d": `${0.3 + i * 0.06}s` }}
              />
            </span>
          </div>
          <div className="producto__fin">
            <CifraAnimada como="p" className="producto__monto cifra" valor={producto.monto} formato={formatearMoneda} />
            <Variacion valor={producto.variacion} />
          </div>
        </Link>
      ))}
    </div>
  );
}

function RejillaInventario({ inventario }) {
  const categorias = inventario?.categorias ?? [];

  // Aquí las fichas son hijas directas de `.dash-inventario`: el atributo "vivo" se
  // pone en esa columna (la encuentra desde la primera ficha).
  const refPrimera = useRef(null);
  useEffect(() => {
    refPrimera.current?.parentElement?.setAttribute("data-vivo", "");
  }, []);

  if (!categorias.length) {
    return (
      <div className="tarjeta tarjeta--mini dash-inventario__vacio" ref={refPrimera}>
        <p className="dash-vacio">
          Aún no hay categorías con existencias. Crea una categoría y registra una compra para ver el inventario
          repartido aquí.
        </p>
        <Link to="/compras/categorias/nuevo" className="enlace">
          Crear categoría
        </Link>
      </div>
    );
  }

  return (
    <>
      <span hidden ref={refPrimera} />
      {categorias.map((categoria, i) => (
        <TarjetaLuz key={categoria.categoria_id} className="tarjeta--mini">
          <Objeto3d forma={formaPorIndice(i)} retardo={i * 0.9} />
          <p className="mini__categoria">{categoria.nombre}</p>
          <CifraAnimada como="p" className="mini__valor cifra" valor={categoria.valor} formato={formatearMoneda} />
          <div className="mini__pie">
            <Variacion valor={categoria.variacion} />
            <span>{formatearNumero(categoria.unidades)} uds</span>
          </div>
        </TarjetaLuz>
      ))}
    </>
  );
}

/* ==========================================================================
   Pantalla
   ========================================================================== */
export default function DashboardPage() {
  const { usuario, tenant } = useAuth();
  const navigate = useNavigate();
  const [periodo, setPeriodo] = useState("mes");
  const [rango, setRango] = useState("1m");
  const [textoBusqueda, setTextoBusqueda] = useState("");

  const panel = useApiResource(`/dashboard/panel?periodo=${periodo}`);
  const serie = useApiResource(`/dashboard/serie?rango=${rango}`);

  const t = panel.data?.totales;
  const proyeccion = panel.data?.proyeccion;

  // Un solo objeto memorizado: es la dependencia de la animación de contadores.
  const cifras = useMemo(
    () => ({
      ventas: t?.ventas ?? 0,
      compras: t?.compras ?? 0,
      proyeccion: proyeccion?.ventas ?? 0,
      clientes: t?.numero_clientes ?? 0,
      productos: t?.productos_vendidos ?? 0,
    }),
    [t, proyeccion]
  );
  // Se desestructuran a identificadores propios: `ref={refVentas}` hace
  // que el linter lo confunda con leer un ref durante el render, cuando lo que
  // se pasa es una función de ref.
  const {
    ventas: refVentas,
    compras: refCompras,
    proyeccion: refProyeccion,
    clientes: refClientes,
    productos: refProductos,
  } = useContadoresAnimados(FORMATOS, panel.data ? cifras : null);

  const hayPanel = Boolean(panel.data);
  const masVendidos = panel.data?.mas_vendidos ?? [];
  const maximoUnidades = Math.max(1, ...masVendidos.map((p) => p.unidades));

  const unidadSerie = serie.data?.unidad;
  const etiquetaEje = useMemo(
    () => (iso) => etiquetaDeInstante(iso, unidadSerie),
    [unidadSerie]
  );

  const nombre = usuario?.nombre_completo?.split(" ")[0] ?? "equipo";
  const mesProyectado = proyeccion ? fmtMesLargo.format(new Date(`${proyeccion.mes}T00:00:00`)) : "";
  const textos = TEXTO_PERIODO[periodo];
  const textosRango = TEXTO_RANGO[rango];

  const buscar = (evento) => {
    evento.preventDefault();
    const q = textoBusqueda.trim();
    if (q) navigate(`/compras/productos?q=${encodeURIComponent(q)}`);
  };

  return (
    <>
      {/* ---------------- Encabezado: saludo, periodo y búsqueda ----------------
          El timbre y el bloque de usuario viven ahora en el sidebar y en la
          barra superior (rediseño monocromático, 2026-10-01). */}
      <header className="dash-head reveal" style={{ "--d": "0s" }}>
        <div className="dash-head__texto">
          <h1 className="saludo">
            {saludoSegunHora()}, <span className="saludo__nombre">{nombre}</span>
          </h1>
          <p className="saludo__sub">
            Así va {tenant?.nombre_empresa ?? "el negocio"} hoy, {fmtFechaCorta.format(new Date())}.
          </p>
        </div>

        <div className="dash-head__controles" role="group" aria-label="Periodo y búsqueda">
          <Pildoras opciones={PERIODOS} valor={periodo} onCambiar={setPeriodo} etiqueta="Periodo" />
          <form className="buscador-pastilla" role="search" onSubmit={buscar}>
            <Search size={15} aria-hidden="true" />
            <input
              type="search"
              value={textoBusqueda}
              onChange={(e) => setTextoBusqueda(e.target.value)}
              placeholder="Buscar productos…"
              aria-label="Buscar productos"
            />
          </form>
        </div>
      </header>

      {/* ---------------- Cifras, más vendidos e inventario ---------------- */}
      {panel.error && <p className="estado estado--error">{panel.error}</p>}

      {/* Las MISMAS tarjetas sirven de esqueleto y de contenido: entran una
          vez, en cascada (45 ms entre KPI, luego el resto en orden de
          lectura), y la respuesta reemplaza el esqueleto en su sitio. Nada
          vuelve a entrar desde opacidad 0. */}
      {!panel.error && (
        <section
          className="dash-resumen"
          aria-label={hayPanel ? "Resumen del periodo" : "Cargando cifras"}
          aria-busy={!hayPanel}
        >
          <div className="dash-grid">
            <TarjetaKpi
              icono={Wallet}
              etiqueta="Total vendido"
              retardo=".04s"
              cargando={!hayPanel}
              valor={
                <p className="kpi__valor" ref={refVentas}>
                  {FORMATOS.ventas(0)}
                </p>
              }
              tendencia={hayPanel && <Tendencia variacion={t.ventas_variacion} textos={textos} />}
            />
            <TarjetaKpi
              icono={ShoppingCart}
              etiqueta="Compras"
              retardo=".085s"
              cargando={!hayPanel}
              valor={
                <p className="kpi__valor" ref={refCompras}>
                  {FORMATOS.compras(0)}
                </p>
              }
              tendencia={hayPanel && <Tendencia variacion={t.compras_variacion} textos={textos} />}
            />
            <TarjetaKpi
              icono={Users}
              etiqueta="Clientes"
              retardo=".13s"
              cargando={!hayPanel}
              valor={
                <p className="kpi__valor" ref={refClientes}>
                  {FORMATOS.clientes(0)}
                </p>
              }
              tendencia={<span className="kpi__contexto">Con compras {textos.en}</span>}
            />
            <TarjetaKpi
              icono={Package}
              etiqueta="Productos vendidos"
              retardo=".175s"
              cargando={!hayPanel}
              valor={
                <p className="kpi__valor" ref={refProductos}>
                  {FORMATOS.productos(0)}
                </p>
              }
              tendencia={<span className="kpi__contexto">Unidades {textos.en}</span>}
            />

            <TarjetaLuz className="reveal dash-vendidos tarjeta--quieta" estilo={{ "--d": ".22s" }}>
              <div className="fila-entre">
                <h2 className="tarjeta__titulo">Productos más vendidos</h2>
                <Link to="/compras/productos" className="enlace enlace--pequeno">
                  Ver todo
                </Link>
              </div>
              {hayPanel ? <ListaMasVendidos productos={masVendidos} maximo={maximoUnidades} /> : <EsqueletoMasVendidos />}
            </TarjetaLuz>

            <div className="dash-inventario reveal" style={{ "--d": ".265s" }}>
              {hayPanel ? <RejillaInventario inventario={panel.data.inventario} /> : <EsqueletoInventario />}
            </div>

            <div className="dash-lateral">
              <div className="tarjeta-punteada reveal" style={{ "--d": ".31s" }}>
                {hayPanel ? (
                  <>
                    <p className="etiqueta etiqueta--acento">Proyección · {mesProyectado}</p>
                    <p className="cifra-media cifra" ref={refProyeccion}>
                      {FORMATOS.proyeccion(0)}
                    </p>
                    <p className="ayuda" style={{ marginTop: 4 }}>
                      Estimado por regresión lineal sobre los últimos {proyeccion.base_meses} meses · no es un dato real
                    </p>
                  </>
                ) : (
                  <EsqueletoProyeccion />
                )}
              </div>

              <div className="tarjeta-acento reveal" style={{ "--d": ".355s" }}>
                {hayPanel ? (
                  <>
                    <BarChart3 size={22} aria-hidden="true" />
                    <p className="tarjeta-acento__titulo">Decisiones con datos</p>
                    <p className="tarjeta-acento__texto">
                      {t.numero_ventas > 0
                        ? `${formatearNumero(t.numero_ventas)} ventas en el periodo, con un saldo de ${formatearCompacto(t.saldo)} frente a compras.`
                        : "Registra tu primera venta y aquí verás el saldo del periodo frente a las compras."}
                    </p>
                    <Link to="/ventas" className="boton-claro">
                      Ver ventas
                      <ArrowRight size={13} aria-hidden="true" />
                    </Link>
                  </>
                ) : (
                  <EsqueletoAcento />
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ---------------- Rendimiento ---------------- */}
      <TarjetaLuz className="reveal rendimiento tarjeta--quieta" estilo={{ "--d": ".4s" }} etiqueta="Rendimiento">
        <div className="rendimiento__cabecera">
          <div>
            <h2 className="tarjeta__titulo">Rendimiento</h2>
            <p className="ayuda">
              {textosRango.actual} frente a {textosRango.anterior.toLowerCase()}, con la proyección punteada del
              periodo siguiente
            </p>
          </div>
          <Pildoras
            compactas
            opciones={RANGOS}
            valor={rango}
            onCambiar={setRango}
            etiqueta="Rango de la gráfica"
          />
        </div>

        {serie.error && <p className="estado estado--error">{serie.error}</p>}
        {/* Mientras llega la primera serie se deja un marcador del mismo tamaño
            que la gráfica: nada se mueve cuando aparece. En los cambios de
            rango los datos actuales se quedan hasta que llegan los nuevos. */}
        {!serie.data && !serie.error && <EsqueletoGrafica />}
        {serie.data && (
          <Suspense fallback={<EsqueletoGrafica />}>
            <GraficaRendimiento
              serie={serie.data}
              etiquetaDe={etiquetaEje}
              etiquetaActual={textosRango.actual}
              etiquetaAnterior={textosRango.anterior}
              etiquetaProyeccion="Proy."
            />
          </Suspense>
        )}
      </TarjetaLuz>

      {/* ---------------- Avisos ---------------- */}
      <section id="avisos" className="dash-avisos reveal" style={{ "--d": ".445s" }} aria-label="Avisos">
        <h2 className="tarjeta__titulo">Avisos</h2>
        <PanelAvisos />
      </section>
    </>
  );
}
