import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.core import validaciones as v


# ---------- Ítems (compartidos por ventas y pedidos) ----------
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


# ---------- Pedidos ----------
Prioridad = Literal["baja", "media", "alta", "urgente"]
EstadoPedido = Literal["pendiente", "en_proceso", "listo", "entregado", "cancelado"]


class PedidoCreate(BaseModel):
    cliente_nombre: str = Field(min_length=2, max_length=80)
    cliente_telefono: str | None = Field(default=None, max_length=30)
    cliente_direccion: str | None = Field(default=None, max_length=255)
    fecha: datetime
    fecha_entrega: datetime | None = None
    prioridad: Prioridad = "media"
    notas: str | None = Field(default=None, max_length=500)
    items: list[ItemCreate] = Field(min_length=1)

    @field_validator("cliente_nombre")
    @classmethod
    def _cliente(cls, valor):
        return v.nombre_item(valor, 80)

    @field_validator("cliente_telefono")
    @classmethod
    def _telefono(cls, valor):
        return v.telefono(valor)

    @field_validator("fecha")
    @classmethod
    def _fecha(cls, valor):
        return v.fecha_no_futura(valor)

    @field_validator("fecha_entrega")
    @classmethod
    def _entrega(cls, valor):
        return v.fecha_no_pasada(valor)


class PedidoUpdate(BaseModel):
    cliente_nombre: str | None = Field(default=None, min_length=2, max_length=80)
    cliente_telefono: str | None = Field(default=None, max_length=30)
    cliente_direccion: str | None = Field(default=None, max_length=255)
    fecha_entrega: datetime | None = None
    prioridad: Prioridad | None = None
    notas: str | None = Field(default=None, max_length=500)
    # Si viene, reemplaza todos los ítems del pedido.
    items: list[ItemCreate] | None = Field(default=None, min_length=1)

    @field_validator("cliente_nombre")
    @classmethod
    def _cliente(cls, valor):
        return None if valor is None else v.nombre_item(valor, 80)

    @field_validator("cliente_telefono")
    @classmethod
    def _telefono(cls, valor):
        return v.telefono(valor)

    @field_validator("fecha_entrega")
    @classmethod
    def _entrega(cls, valor):
        return v.fecha_no_pasada(valor)


class PedidoCambioEstado(BaseModel):
    estado: EstadoPedido
    nota: str | None = Field(default=None, max_length=500)


class PedidoEventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    estado: str
    nota: str | None = None
    usuario_nombre: str | None = None
    created_at: datetime


class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    numero: int
    codigo: str = ""
    cliente_nombre: str
    cliente_telefono: str | None = None
    cliente_direccion: str | None = None
    fecha: datetime
    fecha_entrega: datetime | None = None
    prioridad: str
    estado: str
    total: Decimal
    notas: str | None = None
    items: list[ItemOut]
    eventos: list[PedidoEventoOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
