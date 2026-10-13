"""
PANTALLA DE COCINA (fase 5, 2026-10-12).

La cocina trabaja COMANDAS (cada envío de una orden): entrante → en
preparación (Tomar) → lista (Finalizar). Solo ve lo que va a cocina; la
venta directa no aparece. Queda registrado quién y a qué hora. La pantalla
consulta cada pocos segundos (consulta corta, sin WebSocket: funciona igual
detrás de cualquier proxy o túnel).
"""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError
from app.core.permisos import usuario_con_permiso
from app.core.tiempo import ahora_utc
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.ajustes.schemas import configuracion_de
from app.modules.ordenes import models
from app.modules.ordenes.services import NOMBRE_TIPO, registrar_evento
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/cocina", tags=["Cocina"])

# Cuánto tiempo se muestran en cocina los avisos de platos u órdenes anuladas.
MINUTOS_AVISOS = 15
ESTADOS_EN_COCINA = ("entrante", "en_preparacion", "lista")


def _destino(o: models.Orden) -> str:
    if o.tipo == "local":
        return f"Mesa {o.mesa.nombre}" if o.mesa else "En el local"
    return o.cliente_nombre or NOMBRE_TIPO[o.tipo].capitalize()


def _serializar(c: models.Comanda) -> dict:
    o = c.orden
    return {
        "id": c.id,
        "numero": c.numero,
        "estado": c.estado,
        "created_at": c.created_at,
        "tomada_en": c.tomada_en,
        "tomada_por": c.tomada_por,
        "lista_en": c.lista_en,
        "lista_por": c.lista_por,
        "orden_id": o.id,
        "orden_numero": o.numero,
        "tipo": o.tipo,
        "destino": _destino(o),
        "mesero_nombre": o.mesero_nombre,
        "nota": o.nota if c.numero == 1 else None,
        "items": [
            {
                "id": i.id, "nombre": i.nombre, "cantidad": i.cantidad, "nota": i.nota,
                "modificadores": i.modificadores or [], "anulado": i.anulado, "anulado_motivo": i.anulado_motivo,
            }
            for i in c.items if i.va_a_cocina
        ],
    }


@router.get("/comandas")
def comandas(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("cocina", "ver"))):
    """Las comandas vivas, en orden de llegada, y los avisos recientes de
    lo que se anuló (para que cocina no prepare algo que ya no va)."""
    tenant_id = usuario.tenant_id
    config = configuracion_de(db.get(Tenant, tenant_id))
    filas = (
        db.query(models.Comanda)
        .join(models.Orden, models.Orden.id == models.Comanda.orden_id)
        .options(joinedload(models.Comanda.orden).joinedload(models.Orden.mesa), selectinload(models.Comanda.items))
        .filter(
            models.Comanda.tenant_id == tenant_id,
            models.Comanda.va_a_cocina.is_(True),
            models.Comanda.estado.in_(ESTADOS_EN_COCINA),
            models.Orden.estado == "abierta",
        )
        .order_by(models.Comanda.created_at)
        .all()
    )
    ahora = ahora_utc()
    eventos = (
        db.query(models.OrdenEvento)
        .join(models.Orden, models.Orden.id == models.OrdenEvento.orden_id)
        .filter(
            models.OrdenEvento.tenant_id == tenant_id,
            models.OrdenEvento.tipo.in_(("item_anulado", "anulada")),
            models.OrdenEvento.created_at >= ahora - timedelta(minutes=MINUTOS_AVISOS),
        )
        .order_by(models.OrdenEvento.created_at.desc())
        .with_entities(models.OrdenEvento, models.Orden.numero)
        .all()
    )
    return {
        "ahora": ahora,
        "alerta_minutos": config.alerta_cocina_minutos,
        "sonido": config.sonido_cocina,
        "comandas": [_serializar(c) for c in filas if any(i.va_a_cocina and not i.anulado for i in c.items)],
        "avisos": [
            {
                "id": e.id,
                "orden_numero": numero,
                "texto": f"Orden #{numero} anulada: {e.nota}" if e.tipo == "anulada" else f"Orden #{numero}: se quitó {e.nota}",
                "created_at": e.created_at,
            }
            for e, numero in eventos
        ],
    }


def _cambiar(db: Session, usuario: Usuario, comanda_id: uuid.UUID, desde: str, hacia: str, accion: str) -> dict:
    comanda = obtener_del_tenant(db, models.Comanda, usuario.tenant_id, comanda_id, "La comanda indicada")
    orden = comanda.orden
    nombre = f"la comanda {comanda.numero} de la orden #{orden.numero}"
    if orden.estado != "abierta" or comanda.estado == "anulada":
        raise ConflictError(f"No se puede {accion} {nombre}: la orden fue {orden.estado if orden.estado != 'abierta' else 'modificada'} y ya no va.")
    if comanda.estado != desde:
        legible = {"entrante": "por empezar", "en_preparacion": "en preparación", "lista": "lista", "entregada": "entregada"}[comanda.estado]
        raise ConflictError(f"No se puede {accion} {nombre}: ya está {legible} (quizá otra persona la movió).")
    ahora: datetime = ahora_utc()
    comanda.estado = hacia
    if hacia == "en_preparacion":
        comanda.tomada_en, comanda.tomada_por = ahora, usuario.nombre_completo
        registrar_evento(orden, "tomada", f"Comanda {comanda.numero}", usuario.nombre_completo, ahora)
    else:
        comanda.lista_en, comanda.lista_por = ahora, usuario.nombre_completo
        registrar_evento(orden, "lista", f"Comanda {comanda.numero}", usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(comanda)
    return _serializar(comanda)


@router.post("/comandas/{comanda_id}/tomar")
def tomar(comanda_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("cocina", "cambiar_estado"))):
    return _cambiar(db, usuario, comanda_id, "entrante", "en_preparacion", "tomar")


@router.post("/comandas/{comanda_id}/finalizar")
def finalizar(comanda_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("cocina", "cambiar_estado"))):
    return _cambiar(db, usuario, comanda_id, "en_preparacion", "lista", "finalizar")
