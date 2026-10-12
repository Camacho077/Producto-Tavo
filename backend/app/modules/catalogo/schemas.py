import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core import validaciones as v
from app.modules.inventario.schemas import Unidad

MERMA_MAX = Decimal("90")
MSG_MERMA = "La merma debe ser un porcentaje entre 0 y 90 con máximo 2 decimales"
MSG_DIAS = "Los días van de 0 (lunes) a 6 (domingo), sin repetir"


# ---------- Categoría ----------
class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    orden: int = 0

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 100)

    @field_validator("orden")
    @classmethod
    def _orden(cls, valor):
        return v.entero(valor, 0, 999)


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    orden: int | None = None
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_carta(valor, 100)

    @field_validator("orden")
    @classmethod
    def _orden(cls, valor):
        return None if valor is None else v.entero(valor, 0, 999)


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    descripcion: str | None = None
    orden: int = 0
    activo: bool
    productos_count: int = 0
    created_at: datetime | None = None


class CambioEstado(BaseModel):
    activo: bool


class CambioAgotado(BaseModel):
    agotado: bool


# ---------- Receta, modificadores y componentes ----------
class RecetaItemIn(BaseModel):
    insumo_id: uuid.UUID
    cantidad: Decimal
    unidad: Unidad
    merma_porcentaje: Decimal = Decimal("0")

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return v.cantidad_decimal(valor)

    @field_validator("merma_porcentaje")
    @classmethod
    def _merma(cls, valor):
        if valor is None or valor < 0 or valor > MERMA_MAX or valor != valor.quantize(Decimal("0.01")):
            raise ValueError(MSG_MERMA)
        return valor.quantize(Decimal("0.01"))


class ModificadorIn(BaseModel):
    """`id` para conservar el mismo modificador al editar (las órdenes
    guardan una copia, pero el id sirve para los reportes)."""
    id: uuid.UUID | None = None
    tipo: Literal["sin", "extra"]
    nombre: str = Field(min_length=2, max_length=60)
    precio: Decimal = Decimal("0")
    insumo_id: uuid.UUID | None = None
    cantidad: Decimal | None = None
    unidad: Unidad | None = None
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 60)

    @field_validator("precio")
    @classmethod
    def _precio(cls, valor, info):
        valor = v.precio(valor, permitir_cero=True)
        if info.data.get("tipo") == "sin" and valor != 0:
            raise ValueError("Un «sin…» es gratis: su precio debe ser 0")
        return valor

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return None if valor is None else v.cantidad_decimal(valor)

    @model_validator(mode="after")
    def _insumo(self):
        if self.tipo == "extra" and self.insumo_id and (self.cantidad is None or self.unidad is None):
            raise ValueError(f"El extra «{self.nombre}» lleva insumo: indica cuánto (cantidad y unidad)")
        if self.tipo == "sin":
            self.cantidad = None
            self.unidad = None
        if not self.insumo_id:
            self.cantidad = None
            self.unidad = None
        return self


class ComboItemIn(BaseModel):
    producto_id: uuid.UUID
    cantidad: int = 1

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return v.entero(valor, 1, 20)


def _dias(valor):
    if valor is None:
        return None
    if len(set(valor)) != len(valor) or any(d < 0 or d > 6 for d in valor):
        raise ValueError(MSG_DIAS)
    return sorted(valor) or None


# ---------- Producto (plato o combo) ----------
class ProductoCampos(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    sku: str | None = Field(default=None, max_length=50)
    descripcion: str | None = Field(default=None, max_length=500)
    precio: Decimal
    categoria_id: uuid.UUID | None = None
    va_a_cocina: bool = True
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    dias_semana: list[int] | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 100)

    @field_validator("sku")
    @classmethod
    def _sku(cls, valor):
        return None if valor in (None, "") else v.sku(valor)

    @field_validator("precio")
    @classmethod
    def _precio(cls, valor):
        return v.precio(valor)

    @field_validator("dias_semana")
    @classmethod
    def _dias(cls, valor):
        return _dias(valor)

    @model_validator(mode="after")
    def _vigencia(self):
        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta < self.vigente_desde:
            raise ValueError("La vigencia termina antes de empezar: revisa las fechas")
        return self


class ProductoCreate(ProductoCampos):
    tipo: Literal["plato", "combo"] = "plato"
    receta: list[RecetaItemIn] = Field(default_factory=list, max_length=40)
    modificadores: list[ModificadorIn] = Field(default_factory=list, max_length=30)
    componentes: list[ComboItemIn] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def _por_tipo(self):
        if self.tipo == "combo":
            if not self.componentes:
                raise ValueError("Un combo necesita al menos un plato")
            if self.receta or self.modificadores:
                raise ValueError("Un combo no lleva receta ni modificadores propios: los tiene cada plato")
        elif self.componentes:
            raise ValueError("Solo los combos llevan platos dentro")
        return self


class ProductoUpdate(BaseModel):
    """Todo opcional. `receta`, `modificadores` y `componentes` en None no se
    tocan; una lista (aunque vacía) REEMPLAZA la que había."""
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    sku: str | None = Field(default=None, max_length=50)
    descripcion: str | None = Field(default=None, max_length=500)
    precio: Decimal | None = None
    categoria_id: uuid.UUID | None = None
    va_a_cocina: bool | None = None
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    dias_semana: list[int] | None = None
    receta: list[RecetaItemIn] | None = Field(default=None, max_length=40)
    modificadores: list[ModificadorIn] | None = Field(default=None, max_length=30)
    componentes: list[ComboItemIn] | None = Field(default=None, max_length=15)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_carta(valor, 100)

    @field_validator("sku")
    @classmethod
    def _sku(cls, valor):
        return None if valor in (None, "") else v.sku(valor)

    @field_validator("precio")
    @classmethod
    def _precio(cls, valor):
        return None if valor is None else v.precio(valor)

    @field_validator("dias_semana")
    @classmethod
    def _dias(cls, valor):
        return _dias(valor)


class RecetaItemOut(BaseModel):
    id: uuid.UUID
    insumo_id: uuid.UUID
    insumo_nombre: str
    insumo_unidad: str
    cantidad: Decimal
    unidad: str
    merma_porcentaje: Decimal
    costo: Decimal | None = None


class ModificadorOut(BaseModel):
    id: uuid.UUID
    tipo: str
    nombre: str
    precio: Decimal
    insumo_id: uuid.UUID | None = None
    insumo_nombre: str | None = None
    cantidad: Decimal | None = None
    unidad: str | None = None
    activo: bool
    costo: Decimal | None = None


class ComponenteOut(BaseModel):
    producto_id: uuid.UUID
    producto_nombre: str
    cantidad: int
    va_a_cocina: bool
    precio: Decimal
    costo: Decimal | None = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    nombre: str
    sku: str | None = None
    descripcion: str | None = None
    precio: Decimal
    activo: bool
    categoria_id: uuid.UUID | None = None
    categoria_nombre: str | None = None
    imagen_id: uuid.UUID | None = None
    va_a_cocina: bool
    agotado_hoy: bool = False
    vigente: bool = True
    disponible: bool = True
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    dias_semana: list[int] | None = None
    receta: list[RecetaItemOut] = []
    modificadores: list[ModificadorOut] = []
    componentes: list[ComponenteOut] = []
    tiene_receta: bool = False
    # Costeo (None para quien no tiene costos.ver o si falta receta).
    costo: Decimal | None = None
    precio_neto: Decimal | None = None
    margen: Decimal | None = None
    porcentaje_costo: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
