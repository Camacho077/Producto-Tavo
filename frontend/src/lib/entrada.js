/**
 * Filtros de entrada por tipo de campo. Deciden, carácter por carácter, qué
 * puede entrar en un <input>. Se aplican en `beforeinput` (teclado, IME,
 * autocompletado) y en `paste`, ANTES de que el carácter llegue al value:
 * la tecla inválida no produce nada. Nunca se reescribe el value en
 * onChange, así el cursor no salta al corregir en medio del texto.
 *
 * Cada filtro: { admite(caracter, valorActual, posicion), formatear?(texto) }
 *  - `admite` decide si un carácter puede insertarse.
 *  - `formatear` (opcional) reescribe el texto completo tras insertar o
 *    borrar (máscaras: teléfono "300 123 4567", NIT "900123456-7").
 *  - `maximo` (opcional) limita la cantidad de caracteres "útiles".
 */

const LETRA_RE = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]/;
const DIGITO_RE = /[0-9]/;
const ALFANUM_RE = /[A-Za-z0-9]/;
const SKU_RE = /[A-Za-z0-9_-]/;
const CORREO_RE = /[A-Za-z0-9@._%+-]/;
const CARTA_RE = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9' .,\-+&/()%]/;
const MESA_RE = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 -]/;

const soloDigitos = (t) => t.replace(/\D/g, "");

/** Dígitos y UN separador decimal (la coma se vuelve punto), con tope de decimales. */
function filtroDecimal(decimales) {
  return {
    admite: (c, valor, posicion) => {
      if (DIGITO_RE.test(c)) {
        const punto = valor.indexOf(".");
        return punto === -1 || posicion <= punto || valor.length - punto - 1 < decimales;
      }
      return (c === "." || c === ",") && !valor.includes(".") && valor.length > 0;
    },
    normalizarCaracter: (c) => (c === "," ? "." : c),
  };
}

export const FILTROS = {
  // Nombres de persona, categoría, razón social, rol.
  nombre: {
    admite: (c) => LETRA_RE.test(c),
  },

  // Nombres de la carta (platos, insumos, combos, zonas, negocio): letras,
  // dígitos y los signos . , - + & / ( ) % — "Gaseosa 400 ml", "Pollo 1/4".
  carta: {
    admite: (c) => CARTA_RE.test(c),
  },

  // Mesas: "B2", "Terraza 3", en mayúsculas.
  mesa: {
    admite: (c) => MESA_RE.test(c),
    normalizarCaracter: (c) => c.toUpperCase(),
    maximo: 20,
  },

  // Stock, cantidades: dígitos, sin signo ni decimales.
  entero: {
    admite: (c) => DIGITO_RE.test(c),
  },

  // Precios, montos, porcentajes: dígitos y UN separador decimal (punto; la
  // coma se convierte en punto), máximo 2 decimales.
  decimal: filtroDecimal(2),
  // Cantidades de insumos (2026-10-12): 1,5 kg; 0,25 L → 3 decimales.
  cantidad: filtroDecimal(3),
  // Costo unitario de un insumo ($ por gramo puede llevar decimales): 4.
  costo: filtroDecimal(4),

  // Documentos de identidad: solo dígitos.
  digitos: {
    admite: (c) => DIGITO_RE.test(c),
  },

  // Pasaporte: letras y números, en mayúsculas.
  alfanumerico: {
    admite: (c) => ALFANUM_RE.test(c),
    normalizarCaracter: (c) => c.toUpperCase(),
  },

  // SKU: letras, números, guion y guion bajo, en mayúsculas.
  sku: {
    admite: (c) => SKU_RE.test(c),
    normalizarCaracter: (c) => c.toUpperCase(),
  },

  // NIT: solo dígitos; la máscara pone el guion antes del dígito de verificación.
  nit: {
    admite: (c) => DIGITO_RE.test(c),
    maximo: 11,
    formatear: (t) => {
      const d = soloDigitos(t).slice(0, 11);
      return d.length > 9 ? `${d.slice(0, -1)}-${d.slice(-1)}` : d;
    },
    desformatear: soloDigitos,
  },

  // Teléfono colombiano: 10 dígitos, máscara "300 123 4567".
  telefono: {
    admite: (c) => DIGITO_RE.test(c),
    maximo: 10,
    formatear: (t) => {
      const d = soloDigitos(t).slice(0, 10);
      return [d.slice(0, 3), d.slice(3, 6), d.slice(6, 10)].filter(Boolean).join(" ");
    },
    desformatear: soloDigitos,
  },

  // Documento del cliente en ventas: cédula (dígitos) o NIT con guion.
  documento_nit: {
    admite: (c, valor) => DIGITO_RE.test(c) || (c === "-" && valor.length > 0 && !valor.includes("-")),
  },

  // Correo: sin espacios ni caracteres ilegales; @ . - _ + % sí entran.
  correo: {
    admite: (c) => CORREO_RE.test(c),
    normalizarCaracter: (c) => c.toLowerCase(),
  },
};

