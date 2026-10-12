import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core import validaciones as v

Unidad = Literal["kg", "g", "L", "ml", "unidad"]


class InsumoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    unidad: Unidad
    grupo: str | None = Field(default=None, max_length=40)
    minimo: Decimal = Decimal("0")
    costo_unitario: Decimal = Decimal("0")

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 100)

    @field_validator("grupo")
    @classmethod
    def _grupo(cls, valor):
        return None if valor in (None, "") else v.nombre_carta(valor, 40)

    @field_validator("minimo")
    @classmethod
    def _minimo(cls, valor):
        return v.cantidad_decimal(valor, permitir_cero=True)

    @field_validator("costo_unitario")
    @classmethod
    def _costo(cls, valor):
        return v.costo(valor)


class InsumoCreate(InsumoBase):
    """La existencia NO se escribe: nace en 0 y solo la mueven los
    movimientos. Si el insumo ya está en la bodega al crearlo, va en
    `existencia_inicial` y queda como un movimiento "inicial" con trazabilidad."""
    existencia_inicial: Decimal = Decimal("0")

    @field_validator("existencia_inicial")
    @classmethod
    def _inicial(cls, valor):
        return v.cantidad_decimal(valor, permitir_cero=True)


class InsumoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    unidad: Unidad | None = None
    grupo: str | None = Field(default=None, max_length=40)
    minimo: Decimal | None = None
    costo_unitario: Decimal | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_carta(valor, 100)

    @field_validator("grupo")
    @classmethod
    def _grupo(cls, valor):
        return None if valor in (None, "") else v.nombre_carta(valor, 40)

    @field_validator("minimo")
    @classmethod
    def _minimo(cls, valor):
        return None if valor is None else v.cantidad_decimal(valor, permitir_cero=True)

    @field_validator("costo_unitario")
    @classmethod
    def _costo(cls, valor):
        return None if valor is None else v.costo(valor)


class InsumoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    unidad: str
    grupo: str | None = None
    existencia: Decimal
    minimo: Decimal
    # Costos: None para quien no puede ver costos (permiso costos.ver).
    costo_unitario: Decimal | None = None
    costo_total: Decimal | None = None
    bajo_minimo: bool = False
    activo: bool
    platos_count: int = 0
    proveedores: list[dict] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    insumo_id: uuid.UUID
    insumo_nombre: str | None = None
    unidad: str | None = None
    tipo: str
    cantidad: Decimal
    existencia_resultante: Decimal
    costo_unitario: Decimal | None = None
    valor: Decimal | None = None
    documento_tipo: str | None = None
    documento_id: uuid.UUID | None = None
    documento_codigo: str | None = None
    motivo: str | None = None
    usuario_nombre: str | None = None
    created_at: datetime


class CambioEstado(BaseModel):
    activo: bool


# ---------- Merma ----------
MotivoMerma = Literal["vencido", "danado", "derramado", "preparacion", "otro"]


class MermaCreate(BaseModel):
    """Salida que no es venta: vencido, dañado, derramado, mal preparado."""
    cantidad: Decimal
    unidad: Unidad
    motivo: MotivoMerma
    detalle: str | None = Field(default=None, max_length=200, validate_default=True)

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return v.cantidad_decimal(valor)

    @field_validator("detalle")
    @classmethod
    def _detalle(cls, valor, info):
        texto = " ".join((valor or "").split()) or None
        if info.data.get("motivo") == "otro" and not texto:
            raise ValueError("Cuenta qué pasó: con el motivo «Otro» el detalle es obligatorio")
        return texto


# ---------- Conteo físico ----------
class ConteoLinea(BaseModel):
    insumo_id: uuid.UUID
    contado: Decimal

    @field_validator("contado")
    @classmethod
    def _contado(cls, valor):
        return v.cantidad_decimal(valor, permitir_cero=True)


class ConteoCreate(BaseModel):
    motivo: str | None = Field(default=None, max_length=200)
    lineas: list[ConteoLinea] = Field(min_length=1, max_length=500)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, valor):
        return " ".join((valor or "").split()) or None


class ConteoItemOut(BaseModel):
    insumo_id: uuid.UUID
    insumo_nombre: str
    unidad: str
    sistema: Decimal
    contado: Decimal
    diferencia: Decimal
    valor: Decimal | None = None


class ConteoOut(BaseModel):
    id: uuid.UUID
    numero: int
    codigo: str
    motivo: str | None = None
    usuario_nombre: str | None = None
    lineas: int
    con_diferencia: int
    valor_diferencia: Decimal | None = None
    created_at: datetime
    items: list[ConteoItemOut] = []
