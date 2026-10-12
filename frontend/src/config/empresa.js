/**
 * Datos de la empresa que presta el servicio (JS Company). Se muestran en el
 * pie de todas las pantallas y rellenan los marcadores `{{campo}}` de los
 * documentos legales (`modules/legal/textos/*.md`).
 *
 * POR COMPLETAR (2026-09-30): los valores entre corchetes son marcadores a
 * propósito. Hay que reemplazarlos con los datos reales —razón social y NIT
 * tal como aparecen en el RUT/Cámara de Comercio— ANTES de vender. Cambiarlos
 * aquí los cambia en el pie y en los documentos a la vez.
 */
export const EMPRESA = {
  marca: "JS Company",
  razonSocial: "[RAZÓN SOCIAL POR COMPLETAR]",
  nit: "[NIT POR COMPLETAR]",
  ciudad: "[CIUDAD POR COMPLETAR]",
  direccion: "[DIRECCIÓN POR COMPLETAR]",
  correo: "[CORREO DE CONTACTO POR COMPLETAR]",
  // Canal para consultas y reclamos de titulares (Ley 1581, art. 17 lit. j y
  // Decreto 1377, art. 13). Puede ser el mismo correo de contacto.
  correoDatos: "[CORREO DE PROTECCIÓN DE DATOS POR COMPLETAR]",
  telefono: "[TELÉFONO POR COMPLETAR]",
  // Proveedor de servidores y base de datos en producción (subencargado).
  hosting: "[PROVEEDOR DE HOSTING POR DEFINIR]",
  paisHosting: "[PAÍS DE LOS SERVIDORES POR DEFINIR]",
};
