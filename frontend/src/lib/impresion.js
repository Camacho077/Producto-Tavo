/**
 * IMPRESIÓN DE COMANDAS Y FACTURAS (fase 4, 2026-10-12).
 *
 * Interfaz única: `imprimir(documento, impresora)`. El documento es HTML ya
 * armado para papel térmico (58 u 80 mm) y la impresora es la de Ajustes
 * (`{conexion, ancho_mm, direccion}`). Hoy existe un solo conector, el del
 * NAVEGADOR: un iframe invisible con CSS de impresión y el diálogo del
 * sistema (la impresora térmica se elige ahí, o se deja predeterminada).
 * Pasar a ESC/POS directo es escribir otro conector (`ip`) que reciba el
 * mismo documento: las pantallas no cambian.
 *
 * Sin colores: el papel térmico imprime en un solo tono, la jerarquía va con
 * tamaño, peso y mayúsculas.
 */
const escapar = (texto) =>
  String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function estilos(anchoMm) {
  const util = anchoMm - 6;
  return `
    @page { size: ${anchoMm}mm auto; margin: 3mm; }
    * { box-sizing: border-box; }
    body { margin: 0; width: ${util}mm; font-family: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace; font-size: 12px; line-height: 1.3; }
    h1 { font-size: 30px; margin: 0; line-height: 1; }
    .fila { display: flex; justify-content: space-between; gap: 4px; }
    .linea { border-top: 1px dashed; margin: 6px 0; }
    .plato { font-size: 17px; font-weight: 700; margin-top: 6px; text-transform: uppercase; }
    .mod { font-size: 15px; font-weight: 700; padding-left: 10px; }
    .nota { font-size: 14px; font-style: italic; padding-left: 10px; }
    .grande { font-size: 15px; font-weight: 700; }
    .pie { font-size: 10px; margin-top: 8px; text-align: center; }
    .derecha { text-align: right; }
  `;
}

/** HTML de una comanda: solo lo que va a cocina, en grande. */
export function htmlComanda(orden, comandaNumero, { tipo, destino, empresa }) {
  const comanda = orden.comandas.find((c) => c.numero === comandaNumero) ?? orden.comandas[0];
  const items = orden.items.filter((i) => i.comanda_id === comanda.id && i.va_a_cocina && !i.anulado);
  const hora = new Date(`${comanda.created_at}Z`).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", timeZone: "America/Bogota" });
  const platos = items
    .map(
      (i) => `
      <div class="plato">${i.cantidad}× ${escapar(i.nombre)}</div>
      ${i.modificadores.map((m) => `<div class="mod">${m.tipo === "sin" ? "– " : "+ "}${escapar(m.nombre.toUpperCase())}</div>`).join("")}
      ${i.nota ? `<div class="nota">» ${escapar(i.nota)}</div>` : ""}`
    )
    .join("");
  return {
    titulo: `Comanda #${orden.numero}`,
    cuerpo: `
      <div class="fila"><h1>#${orden.numero}</h1><div class="derecha grande">${escapar(tipo)}${comanda.numero > 1 ? `<br>Agregado ${comanda.numero}` : ""}</div></div>
      <div class="grande">${escapar(destino)}</div>
      <div class="fila"><span>${hora}</span><span>${escapar(orden.mesero_nombre ?? "")}</span></div>
      <div class="linea"></div>
      ${platos}
      ${orden.nota && comanda.numero === 1 ? `<div class="linea"></div><div class="nota">Nota: ${escapar(orden.nota)}</div>` : ""}
      <div class="pie">${escapar(empresa ?? "")}</div>`,
  };
}

const pesos = (v) => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(v));
const MEDIOS = { efectivo: "Efectivo", transferencia: "Transferencia", nequi: "Nequi", daviplata: "Daviplata", tarjeta: "Tarjeta" };

/** Leyenda obligatoria (fase 6): espejo de LEYENDA_COMPROBANTE del backend. */
export const LEYENDA_COMPROBANTE = "Comprobante interno, no válido como factura electrónica.";

