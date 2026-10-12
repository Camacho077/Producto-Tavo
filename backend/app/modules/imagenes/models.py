from sqlalchemy import Column, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base


class Imagen(Base, TenantMixin, TimestampMixin):
    """
    Imagen ya procesada por el servidor (WebP comprimido): foto de un plato o
    logo del restaurante. Se guarda en la base (no en disco) para que viaje con
    los respaldos y funcione igual en Docker sin volúmenes extra; pesa decenas
    de KB porque siempre se recorta y comprime antes de guardarla.

    Se sirve por `GET /imagenes/{id}` sin sesión: un `<img>` no manda el token,
    y son fotos de la carta, no datos personales. El id es un UUID aleatorio,
    imposible de adivinar (decisión del 2026-10-12, docs/DECISIONES.md §7).
    """
    __tablename__ = "imagenes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    uso = Column(String(20), nullable=False)  # plato | logo
    contenido = Column(LargeBinary, nullable=False)
    tipo = Column(String(40), nullable=False, default="image/webp", server_default="image/webp")
    ancho = Column(Integer, nullable=False)
    alto = Column(Integer, nullable=False)
    bytes = Column(Integer, nullable=False)
