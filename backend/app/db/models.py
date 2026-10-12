"""
Modelos "core" que no pertenecen a un módulo de negocio específico:
Tenant = cada empresa cliente que usa el sistema.
Aquí también vive la configuración de personalización visual (theming)
que cada cliente puede ajustar sin tocar el código.
"""
from sqlalchemy import Column, String, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.core.config import settings
from app.db.session import Base
from app.db.mixins import TimestampMixin, gen_uuid


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre_empresa = Column(String, nullable=False)
    nit = Column(String, unique=True, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)

    # Plan contratado: define qué módulos ve este tenant en el frontend.
    # El valor inicial sale de settings.PLAN_POR_DEFECTO (ver core/config.py).
    plan = Column(String, default=lambda: settings.PLAN_POR_DEFECTO, nullable=False)  # basico | estandar | pro_ia

    # Personalización visual del cliente (colores, logo, tipografía)
    # Ejemplo: {"color_primario": "#1E3A5F", "logo_url": "...", "fuente": "Inter"}
    theme_config = Column(JSON, default=dict, nullable=False)

    # Módulos activos explícitamente (independiente del plan, para casos a medida)
    modulos_activos = Column(JSON, default=list, nullable=False)

    # DATOS DEL NEGOCIO (2026-10-12): salen en la comanda, la factura interna
    # y los PDF. Los edita el administrador en Ajustes.
    direccion = Column(String, nullable=True)
    ciudad = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    correo = Column(String, nullable=True)
    # Logo para la comanda y la factura (tabla `imagenes`). Sin clave foránea a
    # propósito: `imagenes` ya apunta a `tenants` y la referencia circular
    # obligaría a crear las tablas en dos pasos. Lo valida el servicio.
    logo_id = Column(UUID(as_uuid=True), nullable=True)

    # CONFIGURACIÓN DEL RESTAURANTE (2026-10-12): tipos de orden, medios de
    # pago, impuesto al consumo, propina, cocina, jornada e impresoras. El
    # esquema (con sus valores por defecto) es `ConfiguracionRestaurante` en
    # app/modules/ajustes/schemas.py: lo guardado siempre se lee a través de él.
    configuracion = Column(JSON, default=dict, nullable=False, server_default="{}")
