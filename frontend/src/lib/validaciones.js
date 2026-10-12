import { z } from "zod";

/**
 * Reglas de validación del frontend. Son un ESPEJO de
 * backend/app/core/validaciones.py: mismos patrones, mismos topes y los
 * mismos mensajes en español. La validación del backend es la que manda;
 * esta capa existe para avisar antes de enviar.
 */

// ---------- Mensajes (idénticos al backend) ----------
export const MSG = {
  obligatorio: "Este campo es obligatorio",
  nombrePersona: "Solo letras, espacios, tildes y apóstrofes (entre 2 y 80 caracteres)",
  nombreItem: "Solo letras, espacios, tildes y apóstrofes; sin espacios al inicio o al final",
  sku: "Solo letras, números, guion y guion bajo (entre 2 y 50 caracteres)",
  nombreCarta: "Solo letras, números, espacios y los signos . , - + & / ( ) %; sin espacios al inicio o al final",
  mesa: "Solo letras, números, espacios y guion (entre 1 y 20 caracteres)",
  hora: "Debe ser una hora en formato 24 h, p. ej. 06:30",
  precio: "Debe ser un monto positivo con máximo 2 decimales (hasta $ 999.999.999,99)",
  porcentaje: "Debe ser un porcentaje entre 0 y 100",
  telefono: "Debe ser un celular de 10 dígitos que empiece por 3 o un fijo con indicativo (60 + 8 dígitos)",
  email: "Debe ser un correo electrónico válido",
  nitFormato: "El NIT debe tener el formato 900123456-7 (número y dígito de verificación)",
  fechaFutura: "La fecha no puede ser futura",
  entregaPasada: "La fecha de entrega no puede ser anterior a hoy",
  entero: (min, max) => `Debe ser un número entero entre ${min} y ${max}`,
  maximo: (n) => `Máximo ${n} caracteres`,
};

export const STOCK_MAX = 1_000_000;
export const CANTIDAD_MAX = 100_000;
export const PRECIO_MAX = 999_999_999.99;

// ---------- Patrones ----------
const NOMBRE_PERSONA_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]+$/;
const NOMBRE_ITEM_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]+$/;
const SKU_RE = /^[A-Za-z0-9_-]+$/;
// Nombres de la carta y del restaurante (2026-10-12): platos, insumos,
// combos, zonas y el nombre del negocio llevan dígitos y algunos signos
// ("Gaseosa 400 ml", "Pollo 1/4"). Espejo de NOMBRE_CARTA_RE del backend.
const NOMBRE_CARTA_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9' .,\-+&/()%]+$/;
const MESA_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 -]+$/;
const HORA_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;
const TELEFONO_RE = /^(3\d{9}|60\d{8})$/;
// Correo "de verdad": parte local sin espacios ni puntos dobles, dominio con TLD de 2+ letras.
const EMAIL_RE = /^(?!\.)(?!.*\.\.)[A-Za-z0-9._%+-]+(?<!\.)@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;
const NIT_RE = /^(\d{6,10})-(\d)$/;

// ---------- Documentos (Colombia) ----------
export const TIPOS_DOCUMENTO = [
  { valor: "CC", etiqueta: "Cédula de ciudadanía" },
  { valor: "CE", etiqueta: "Cédula de extranjería" },
  { valor: "PA", etiqueta: "Pasaporte" },
  { valor: "TI", etiqueta: "Tarjeta de identidad" },
];
const REGLAS_DOCUMENTO = {
  CC: [/^\d{6,10}$/, "La cédula de ciudadanía tiene entre 6 y 10 dígitos"],
  CE: [/^\d{6,7}$/, "La cédula de extranjería tiene entre 6 y 7 dígitos"],
  PA: [/^[A-Z0-9]{6,12}$/, "El pasaporte tiene entre 6 y 12 letras o números"],
  TI: [/^\d{10,11}$/, "La tarjeta de identidad tiene 10 u 11 dígitos"],
};

const PESOS_NIT = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71];

/** Dígito de verificación del NIT (algoritmo DIAN, módulo 11). */
export function digitoVerificacionNit(base) {
  const digitos = String(base).split("").reverse();
  const suma = digitos.reduce((acc, d, i) => acc + Number(d) * (PESOS_NIT[i] ?? 0), 0);
  const resto = suma % 11;
  return resto < 2 ? resto : 11 - resto;
}

/** Devuelve el mensaje de error del NIT o null si es válido. */
export function errorNit(valor) {
  const texto = String(valor ?? "").trim().replace(/[.\s]/g, "");
  const m = NIT_RE.exec(texto);
  if (!m) return MSG.nitFormato;
  const esperado = digitoVerificacionNit(m[1]);
  if (Number(m[2]) !== esperado) return `El dígito de verificación del NIT no coincide: para ${m[1]} debería ser ${esperado}`;
  return null;
}

export function errorDocumento(tipo, numero) {
  const regla = REGLAS_DOCUMENTO[tipo];
  if (!regla) return "Selecciona el tipo de documento";
  const [patron, mensaje] = regla;
  return patron.test(String(numero ?? "").trim().toUpperCase()) ? null : mensaje;
}

// ---------- Normalizadores para máscaras de entrada ----------
export const soloDigitos = (texto, max = 10) => String(texto ?? "").replace(/\D/g, "").slice(0, max);
export const formatoNit = (texto) => {
  const limpio = String(texto ?? "").replace(/[^\d]/g, "").slice(0, 11);
  return limpio.length > 9 ? `${limpio.slice(0, limpio.length - 1)}-${limpio.slice(-1)}` : limpio;
};

