import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.core import validaciones as v


# ---------- Ítems ----------
class ItemCreate(BaseModel):
    producto_id: uuid.UUID
    cantidad: int
    precio_unitario: Decimal

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return v.entero(valor, 1, v.CANTIDAD_MAX)

    @field_validator("precio_unitario")
    @classmethod
    def _precio(cls, valor):
        return v.precio(valor, permitir_cero=True)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    producto_id: uuid.UUID
    producto_nombre: str | None = None
    producto_sku: str | None = None
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal = Decimal("0")


VentaItemCreate = ItemCreate
VentaItemOut = ItemOut


# ---------- Ventas ----------
class VentaCreate(BaseModel):
    cliente_nombre: str = Field(min_length=2, max_length=80)
    cliente_documento: str | None = Field(default=None, max_length=20)
    fecha: datetime

    @field_validator("cliente_nombre")
    @classmethod
    def _cliente(cls, valor):
        return v.nombre_item(valor, 80)

    @field_validator("cliente_documento")
    @classmethod
    def _documento(cls, valor):
        if valor in (None, ""):
            return None
        texto = valor.strip()
        return v.validar_nit(texto) if "-" in texto else v.validar_documento("CC", texto)

    @field_validator("fecha")
    @classmethod
    def _fecha(cls, valor):
        return v.fecha_no_futura(valor)
    notas: str | None = Field(default=None, max_length=500)
    # True: la venta se completa de una vez y descuenta stock. False: queda
    # pendiente hasta confirmarla (comportamiento original).
    confirmar: bool = False
    items: list[ItemCreate] = Field(min_length=1)


class VentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    numero: int
    codigo: str = ""
    cliente_nombre: str
    cliente_documento: str | None = None
    fecha: datetime
    estado: str
    total: Decimal
    notas: str | None = None
    items: list[ItemOut]
    created_at: datetime | None = None
