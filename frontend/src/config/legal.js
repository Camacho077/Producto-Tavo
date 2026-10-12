/**
 * Versiones vigentes de los documentos legales. ESPEJO de
 * `backend/app/core/legal.py`, que es el que manda (el backend guarda la
 * versión aceptada). Si no coinciden, falla `modules/legal/legal.test.jsx`.
 */
export const VERSIONES_LEGALES = {
  politica_datos: "1.1-borrador-2026-10-02",
  terminos: "1.1-borrador-2026-10-02",
};

export const RUTAS_LEGALES = {
  politica_datos: "/legal/privacidad",
  terminos: "/legal/terminos",
};
