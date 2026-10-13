import { agruparPartes } from "@/components/charts/partes";
import { formatearMoneda } from "@/lib/formato";

import "./charts.css";

/**
 * DONA DE PARTICIPACIÓN (fase 8, 2026-10-12): por categoría, por medio de
 * pago, por tipo de orden. Monocroma como todo el producto: seis tonos de la
 * escala de grises por ROL (nunca un color), con leyenda, valor y porcentaje
 * siempre visibles. Nunca más de 6 partes: lo demás se suma en "Otros".
 *
 * Movimiento: el SVG entra UNA vez girando y creciendo un poco (transform y
 * opacidad). Los `d` de los arcos se calculan aquí y no se animan (regla c:
 * nada de atributos SVG por CSS).
 */
const R = 46;
const r = 30;
const punto = (radio, angulo) => [50 + radio * Math.sin(angulo), 50 - radio * Math.cos(angulo)];

function arco(desde, hasta) {
  // Un arco de 360° no se puede dibujar de una vez: se parte en dos.
  if (hasta - desde >= Math.PI * 2 - 1e-6) return `${arco(0, Math.PI)} ${arco(Math.PI, Math.PI * 2)}`;
  const grande = hasta - desde > Math.PI ? 1 : 0;
  const [x1, y1] = punto(R, desde);
  const [x2, y2] = punto(R, hasta);
  const [x3, y3] = punto(r, hasta);
  const [x4, y4] = punto(r, desde);
  return `M${x1.toFixed(3)} ${y1.toFixed(3)} A${R} ${R} 0 ${grande} 1 ${x2.toFixed(3)} ${y2.toFixed(3)} L${x3.toFixed(3)} ${y3.toFixed(3)} A${r} ${r} 0 ${grande} 0 ${x4.toFixed(3)} ${y4.toFixed(3)} Z`;
}

export default function Dona({ titulo, partes, formato = formatearMoneda, vacio = "Sin datos en el periodo." }) {
  const lista = agruparPartes(partes);
  const total = lista.reduce((s, p) => s + Number(p.valor), 0);
  // Ángulo acumulado de cada parte, sin variables que muten durante el render.
  const fracciones = lista.map((p) => Number(p.valor) / total);
  const arcos = lista.map((p, i) => {
    const desde = fracciones.slice(0, i).reduce((s, f) => s + f, 0) * Math.PI * 2;
    const hasta = desde + fracciones[i] * Math.PI * 2;
    return { ...p, i, d: arco(desde, hasta), pct: Math.round(fracciones[i] * 1000) / 10 };
  });
  return (
    <figure className="dona" aria-label={titulo}>
      <figcaption className="dona__titulo">{titulo}</figcaption>
      {total <= 0 ? (
        <p className="dona__vacio">{vacio}</p>
      ) : (
        <div className="dona__cuerpo">
          <svg className="dona__svg" viewBox="0 0 100 100" role="img" aria-label={`${titulo}: ${arcos.map((a) => `${a.nombre} ${a.pct} %`).join(", ")}`}>
            {arcos.map((a) => (
              <path key={a.nombre} d={a.d} className={`dona__parte dona__parte--${a.i} ${arcos.length === 1 ? "dona__parte--unica" : ""}`} />
            ))}
          </svg>
          <ul className="dona__leyenda">
            {arcos.map((a) => (
              <li key={a.nombre}>
                <span className={`dona__muestra dona__parte--${a.i}`} aria-hidden="true" />
                <span className="dona__nombre">{a.nombre}</span>
                <span className="dona__pct cifra">{a.pct.toLocaleString("es-CO")} %</span>
                <span className="dona__valor cifra">{formato(a.valor)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </figure>
  );
}
