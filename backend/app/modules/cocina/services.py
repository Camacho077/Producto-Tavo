"""
Movimientos de la cocina (fase 5): Tomar (entrante → en preparación) y
Finalizar (en preparación → lista), con quién y cuándo. `ahora` solo lo usan
los datos de demostración (la API siempre registra la hora del servidor).
"""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError
from app.core.tiempo import ahora_utc
from app.modules.ordenes import models
from app.modules.ordenes.services import registrar_evento
from app.modules.seguridad.models import Usuario


def mover(db: Session, usuario: Usuario, comanda_id: uuid.UUID, desde: str, hacia: str, accion: str, ahora: datetime | None = None) -> models.Comanda:
    comanda = obtener_del_tenant(db, models.Comanda, usuario.tenant_id, comanda_id, "La comanda indicada")
    orden = comanda.orden
    nombre = f"la comanda {comanda.numero} de la orden #{orden.numero}"
    if orden.estado == "anulada" or comanda.estado == "anulada":
        raise ConflictError(f"No se puede {accion} {nombre}: la orden fue {'anulada' if orden.estado == 'anulada' else 'modificada'} y ya no va.")
    if comanda.estado != desde:
        legible = {"entrante": "por empezar", "en_preparacion": "en preparación", "lista": "lista", "entregada": "entregada"}[comanda.estado]
        raise ConflictError(f"No se puede {accion} {nombre}: ya está {legible} (quizá otra persona la movió).")
    ahora = ahora or ahora_utc()
    comanda.estado = hacia
    if hacia == "en_preparacion":
        comanda.tomada_en, comanda.tomada_por = ahora, usuario.nombre_completo
        registrar_evento(orden, "tomada", f"Comanda {comanda.numero}", usuario.nombre_completo, ahora)
    else:
        comanda.lista_en, comanda.lista_por = ahora, usuario.nombre_completo
        registrar_evento(orden, "lista", f"Comanda {comanda.numero}", usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(comanda)
    return comanda