// ---------- Esquemas Zod reutilizables ----------
const texto = (valor) => (typeof valor === "string" ? valor : String(valor ?? ""));

/**
 * "Hoy" es el día calendario del negocio (Colombia), igual que ZONA_NEGOCIO en
 * backend/app/core/validaciones.py: ni el de UTC (de 19:00 a 24:00 ya es mañana)
 * ni el de la zona del navegador. Devuelve "AAAA-MM-DD", comparable como texto.
 */
export const ZONA_NEGOCIO = "America/Bogota";
const formatoDiaNegocio = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA_NEGOCIO, year: "numeric", month: "2-digit", day: "2-digit" });
export const diaNegocio = (fecha) => formatoDiaNegocio.format(fecha);

export const esquemas = {
  nombrePersona: () =>
    z
      .string()
      .transform((s) => s.replace(/\s+/g, " ").trim())
      .refine((s) => s.length > 0, MSG.obligatorio)
      .refine((s) => s.length >= 2 && s.length <= 80 && NOMBRE_PERSONA_RE.test(s), MSG.nombrePersona),

  nombreItem: (max = 100) =>
    z
      .string()
      .refine((s) => s.trim().length > 0, MSG.obligatorio)
      .refine((s) => s === s.trim() && s.length >= 2 && s.length <= max && NOMBRE_ITEM_RE.test(s), MSG.nombreItem),

  nombreCarta: (max = 100) =>
    z
      .string()
      .refine((s) => s.trim().length > 0, MSG.obligatorio)
      .refine((s) => s === s.trim() && s.length >= 2 && s.length <= max && NOMBRE_CARTA_RE.test(s), MSG.nombreCarta),

  mesa: () =>
    z
      .string()
      .transform((s) => s.replace(/\s+/g, " ").trim().toUpperCase())
      .refine((s) => s.length > 0, MSG.obligatorio)
      .refine((s) => s.length <= 20 && MESA_RE.test(s), MSG.mesa),

  hora: () => z.string().refine((s) => HORA_RE.test(s), MSG.hora),

  sku: () =>
    z
      .string()
      .transform((s) => s.trim().toUpperCase())
      .refine((s) => s.length > 0, MSG.obligatorio)
      .refine((s) => s.length >= 2 && s.length <= 50 && SKU_RE.test(s), MSG.sku),

  descripcion: (max) => z.string().max(max, MSG.maximo(max)),

  email: () =>
    z
      .string()
      .transform((s) => s.trim().toLowerCase())
      .refine((s) => s.length > 0, MSG.obligatorio)
      .refine((s) => EMAIL_RE.test(s), MSG.email),

  emailOpcional: () =>
    z
      .string()
      .transform((s) => s.trim().toLowerCase())
      .refine((s) => s === "" || EMAIL_RE.test(s), MSG.email),

  telefono: ({ obligatorio = false } = {}) =>
    z
      .string()
      .transform((s) => s.replace(/\D/g, ""))
      .refine((s) => !obligatorio || s.length > 0, MSG.obligatorio)
      .refine((s) => s === "" || TELEFONO_RE.test(s), MSG.telefono),

  nit: () =>
    z.string().superRefine((s, ctx) => {
      if (s.trim().length === 0) ctx.addIssue({ code: "custom", message: MSG.obligatorio });
      else {
        const err = errorNit(s);
        if (err) ctx.addIssue({ code: "custom", message: err });
      }
    }),

  precio: ({ permitirCero = false, obligatorio = true } = {}) =>
    z
      .string()
      .refine((s) => !obligatorio || s.trim() !== "", MSG.obligatorio)
      .refine((s) => {
        if (s.trim() === "") return true;
        const n = Number(s);
        if (!Number.isFinite(n) || n > PRECIO_MAX || n < 0 || (n === 0 && !permitirCero)) return false;
        return /^\d+(\.\d{1,2})?$/.test(s.trim());
      }, MSG.precio),

  entero: (min, max, { obligatorio = true } = {}) =>
    z
      .string()
      .refine((s) => !obligatorio || s.trim() !== "", MSG.obligatorio)
      .refine((s) => s.trim() === "" || (/^\d+$/.test(s.trim()) && Number(s) >= min && Number(s) <= max), MSG.entero(min, max)),

  porcentaje: () =>
    z
      .string()
      .refine((s) => s.trim() !== "", MSG.obligatorio)
      .refine((s) => /^\d+(\.\d{1,2})?$/.test(s.trim()) && Number(s) >= 0 && Number(s) <= 100, MSG.porcentaje),

  obligatorio: () => z.string().refine((s) => texto(s).trim().length > 0, MSG.obligatorio),

  fechaNoFutura: () =>
    z.string().refine((s) => s === "" || new Date(s).getTime() <= Date.now() + 5 * 60 * 1000, MSG.fechaFutura),

  fechaNoPasada: () =>
    z.string().refine((s) => {
      if (s === "") return true;
      const fecha = new Date(s);
      return !Number.isNaN(fecha.getTime()) && diaNegocio(fecha) >= diaNegocio(new Date());
    }, MSG.entregaPasada),
};

/** Ítems de compra/venta/pedido: cada línea con producto, cantidad y precio válidos. */
export const esquemaItems = z
  .array(
    z.object({
      producto_id: z.string().min(1, "Selecciona un producto"),
      cantidad: esquemas.entero(1, CANTIDAD_MAX),
      precio_unitario: esquemas.precio({ permitirCero: true }),
    })
  )
  .min(1, "Agrega al menos un producto");
