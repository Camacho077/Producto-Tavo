import { api } from "@/lib/api";

/**
 * Traduce un fallo de axios a la frase que se muestra en la alerta roja.
 *
 * Regla del producto: el backend ya devuelve en `detail` un mensaje en
 * español con la CAUSA concreta (ver backend/app/core/mensajes.py), así que
 * aquí ese texto se muestra TAL CUAL. Nunca se reemplaza por un genérico:
 * lo único que arma el frontend es el caso en que no hubo respuesta del
 * servidor (ahí el backend no pudo decir nada) y el detalle de los 422,
 * donde la causa viene repartida campo por campo.
 *
 * `accion` es lo que el usuario intentaba hacer ("eliminar la categoría",
 * "guardar el producto"); se antepone solo cuando el mensaje propio no
 * alcanza para situar el error.
 */
export function mensajeDeError(err, accion) {
  const prefijo = accion ? `No se pudo ${accion}: ` : "";
  const respuesta = err?.response;

  // Sin respuesta: el servidor no respondió, así que la causa la sabe el frontend.
  if (!respuesta) {
    if (err?.code === "ECONNABORTED") {
      return `${prefijo}el servidor tardó demasiado en responder. Intenta otra vez en unos segundos.`;
    }
    return `${prefijo}no hay conexión con el servidor (${api.defaults.baseURL}). Revisa que el backend esté corriendo.`;
  }

  const datos = respuesta.data;

  // 422 de Pydantic: la causa está campo por campo.
  if (Array.isArray(datos?.errores) && datos.errores.length > 0) {
    const detalles = datos.errores.map((e) => (e.campo ? `${etiquetaDeCampo(e.campo)}: ${e.mensaje}` : e.mensaje)).join(" · ");
    return `${prefijo || "Revisa los datos: "}${detalles}`;
  }

  // Caso normal: el backend ya explicó la causa. Se muestra tal cual.
  if (typeof datos?.detail === "string" && datos.detail.trim()) return datos.detail;

  // Sin `detail` utilizable: al menos se dice qué respondió el servidor, para
  // que el mensaje siga siendo accionable y no un "algo falló".
  const porEstado = {
    401: "la sesión expiró. Vuelve a iniciar sesión.",
    403: "tu rol no tiene permiso para esta acción.",
    404: "el registro ya no existe (puede que alguien lo haya eliminado).",
    409: "el registro cambió de estado mientras trabajabas. Recarga la pantalla.",
    413: "el contenido enviado es demasiado grande.",
  };
  const causa = porEstado[respuesta.status] ?? `el servidor respondió con el código ${respuesta.status}.`;
  return `${prefijo}${causa}`;
}

/**
 * Mensaje del inicio de sesión, distinto según la causa (2026-10-13): un
 * compañero veía "No se pudo iniciar sesión" cuando en realidad su backend
 * no estaba corriendo, y buscaba el error en su contraseña.
 *   - sin respuesta: el backend no está (o está en otro puerto);
 *   - 401: correo o contraseña;
 *   - cualquier otro: el motivo que devuelve el backend.
 */
export function mensajeDeLogin(err) {
  if (!err?.response) {
    if (err?.code === "ECONNABORTED") return "El servidor tardó demasiado en responder. Intenta otra vez en unos segundos.";
    return `No se pudo conectar con el servidor en ${api.defaults.baseURL}. Verifica que el backend esté corriendo.`;
  }
  if (err.response.status === 401) return "Correo o contraseña incorrectos.";
  return mensajeDeError(err);
}

/** "cliente_nombre" → "Cliente nombre" para que el 422 se lea en español. */
function etiquetaDeCampo(campo) {
  const limpio = campo.replaceAll("_", " ").replace(/\.\d+\./g, " ");
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}
