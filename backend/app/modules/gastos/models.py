"""
GASTOS DEL NEGOCIO (fase 6, 2026-10-12): arriendo, servicios, nómina, gas,
aseo y otros. Sin ellos no se puede responder "¿cuánto gano?": ventas menos
costo de lo vendido es la utilidad BRUTA; restando los gastos, la REAL.

Un gasto pagado en efectivo DESDE LA CAJA abierta queda amarrado a ella y
se descuenta de lo que se espera encontrar al cerrarla.
"""
from sqlalchemy import Column, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base
from app.modules.caja import models as _caja  # noqa: F401

CATEGORIAS = {
    "arriendo": "Arriendo",
    "servicios": "Servicios públicos",
    "nomina": "Nómina",
    "gas": "Gas",
    "aseo": "Insumos de aseo",
    "mantenimiento": "Mantenimiento",
    "impuestos": "Impuestos y trámites",
    "otros": "Otros",
}


class Gasto(Base, TenantMixin, TimestampMixin):
    __tablename__ = "gastos"
    __table_args__ = (
        Index("ix_gastos_tenant_fecha", "tenant_id", "fecha"),
        Index("ix_gastos_caja", "caja_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    fecha = Column(Date, nullable=False)  # día de Colombia
    categoria = Column(String(20), nullable=False)
    descripcion = Column(String(150), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    medio_pago = Column(String(15), nullable=False, default="efectivo")
    caja_id = Column(UUID(as_uuid=True), ForeignKey("cajas.id"), nullable=True)
    usuario_nombre = Column(String, nullable=True)

    caja = relationship("CajaSesion")
