import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

from app.core import validaciones as v


# ---------- Catálogos simples (Categoría / Marca) ----------
class CatalogoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_item(valor, 100)


class CategoriaCreate(CatalogoBase):
    pass


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_item(valor, 100)


class CategoriaOut(CatalogoBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    activo: bool
    productos_count: int = 0
    created_at: datetime | None = None


class MarcaCreate(CatalogoBase):
    pass


class MarcaUpdate(CategoriaUpdate):
    pass


class MarcaOut(CategoriaOut):
    pass


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
    # Productos que surte (relación muchos a muchos).
    producto_ids: list[uuid.UUID] = Field(default_factory=list)

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
    productos: list["ProductoResumen"] = []
    created_at: datetime | None = None


class ProductoResumen(BaseModel):
    id: uuid.UUID
    nombre: str
    sku: str
    stock: int = 0


class ProveedorResumen(BaseModel):
    id: uuid.UUID
    nombre: str


# ---------- Producto ----------
class ProductoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    sku: str = Field(min_length=2, max_length=50)
    descripcion: str | None = Field(default=None, max_length=500)
    precio: Decimal
    precio_compra: Decimal | None = None
    stock_minimo: int = 0
    categoria_id: uuid.UUID | None = None
    marca_id: uuid.UUID | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_item(valor, 150)

    @field_validator("sku")
    @classmethod
    def _sku(cls, valor):
        return v.sku(valor)

    @field_validator("precio")
    @classmethod
    def _precio(cls, valor):
        return v.precio(valor)

    @field_validator("precio_compra")
    @classmethod
    def _precio_compra(cls, valor):
        return None if valor is None else v.precio(valor, permitir_cero=True)

    @field_validator("stock_minimo")
    @classmethod
    def _stock_minimo(cls, valor):
        return v.entero(valor, 0, v.STOCK_MAX)


class ProductoCreate(ProductoBase):
    """El stock no se escribe: nace en 0 y solo lo mueven compras y ventas."""


class ProductoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    sku: str | None = Field(default=None, min_length=2, max_length=50)
    descripcion: str | None = Field(default=None, max_length=500)
    precio: Decimal | None = None
    precio_compra: Decimal | None = None
    stock_minimo: int | None = None
    categoria_id: uuid.UUID | None = None
    marca_id: uuid.UUID | None = None
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_item(valor, 150)

    @field_validator("sku")
    @classmethod
    def _sku(cls, valor):
        return None if valor is None else v.sku(valor)

    @field_validator("precio")
    @classmethod
    def _precio(cls, valor):
        return None if valor is None else v.precio(valor)

    @field_validator("precio_compra")
    @classmethod
    def _precio_compra(cls, valor):
        return None if valor is None else v.precio(valor, permitir_cero=True)

    @field_validator("stock_minimo")
    @classmethod
    def _stock_minimo(cls, valor):
        return None if valor is None else v.entero(valor, 0, v.STOCK_MAX)


class CambioEstado(BaseModel):
    activo: bool


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    sku: str
    descripcion: str | None = None
    precio: Decimal
    precio_compra: Decimal | None = None
    stock_minimo: int = 0
    categoria_id: uuid.UUID | None = None
    marca_id: uuid.UUID | None = None
    stock: int
    activo: bool
    categoria_nombre: str | None = None
    marca_nombre: str | None = None
    proveedores: list[ProveedorResumen] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    cantidad: int
    stock_resultante: int
    documento_tipo: str
    documento_id: uuid.UUID
    documento_codigo: str
    usuario_nombre: str | None = None
    created_at: datetime


# ---------- Compra ----------
class CompraItemCreate(BaseModel):
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


class CompraItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    producto_id: uuid.UUID
    producto_nombre: str | None = None
    producto_sku: str | None = None
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal = Decimal("0")


class CompraCreate(BaseModel):
    proveedor_id: uuid.UUID
    fecha: datetime
    notas: str | None = Field(default=None, max_length=500)
    # True: la compra queda confirmada de una vez y el stock sube. False:
    # queda pendiente hasta que se confirme (comportamiento original).
    confirmar: bool = False
    items: list[CompraItemCreate] = Field(min_length=1)

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
