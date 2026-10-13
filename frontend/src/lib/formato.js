const monedaCO = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const numeroCO = new Intl.NumberFormat("es-CO");

export function formatearMoneda(valor) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  return monedaCO.format(numero);
}

export function formatearNumero(valor) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  return numeroCO.format(numero);
}

/** Zona del negocio: los días y las horas que ve el restaurante (Colombia). */
const ZONA = "America/Bogota";

/**
 * El backend manda instantes en UTC SIN zona ("2026-10-12T23:41:36"): leídos
 * tal cual, el navegador los toma como hora local y en Colombia salen 5 h
 * corridos (un cierre de las 9:15 p. m. aparecía a las 2:15 a. m.). Una fecha
 * sola ("2026-10-12") es un día del calendario, no un instante.
 */
function aInstante(iso) {
  const texto = String(iso);
  if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) return new Date(`${texto}T12:00:00Z`);
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(texto) ? texto : `${texto}Z`);
}

export function formatearFecha(iso) {
  if (!iso) return "—";
  const fecha = aInstante(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return fecha.toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric", timeZone: ZONA });
}

export function formatearVariacion(actual, anterior) {
  const a = Number(actual);
  const b = Number(anterior);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return null;
  const variacion = ((a - b) / b) * 100;
  return {
    valor: variacion,
    texto: `${variacion >= 0 ? "+" : ""}${variacion.toFixed(1)}%`,
    positiva: variacion >= 0,
  };
}

export function formatearFechaHora(iso) {
  if (!iso) return "—";
  const fecha = aInstante(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return fecha.toLocaleString("es-CO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: ZONA,
  });
}

/** Número compacto para ejes y tarjetas: 1.2 mil, 3,4 M. */
export function formatearCompacto(valor) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  return new Intl.NumberFormat("es-CO", { notation: "compact", maximumFractionDigits: 1 }).format(numero);
}

/** Fecha y hora local actual en el formato de <input type="datetime-local">. */
export function fechaLocalAhora() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** "07:45 a. m." en hora de Colombia (comandas, tablero, cocina). */
export function formatearHora(iso) {
  if (!iso) return "—";
  const fecha = aInstante(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return fecha.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", timeZone: ZONA });
}

/** Minutos enteros desde un instante del backend (UTC sin zona). */
export function minutosDesde(iso, ahora = Date.now()) {
  if (!iso) return 0;
  const fecha = aInstante(iso);
  return Math.max(0, Math.floor((ahora - fecha.getTime()) / 60000));
}
