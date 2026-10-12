"""
Módulo IA (add-on de pago, plan Pro + IA o contratado aparte). Las reglas
viven en `analisis.py`: estadística local sobre los datos del tenant, sin
servicios externos (docs/ia/README.md).

El plan se exige en `tenant_con_permiso`/`usuario_con_permiso` (ver
app/core/permisos.py): una empresa sin el módulo recibe 403 con la causa.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permisos import tiene_permiso, usuario_con_permiso
from app.core.tiempo import ahora_utc
from app.db.session import get_db
from app.modules.ia import analisis
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/ia", tags=["IA (add-on)"])


@router.get("/status")
def estado_modulo_ia(_: Usuario = Depends(usuario_con_permiso("ia", "ver"))):
    """El módulo está activo para esta empresa (si no, el permiso ya respondió 403)."""
    return {"activo": True, "motor": "Reglas estadísticas locales", "servicios_externos": False}


@router.get("/sugerencias")
def sugerencias(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ia", "ver")),
):
    """Sugerencias de negocio con su porqué y sus datos. Costos, márgenes y
    proveedores solo para quien puede ver compras (misma regla que el costo
    del producto)."""
    return analisis.calcular(db, usuario.tenant_id, ahora_utc(), ver_costos=tiene_permiso(usuario, "compras", "ver"))
