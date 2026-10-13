import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError
from app.core.exportar import campo, responder
from app.core.paginacion import ParametrosPagina, paginar
from app.core.permisos import usuario_con_permiso
from app.db.session import get_db
from app.modules.gastos import models, schemas, services
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/gastos", tags=["Gastos"])

COLUMNAS = [
    ("Fecha", campo("fecha")),
    ("Categoría", lambda f: models.CATEGORIAS.get(f.get("categoria"), f.get("categoria"))),
    ("Descripción", campo("descripcion")),
    ("Valor", campo("valor")),
    ("Medio de pago", campo("medio_pago")),
    ("Desde la caja", lambda f: "Sí" if f.get("caja_id") else "No"),
    ("Registró", campo("usuario_nombre")),
]


def _serializar(g: models.Gasto) -> dict:
    return {
        "id": g.id, "fecha": g.fecha, "categoria": g.categoria, "categoria_nombre": models.CATEGORIAS.get(g.categoria, g.categoria),
        "descripcion": g.descripcion, "valor": g.valor, "medio_pago": g.medio_pago, "caja_id": g.caja_id,
        "caja_numero": g.caja.numero if g.caja_id and g.caja else None, "caja_cerrada": bool(g.caja_id and g.caja and g.caja.estado == "cerrada"),
        "usuario_nombre": g.usuario_nombre, "created_at": g.created_at,
    }


def _obtener(db: Session, tenant_id: uuid.UUID, gasto_id: uuid.UUID) -> models.Gasto:
    return obtener_del_tenant(db, models.Gasto, tenant_id, gasto_id, "El gasto indicado")


def _exigir_editable(gasto: models.Gasto, accion: str) -> None:
    if gasto.caja_id and gasto.caja.estado == "cerrada":
        raise ConflictError(f"No se puede {accion} el gasto: salió de la caja {gasto.caja.numero}, que ya se cerró y su cuadre no se toca.")


@router.get("")
def listar(
    params: ParametrosPagina = Depends(),
    categoria: str | None = Query(default=None, max_length=20),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("gastos", "ver")),
):
    query = db.query(models.Gasto).filter(models.Gasto.tenant_id == usuario.tenant_id)
    if categoria:
        query = query.filter(models.Gasto.categoria == categoria)
    if desde:
        query = query.filter(models.Gasto.fecha >= desde)
    if hasta:
        query = query.filter(models.Gasto.fecha <= hasta)
    total = query.with_entities(func.coalesce(func.sum(models.Gasto.valor), 0)).scalar()
    pagina = paginar(query, params, columnas_busqueda=(models.Gasto.descripcion, models.Gasto.usuario_nombre),
                     orden=(models.Gasto.fecha.desc(), models.Gasto.created_at.desc()))
    pagina["items"] = [_serializar(g) for g in pagina["items"]]
    pagina["suma"] = total
    return responder(pagina, params, None, COLUMNAS, "gastos")


@router.get("/{gasto_id}")
def obtener(gasto_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("gastos", "ver"))):
    return _serializar(_obtener(db, usuario.tenant_id, gasto_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(payload: schemas.GastoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("gastos", "crear"))):
    return _serializar(services.registrar(db, usuario, payload))


@router.put("/{gasto_id}")
def editar(gasto_id: uuid.UUID, payload: schemas.GastoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("gastos", "editar"))):
    gasto = _obtener(db, usuario.tenant_id, gasto_id)
    _exigir_editable(gasto, "editar")
    services.aplicar(db, usuario, gasto, payload)
    db.commit()
    db.refresh(gasto)
    return _serializar(gasto)


@router.delete("/{gasto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(gasto_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("gastos", "eliminar"))):
    gasto = _obtener(db, usuario.tenant_id, gasto_id)
    _exigir_editable(gasto, "eliminar")
    db.delete(gasto)
    db.commit()