/** Filtra un texto (pegado) dejando solo los caracteres admitidos, en orden. */
export function filtrarTexto(filtro, texto, valorActual = "", posicion = 0) {
  let salida = "";
  let valorSimulado = valorActual;
  let pos = posicion;
  for (const c of String(texto ?? "")) {
    const car = filtro.normalizarCaracter ? filtro.normalizarCaracter(c) : c;
    if (filtro.admite(car, valorSimulado, pos)) {
      salida += car;
      valorSimulado = valorSimulado.slice(0, pos) + car + valorSimulado.slice(pos);
      pos += 1;
    }
  }
  return salida;
}

/**
 * Escribe un valor nuevo en el <input> de forma que React lo vea como una
 * edición del usuario (dispara onChange) y deja el cursor donde se indica.
 */
export function escribirEnInput(input, valor, cursor) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  if (setter) setter.call(input, valor);
  else input.value = valor;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  try {
    input.setSelectionRange(cursor, cursor);
  } catch {
    /* algunos tipos de input no permiten selección */
  }
}

/** Cuántos caracteres "útiles" (sin formato) hay antes de una posición. */
function utilesHasta(filtro, texto, posicion) {
  const parte = texto.slice(0, posicion);
  return filtro.desformatear ? filtro.desformatear(parte).length : parte.length;
}

/** Posición del cursor en el texto formateado tras `n` caracteres útiles. */
function posicionTrasUtiles(filtro, textoFormateado, n) {
  if (!filtro.desformatear) return n;
  let contados = 0;
  for (let i = 0; i < textoFormateado.length; i++) {
    if (filtro.desformatear(textoFormateado[i]).length) {
      contados += 1;
      if (contados === n) return i + 1;
    }
  }
  return n === 0 ? 0 : textoFormateado.length;
}

/**
 * Manejador de `beforeinput` y `paste`. Devuelve true si ya se encargó de la
 * edición (y el evento nativo debe cancelarse).
 */
export function interceptarEntrada(filtro, e) {
  const input = e.currentTarget;
  if (!input || input.readOnly || input.disabled) return false;
  const valor = input.value ?? "";
  const inicio = input.selectionStart ?? valor.length;
  const fin = input.selectionEnd ?? inicio;

  // ---- Pegado ----
  if (e.type === "paste") {
    const texto = e.clipboardData?.getData("text") ?? "";
    e.preventDefault();
    insertar(filtro, input, valor, inicio, fin, texto);
    return true;
  }

  const tipo = e.inputType ?? "";

  // ---- Borrado en campos con máscara: si el carácter a borrar es de
  // formato (espacio/guion), se salta y se borra el dígito de al lado. ----
  if (filtro.formatear && (tipo === "deleteContentBackward" || tipo === "deleteContentForward")) {
    e.preventDefault();
    let a = inicio;
    let b = fin;
    if (a === b) {
      if (tipo === "deleteContentBackward") {
        a = Math.max(0, a - 1);
        while (a > 0 && !filtro.admite(valor[a], valor, a)) a -= 1;
      } else {
        b = Math.min(valor.length, b + 1);
        while (b < valor.length && !filtro.admite(valor[b - 1], valor, b - 1)) b += 1;
      }
    }
    const utiles = filtro.desformatear(valor.slice(0, a) + valor.slice(b));
    const nuevo = filtro.formatear(utiles);
    escribirEnInput(input, nuevo, posicionTrasUtiles(filtro, nuevo, utilesHasta(filtro, valor, a)));
    return true;
  }

  // Solo inserciones de texto; los demás inputTypes (borrar, deshacer) pasan.
  if (!tipo.startsWith("insert")) return false;
  const texto = e.data ?? e.dataTransfer?.getData("text") ?? "";
  if (texto === "" && tipo !== "insertLineBreak") return false;

  e.preventDefault();
  insertar(filtro, input, valor, inicio, fin, texto);
  return true;
}

function insertar(filtro, input, valor, inicio, fin, texto) {
  const base = valor.slice(0, inicio) + valor.slice(fin);
  let limpio = filtrarTexto(filtro, texto, base, inicio);
  // Respeta el maxLength del input aunque la inserción sea programática.
  const tope = input.maxLength > 0 ? input.maxLength : Infinity;
  if (!filtro.formatear && base.length + limpio.length > tope) limpio = limpio.slice(0, Math.max(0, tope - base.length));
  if (!limpio && !filtro.formatear) {
    // Nada válido que insertar; si había selección, se reemplaza por nada.
    if (base !== valor) escribirEnInput(input, base, inicio);
    return;
  }

  let nuevo = base.slice(0, inicio) + limpio + base.slice(inicio);
  let cursor = inicio + limpio.length;

  if (filtro.formatear) {
    const utiles = filtro.desformatear(nuevo);
    const recortado = filtro.maximo ? utiles.slice(0, filtro.maximo) : utiles;
    nuevo = filtro.formatear(recortado);
    const utilesAntes = Math.min(utilesHasta(filtro, base, inicio) + limpio.length, recortado.length);
    cursor = posicionTrasUtiles(filtro, nuevo, utilesAntes);
  } else if (filtro.maximo && nuevo.length > filtro.maximo) {
    return;
  }

  if (nuevo === valor) return;
  escribirEnInput(input, nuevo, cursor);
}
