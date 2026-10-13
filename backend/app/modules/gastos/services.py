"""Registrar un gasto (fase 6). `ahora` solo lo usan los datos de demostración."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.caja.services import caja_abierta
from app.modules.gastos import models, schemas
from app.modules.seguridad.models import Usuario


def aplicar(db: Session, usuario: Usuario, gasto: models.Gasto, payload: schemas.GastoIn) -> None:
    """Pasa los datos al gasto. Si sale de la caja, se amarra a la caja abierta
    (solo efectivo) y cuenta en su cuadre."""
    if payload.de_caja and payload.medio_pago != "efectivo":
        raise ConflictError("Solo un gasto en efectivo puede salir de la caja.")
    if payload.de_caja:
        if gasto.caja_id is None:
            caja = caja_abierta(db, usuario.tenant_id)
            if caja is None:
                raise ConflictError("No hay caja abierta de donde sacar el efectivo: desmarca «Pagado desde la caja» o abre la caja.")
            gasto.caja_id = caja.id
    else:
        gasto.caja_id = None
    for campo in ("fecha", "categoria", "descripcion", "valor", "medio_pago"):
        setattr(gasto, campo, getattr(payload, campo))


def registrar(db: Session, usuario: Usuario, payload: schemas.GastoIn, ahora: datetime | None = None) -> models.Gasto:
    gasto = models.Gasto(tenant_id=usuario.tenant_id, usuario_nombre=usuario.nombre_completo)
    if ahora is not None:
        gasto.created_at = gasto.updated_at = ahora
    aplicar(db, usuario, gasto, payload)
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto
