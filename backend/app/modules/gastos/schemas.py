from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core import validaciones as v
from app.modules.ajustes.schemas import MedioPago

Categoria = Literal["arriendo", "servicios", "nomina", "gas", "aseo", "mantenimiento", "impuestos", "otros"]


class GastoIn(BaseModel):
    fecha: date
    categoria: Categoria
    descripcion: str = Field(min_length=3, max_length=150)
    valor: Decimal
    medio_pago: MedioPago = "efectivo"
    # Efectivo sacado de la caja abierta: se descuenta de su cuadre.
    de_caja: bool = False

    @field_validator("descripcion")
    @classmethod
    def _descripcion(cls, valor):
        texto = " ".join(valor.split())
        if len(texto) < 3:
            raise ValueError("Describe el gasto (al menos 3 caracteres)")
        return texto

    @field_validator("valor")
    @classmethod
    def _valor(cls, valor):
        return v.precio(valor)

    @field_validator("fecha")
    @classmethod
    def _fecha(cls, valor):
        hoy = datetime.now(v.ZONA_NEGOCIO).date()
        if valor > hoy:
            raise ValueError("La fecha del gasto no puede ser futura")
        return valor
