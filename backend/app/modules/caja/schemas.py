import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core import validaciones as v
from app.modules.ajustes.schemas import MedioPago

TipoDocumento = Literal["CC", "CE", "NIT", "PA", "TI"]


def _texto(valor: str | None) -> str | None:
    return " ".join((valor or "").split()) or None


def _monto(valor, permitir_cero=False) -> Decimal:
    return v.precio(Decimal(valor), permitir_cero=permitir_cero)


class AbrirCaja(BaseModel):
    base_inicial: Decimal = Decimal("0")

    @field_validator("base_inicial")
    @classmethod
    def _base(cls, valor):
        return _monto(valor, permitir_cero=True)


class CerrarCaja(BaseModel):
    """Lo que se contó por medio de pago. Un medio que no venga cuenta 0."""
    contado: dict[MedioPago, Decimal] = Field(default_factory=dict)
    motivo_diferencia: str | None = Field(default=None, max_length=250)

    @field_validator("contado")
    @classmethod
    def _contado(cls, valor):
        return {m: _monto(x, permitir_cero=True) for m, x in valor.items()}

    @field_validator("motivo_diferencia")
    @classmethod
    def _motivo(cls, valor):
        return _texto(valor)


class ItemCobro(BaseModel):
    orden_item_id: uuid.UUID
    # Menos que la cantidad del plato = dividir la cuenta dentro de la línea
    # (2 sándwiches, cada quien paga uno).
    cantidad: int | None = None

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return None if valor is None else v.entero(valor, 1, 99)


class PagoIn(BaseModel):
    medio: MedioPago
    monto: Decimal
    recibido: Decimal | None = None

    @field_validator("monto")
    @classmethod
    def _monto(cls, valor):
        return _monto(valor)

    @field_validator("recibido")
    @classmethod
    def _recibido(cls, valor):
        return None if valor is None else _monto(valor)

    @model_validator(mode="after")
    def _efectivo(self):
        if self.recibido is not None:
            if self.medio != "efectivo":
                raise ValueError("Solo el efectivo tiene «recibido» y devueltas")
            if self.recibido < self.monto:
                raise ValueError("Lo recibido en efectivo no alcanza para el monto de ese pago")
        return self


class ClienteComprobante(BaseModel):
    nombre: str | None = Field(default=None, max_length=80)
    documento_tipo: TipoDocumento | None = None
    documento: str | None = Field(default=None, max_length=20)
    correo: EmailStr | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if not _texto(valor) else v.nombre_persona(_texto(valor))

    @field_validator("correo", mode="before")
    @classmethod
    def _correo(cls, valor):
        return None if valor in (None, "") else v.email_normalizado(valor)

    @model_validator(mode="after")
    def _documento(self):
        doc = _texto(self.documento)
        if not doc:
            self.documento, self.documento_tipo = None, None
            return self
        if not self.documento_tipo:
            raise ValueError("Indica el tipo de documento del cliente")
        self.documento = v.validar_nit(doc) if self.documento_tipo == "NIT" else v.validar_documento(self.documento_tipo, doc)
        return self


class CobroCreate(BaseModel):
    orden_id: uuid.UUID
    # None: todo lo que falta por cobrar de la orden.
    items: list[ItemCobro] | None = Field(default=None, max_length=60)
    propina: Decimal = Decimal("0")
    pagos: list[PagoIn] = Field(min_length=1, max_length=6)
    cliente: ClienteComprobante | None = None

    @field_validator("propina")
    @classmethod
    def _propina(cls, valor):
        return _monto(valor, permitir_cero=True)


class Motivo(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, valor):
        texto = _texto(valor)
        if not texto or len(texto) < 3:
            raise ValueError("Escribe el motivo (al menos 3 caracteres): queda en el historial")
        return texto
