/**
 * Descargas que exigen el token (CSV de listados, plantillas): el archivo
 * llega como Blob por axios y se guarda con un <a download> temporal.
 */
export function guardarBlob(blob, nombre) {
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(blob);
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(enlace.href), 0);
}

function leerTexto(blob) {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader();
    lector.onload = () => resolver(lector.result);
    lector.onerror = () => rechazar(lector.error);
    lector.readAsText(blob);
  });
}

/**
 * Con `responseType: "blob"` el error también llega como archivo: se lee el
 * JSON de dentro para mostrar la causa concreta del backend, nunca un
 * genérico (regla de alertas, lib/errores.js).
 */
export async function errorLegible(err) {
  const datos = err?.response?.data;
  if (datos instanceof Blob) {
    try {
      return { ...err, response: { ...err.response, data: JSON.parse(await leerTexto(datos)) } };
    } catch {
      return err;
    }
  }
  return err;
}
