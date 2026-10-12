"""
Versiones VIGENTES de los documentos legales que acepta quien registra una
empresa (decisión del 2026-09-30, Ley 1581 de 2012 y Decreto 1377 de 2013,
hoy compilado en el Decreto 1074 de 2015).

El texto vive en `frontend/src/modules/legal/textos/*.md` (BORRADORES
pendientes de revisión por abogado). Cada vez que cambie un texto de forma
sustancial se sube aquí su versión: las aceptaciones viejas quedan con la
versión que se aceptó en su momento (la autorización debe poder probarse,
art. 9 de la Ley 1581 y art. 7 del Decreto 1377), y el frontend muestra la
misma versión (lo comprueba `frontend/src/modules/legal/legal.test.jsx`).
"""

POLITICA_DATOS = "politica_datos"
TERMINOS = "terminos"

VERSIONES = {
    POLITICA_DATOS: "1.1-borrador-2026-10-02",
    TERMINOS: "1.1-borrador-2026-10-02",
}
