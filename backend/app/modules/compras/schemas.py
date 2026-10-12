import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

from app.core import validaciones as v
from app.modules.inventario.schemas import Unidad


# ---------- Proveedor ----------
TipoPersona = Literal["natural", "juridica"]
TipoDocumento = Literal["CC", "CE", "PA", "TI"]


class ProveedorBase(BaseModel):
    tipo_persona: TipoPersona = "juridica"
    # Persona natural
    tipo_documento: TipoDocumento | None = None
    numero_documento: str | None = Field(default=None, max_length=20)
    nombres: str | None = Field(default=None, max_length=80)
    apellidos: str | None = Field(default=None, max_length=80)
    # Persona jurídica
    nit: str | None = Field(default=None, max_length=20)
    razon_social: str | None = Field(default=None, max_length=150)
    representante_nombre: str | None = Field(default=None, max_length=80)
    representante_documento: str | None = Field(default=None, max_length=20)
    # Contacto (ambos)
    telefono: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    direccion: str | None = Field(default=None, max_length=255)
    # Insumos que surte (relación muchos a muchos).
    insumo_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, valor):
        return v.telefono(valor)

    @field_validator("email")
    @classmethod
    def _email(cls, valor):
        return None if valor is None else v.email_normalizado(valor)

    @field_validator("nombres", "apellidos", "representante_nombre")
    @classmethod
    def _persona(cls, valor):
        return None if valor in (None, "") else v.nombre_persona(valor)

    @field_validator("razon_social")
    @classmethod
    def _razon(cls, valor):
        return None if valor in (None, "") else v.nombre_item(valor, 150)

    # Validaciones POR CAMPO según el tipo de persona (con field_validator y
    # info.data), para que el 422 traiga `campo` y el frontend pinte el
    # mensaje bajo el campo correcto. `tipo_persona` va declarado primero y
    # por eso ya está en info.data cuando se validan los demás.
    @field_validator("tipo_documento")
    @classmethod
    def _tipo_documento(cls, valor, info):
        if info.data.get("tipo_persona") == "natural" and not valor:
            raise ValueError("Selecciona el tipo de documento")
        return valor

    @field_validator("numero_documento")
    @classmethod
    def _numero_documento(cls, valor, info):
        if info.data.get("tipo_persona") != "natural":
            return valor
        tipo = info.data.get("tipo_documento")
        if not tipo:
            return valor
        if not (valor or "").strip():
            raise ValueError("Este campo es obligatorio")
        return v.validar_documento(tipo, valor)

    @field_validator("nombres", "apellidos")
    @classmethod
    def _nombres_natural(cls, valor, info):
        if info.data.get("tipo_persona") == "natural" and not valor:
            raise ValueError("Este campo es obligatorio")
        return valor

    @field_validator("nit")
    @classmethod
    def _nit(cls, valor, info):
        if info.data.get("tipo_persona") == "natural":
            return valor
        return v.validar_nit(valor or "")

    @field_validator("razon_social", "representante_nombre")
    @classmethod
    def _obligatorios_juridica(cls, valor, info):
        if info.data.get("tipo_persona") != "natural" and not valor:
            raise ValueError("Este campo es obligatorio")
        return valor

    @field_validator("representante_documento")
    @classmethod
    def _representante_documento(cls, valor, info):
        if info.data.get("tipo_persona") == "natural" or not valor:
            return None if not valor else valor
        return v.validar_documento("CC", valor)

    @model_validator(mode="after")
    def _limpiar_por_tipo(self):
        """Los campos que no aplican al tipo se limpian de verdad (sin
        valores fantasma)."""
        if self.tipo_persona == "natural":
            self.nit = None
            self.razon_social = None
            self.representante_nombre = None
            self.representante_documento = None
        else:
            self.tipo_documento = None
            self.numero_documento = None
            self.nombres = None
            self.apellidos = None
        return self

    @property
    def nombre_derivado(self) -> str:
        if self.tipo_persona == "natural":
            return f"{self.nombres} {self.apellidos}".strip()
        return self.razon_social or ""


class ProveedorCreate(ProveedorBase):
    pass


class ProveedorUpdate(ProveedorBase):
    activo: bool | None = None


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    tipo_persona: str
    tipo_documento: str | None = None
    numero_documento: str | None = None
    nombres: str | None = None
    apellidos: str | None = None
    nit: str | None = None
    razon_social: str | None = None
    representante_nombre: str | None = None
    representante_documento: str | None = None
    telefono: str | None = None
    email: str | None = None
    direccion: str | None = None
    activo: bool
    compras_count: int = 0
    insumos: list["InsumoResumen"] = []
    created_at: datetime | None = None


class InsumoResumen(BaseModel):
    id: uuid.UUID
    nombre: str
    unidad: str
    existencia: Decimal = Decimal("0")


class CambioEstado(BaseModel):
    activo: bool


# ---------- Compra de insumos ----------
class CompraItemCreate(BaseModel):
    """Cantidad y precio en la unidad en que se COMPRÓ (kg aunque el insumo
    se lleve en g); el backend convierte al confirmar."""
    insumo_id: uuid.UUID
    cantidad: Decimal
    unidad: Unidad
    precio_unitario: Decimal

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return v.cantidad_decimal(valor)

    @field_validator("precio_unitario")
    @classmethod
    def _precio(cls, valor):
        return v.precio(valor, permitir_cero=True)


class CompraItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    insumo_id: uuid.UUID
    insumo_nombre: str | None = None
    insumo_unidad: str | None = None
    cantidad: Decimal
    unidad: str
    precio_unitario: Decimal
    subtotal: Decimal = Decimal("0")


class CompraCreate(BaseModel):
    proveedor_id: uuid.UUID
    fecha: datetime
    notas: str | None = Field(default=None, max_length=500)
    # True: la compra queda confirmada de una vez y las existencias suben.
    # False: queda pendiente hasta que se confirme.
    confirmar: bool = False
    items: list[CompraItemCreate] = Field(min_length=1, max_length=60)

    @field_validator("fecha")
    @classmethod
    def _fecha(cls, valor):
        return v.fecha_no_futura(valor)


class CompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    numero: int
    codigo: str = ""
    proveedor_id: uuid.UUID
    proveedor_nombre: str | None = None
    fecha: datetime
    estado: str
    total: Decimal
    notas: str | None = None
    items: list[CompraItemOut]
    created_at: datetime | None = None
