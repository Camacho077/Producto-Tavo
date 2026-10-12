"""
Consultas que todos los módulos repiten.

La más frecuente es "tráeme este registro de ESTA empresa o devuelve 404".
Es la pieza donde se aplica el aislamiento multi-tenant, así que vive en un
solo sitio: cada módulo la usaba copiada, con el mismo cuerpo y solo el
modelo y el texto distintos.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.mensajes import no_existe


def obtener_del_tenant(db: Session, modelo, tenant_id: uuid.UUID, registro_id: uuid.UUID, etiqueta: str):
    """
    Busca por id DENTRO del tenant. Filtrar por `tenant_id` aquí es lo que
    impide que una empresa lea registros de otra: si el id existe pero es de
    otra empresa, la respuesta es la misma que si no existiera.

    `etiqueta` es cómo se nombra el registro en el mensaje de error
    ("El producto indicado").
    """
    registro = db.query(modelo).filter(modelo.id == registro_id, modelo.tenant_id == tenant_id).first()
    if registro is None:
        raise NotFoundError(no_existe(etiqueta))
    return registro
