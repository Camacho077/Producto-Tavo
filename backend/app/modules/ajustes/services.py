import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.consultas import obtener_del_tenant
from app.core.validaciones import ZONA_NEGOCIO
from app.modules.ajustes import models
from app.modules.ajustes.schemas import ConfiguracionRestaurante


def obtener_zona_o_404(db: Session, tenant_id: uuid.UUID, zona_id: uuid.UUID) -> models.Zona:
    return obtener_del_tenant(db, models.Zona, tenant_id, zona_id, "La zona indicada")


def obtener_mesa_o_404(db: Session, tenant_id: uuid.UUID, mesa_id: uuid.UUID) -> models.Mesa:
    return obtener_del_tenant(db, models.Mesa, tenant_id, mesa_id, "La mesa indicada")


def conteo_mesas_por_zona(db: Session, tenant_id: uuid.UUID) -> dict:
    filas = (
        db.query(models.Mesa.zona_id, func.count(models.Mesa.id))
        .filter(models.Mesa.tenant_id == tenant_id, models.Mesa.zona_id.isnot(None))
        .group_by(models.Mesa.zona_id)
        .all()
    )
    return dict(filas)


def serializar_zona(z: models.Zona, mesas_count: int = 0) -> dict:
    return {"id": z.id, "nombre": z.nombre, "orden": z.orden, "mesas_count": mesas_count, "created_at": z.created_at}


def serializar_mesa(m: models.Mesa) -> dict:
    return {
        "id": m.id,
        "nombre": m.nombre,
        "zona_id": m.zona_id,
        "zona_nombre": m.zona.nombre if m.zona else None,
        "puestos": m.puestos,
        "activo": m.activo,
        "created_at": m.created_at,
    }


# ---------------------------------------------------------------------------
# Jornada: el "día de trabajo" del restaurante
# ---------------------------------------------------------------------------
def _minutos(hhmm: str) -> int:
    horas, minutos = hhmm.split(":")
    return int(horas) * 60 + int(minutos)


def fecha_jornada(config: ConfiguracionRestaurante, instante_utc: datetime) -> date:
    """Día de la jornada a la que pertenece un instante (UTC naive). La
    jornada empieza a la hora de inicio EN COLOMBIA: con inicio a las 06:00,
    las 05:59 del martes todavía son la jornada del lunes."""
    local = instante_utc.replace(tzinfo=None) + ZONA_NEGOCIO.utcoffset(None)
    desplazado = local - timedelta(minutes=_minutos(config.jornada.inicio))
    return desplazado.date()


def limites_jornada(config: ConfiguracionRestaurante, dia: date) -> tuple[datetime, datetime]:
    """[inicio, fin) de la jornada `dia`, en UTC naive (como las columnas)."""
    inicio_local = datetime(dia.year, dia.month, dia.day) + timedelta(minutes=_minutos(config.jornada.inicio))
    inicio_utc = inicio_local - ZONA_NEGOCIO.utcoffset(None)
    return inicio_utc, inicio_utc + timedelta(days=1)
