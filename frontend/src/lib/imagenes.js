import { api } from "@/lib/api";

/**
 * URL pública de una imagen ya procesada por el backend (WebP). Un `<img>` no
 * manda el token, por eso la ruta del backend es pública (por UUID aleatorio)
 * y la respuesta se cachea para siempre: reemplazar una imagen crea otra con
 * otro id (backend/app/modules/imagenes).
 */
export function urlImagen(id) {
  return id ? `${api.defaults.baseURL}/imagenes/${id}` : null;
}

// Mismos topes que backend/app/modules/imagenes/services.py: se revisan
// ANTES de subir para no mandar 12 MB por la red y recibir un 413.
export const TIPOS_IMAGEN = ["image/jpeg", "image/png", "image/webp"];
export const MAX_BYTES_IMAGEN = 5 * 1024 * 1024;

/** Mensaje de error si el archivo no sirve, o null. */
export function errorArchivoImagen(archivo) {
  if (!archivo) return "No elegiste ningún archivo.";
  if (!TIPOS_IMAGEN.includes(archivo.type)) {
    return `El archivo «${archivo.name}» no es una imagen JPG, PNG o WebP.`;
  }
  if (archivo.size > MAX_BYTES_IMAGEN) {
    const mb = (archivo.size / 1024 / 1024).toFixed(1).replace(".", ",");
    return `La imagen pesa ${mb} MB y el máximo es 5 MB. Elige una foto más liviana.`;
  }
  return null;
}
