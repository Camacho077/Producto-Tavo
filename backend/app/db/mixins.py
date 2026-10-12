"""
Este mixin es la pieza clave de la estrategia multi-tenant del sistema:
todas las tablas de datos "de negocio" (productos, ventas, compras, etc.)
heredan de TenantMixin, de forma que cada fila queda amarrada a la empresa
(tenant) dueña de ese dato. Un solo código base y una sola base de datos
sirven a todas las empresas cliente, sin desplegar un backend por cliente.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.core.tiempo import ahora_utc


class TenantMixin:
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)


class TimestampMixin:
    # ahora_utc da lo mismo que el viejo datetime.utcnow (UTC naive) sin la
    # función deprecada, que generaba un aviso por cada fila insertada.
    created_at = Column(DateTime, default=ahora_utc, nullable=False)
    updated_at = Column(DateTime, default=ahora_utc, onupdate=ahora_utc, nullable=False)


def gen_uuid():
    return uuid.uuid4()
