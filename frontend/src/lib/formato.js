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

export function formatearFecha(iso) {
  if (!iso) return "—";
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return fecha.toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });
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
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return fecha.toLocaleString("es-CO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
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
  const fecha = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(fecha.getTime())) return "—";
  return fecha.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", timeZone: "America/Bogota" });
}

/** Minutos enteros desde un instante del backend (UTC sin zona). */
export function minutosDesde(iso, ahora = Date.now()) {
  if (!iso) return 0;
  const fecha = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  return Math.max(0, Math.floor((ahora - fecha.getTime()) / 60000));
}