/** HTML del comprobante interno de un cobro, para papel térmico. */
export function htmlComprobante(venta, negocio) {
  const fecha = new Date(`${venta.fecha}Z`).toLocaleString("es-CO", { timeZone: "America/Bogota", dateStyle: "short", timeStyle: "short" });
  const filas = venta.items
    .map((i) => `<div class="fila"><span>${i.cantidad}× ${escapar(i.nombre)}</span><span>${pesos(i.subtotal)}</span></div>`)
    .join("");
  const pagos = venta.pagos
    .map((p) => `<div class="fila"><span>${MEDIOS[p.medio] ?? p.medio}</span><span>${pesos(p.monto)}</span></div>${p.cambio ? `<div class="fila"><span>Recibido / devueltas</span><span>${pesos(p.recibido)} / ${pesos(p.cambio)}</span></div>` : ""}`)
    .join("");
  return {
    titulo: `Comprobante ${venta.codigo}`,
    cuerpo: `
      <div class="grande">${escapar(negocio?.nombre_empresa ?? "")}</div>
      ${negocio?.nit ? `<div>NIT ${escapar(negocio.nit)}</div>` : ""}
      ${negocio?.direccion ? `<div>${escapar(negocio.direccion)}</div>` : ""}
      <div class="linea"></div>
      <div class="fila"><span class="grande">${venta.codigo}</span><span>${fecha}</span></div>
      <div>Orden #${venta.orden_numero}${venta.mesa_nombre ? ` · Mesa ${escapar(venta.mesa_nombre)}` : ""}</div>
      ${venta.cliente_nombre ? `<div>Cliente: ${escapar(venta.cliente_nombre)}${venta.cliente_documento ? ` · ${venta.cliente_documento_tipo} ${escapar(venta.cliente_documento)}` : ""}</div>` : ""}
      <div class="linea"></div>
      ${filas}
      <div class="linea"></div>
      <div class="fila"><span>Base</span><span>${pesos(venta.subtotal)}</span></div>
      ${Number(venta.impuesto) ? `<div class="fila"><span>Impoconsumo ${Number(venta.impuesto_tasa)} %</span><span>${pesos(venta.impuesto)}</span></div>` : ""}
      <div class="fila grande"><span>Total</span><span>${pesos(venta.total)}</span></div>
      ${Number(venta.propina) ? `<div class="fila"><span>Propina voluntaria</span><span>${pesos(venta.propina)}</span></div><div class="fila grande"><span>A pagar</span><span>${pesos(venta.total_pagado)}</span></div>` : ""}
      <div class="linea"></div>
      ${pagos}
      <div class="linea"></div>
      <div class="pie">${LEYENDA_COMPROBANTE}<br>Atendió: ${escapar(venta.cajero_nombre ?? "")}</div>`,
  };
}

const CONECTORES = {
  navegador: (documento, impresora) =>
    new Promise((resolver) => {
      const marco = document.createElement("iframe");
      marco.setAttribute("aria-hidden", "true");
      marco.style.cssText = "position:fixed;width:0;height:0;border:0;opacity:0;pointer-events:none";
      document.body.appendChild(marco);
      const doc = marco.contentDocument;
      doc.open();
      doc.write(
        `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${escapar(documento.titulo)}</title>` +
          `<style>${estilos(impresora?.ancho_mm ?? 80)}</style></head><body>${documento.cuerpo}</body></html>`
      );
      doc.close();
      const quitar = () => {
        marco.remove();
        resolver();
      };
      marco.contentWindow.addEventListener("afterprint", quitar, { once: true });
      // Algunos navegadores no disparan afterprint: se limpia igual.
      setTimeout(quitar, 60_000);
      marco.contentWindow.focus();
      marco.contentWindow.print();
    }),
  ip: () => Promise.reject(new Error("La impresión directa por IP (ESC/POS) todavía no está disponible: en Ajustes, cambia la impresora a «Desde el navegador».")),
};

/** La impresora activa de Ajustes para un uso ("comanda" o "factura"), o null. */
export function impresoraPara(configuracion, uso) {
  return (configuracion?.impresoras ?? []).find((i) => i.activa && (i.uso === uso || i.uso === "ambos")) ?? null;
}

export function imprimir(documento, impresora) {
  const conector = CONECTORES[impresora?.conexion ?? "navegador"];
  return conector(documento, impresora);
}

/** Imprime el comprobante de un cobro en la impresora de facturas (o la del navegador). */
export function imprimirComprobante(venta, tenant) {
  const impresora = impresoraPara(tenant?.configuracion, "factura") ?? { conexion: "navegador", ancho_mm: 80 };
  return imprimir(htmlComprobante(venta, tenant), impresora);
}
