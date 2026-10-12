/**
 * Vocabulario de la operación del restaurante (2026-10-12). Las CLAVES son
 * las del backend (app/modules/ajustes/schemas.py: TipoOrden, OrigenOrden,
 * MedioPago); aquí solo se les pone nombre para la pantalla.
 */
export const TIPOS_ORDEN = [
  { valor: "local", etiqueta: "En el local", corta: "Local", ayuda: "Con mesa" },
  { valor: "llevar", etiqueta: "Para llevar", corta: "Llevar", ayuda: "El cliente la recoge" },
  { valor: "domicilio", etiqueta: "Domicilio", corta: "Domicilio", ayuda: "Con dirección y teléfono" },
];

export const ORIGENES = [
  { valor: "local", etiqueta: "En el local" },
  { valor: "llamada", etiqueta: "Llamada" },
  { valor: "whatsapp", etiqueta: "WhatsApp" },
];

export const MEDIOS_PAGO = [
  { valor: "efectivo", etiqueta: "Efectivo" },
  { valor: "transferencia", etiqueta: "Transferencia" },
  { valor: "nequi", etiqueta: "Nequi" },
  { valor: "daviplata", etiqueta: "Daviplata" },
  { valor: "tarjeta", etiqueta: "Tarjeta" },
];

export const USOS_IMPRESORA = [
  { valor: "comanda", etiqueta: "Comandas de cocina" },
  { valor: "factura", etiqueta: "Facturas de caja" },
  { valor: "ambos", etiqueta: "Comandas y facturas" },
];

export const CONEXIONES_IMPRESORA = [
  { valor: "navegador", etiqueta: "Desde el navegador" },
  { valor: "ip", etiqueta: "Por IP (ESC/POS)" },
];

const porValor = (lista) => Object.fromEntries(lista.map((x) => [x.valor, x]));
const TIPOS = porValor(TIPOS_ORDEN);
const ORIGEN = porValor(ORIGENES);
const MEDIO = porValor(MEDIOS_PAGO);
const USO = porValor(USOS_IMPRESORA);
const CONEXION = porValor(CONEXIONES_IMPRESORA);

export const etiquetaTipoOrden = (v) => TIPOS[v]?.etiqueta ?? v;
export const etiquetaCortaTipoOrden = (v) => TIPOS[v]?.corta ?? v;
export const etiquetaOrigen = (v) => ORIGEN[v]?.etiqueta ?? v;
export const etiquetaMedioPago = (v) => MEDIO[v]?.etiqueta ?? v;
export const etiquetaUsoImpresora = (v) => USO[v]?.etiqueta ?? v;
export const etiquetaConexionImpresora = (v) => CONEXION[v]?.etiqueta ?? v;
