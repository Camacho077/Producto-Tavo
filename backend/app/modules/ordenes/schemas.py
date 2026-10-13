import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core import validaciones as v

TipoOrden = Literal["local", "llevar", "domicilio"]
Origen = Literal["local", "llamada", "whatsapp"]


def _texto(valor: str | None) -> str | None:
    return " ".join((valor or "").split()) or None


class ItemPedido(BaseModel):
    producto_id: uuid.UUID
    cantidad: int = 1
    modificador_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    nota: str | None = Field(default=None, max_length=120)

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, valor):
        return v.entero(valor, 1, 99)

    @field_validator("nota")
    @classmethod
    def _nota(cls, valor):
        return _texto(valor)


class DatosOrden(BaseModel):
    """Encabezado de la orden: lo mismo al crearla y al editarla."""
    tipo: TipoOrden
    origen: Origen = "local"
    mesa_id: uuid.UUID | None = None
    cliente_nombre: str | None = Field(default=None, max_length=80)
    cliente_telefono: str | None = Field(default=None, max_length=20)
    cliente_direccion: str | None = Field(default=None, max_length=150)
    nota: str | None = Field(default=None, max_length=200)

    @field_validator("cliente_nombre")
    @classmethod
    def _cliente(cls, valor):
        return None if not _texto(valor) else v.nombre_persona(_texto(valor))

    @field_validator("cliente_telefono")
    @classmethod
    def _telefono(cls, valor):
        return v.telefono(valor)

    @field_validator("cliente_direccion", "nota")
    @classmethod
    def _limpiar(cls, valor):
        return _texto(valor)

    @model_validator(mode="after")
    def _segun_tipo(self):
        if self.tipo == "local" and not self.mesa_id:
            raise ValueError("Una orden en el local va con mesa: elige para qué mesa es")
        if self.tipo != "local":
            self.mesa_id = None
        if self.tipo == "domicilio":
            faltan = [n for n, val in (("la dirección", self.cliente_direccion), ("el teléfono", self.cliente_telefono)) if not val]
            if faltan:
                raise ValueError(f"Un domicilio necesita {' y '.join(faltan)} del cliente")
        else:
            self.cliente_direccion = None
        return self


class OrdenCreate(DatosOrden):
    items: list[ItemPedido] = Field(min_length=1, max_length=60)


class ItemsAgregar(BaseModel):
    items: list[ItemPedido] = Field(min_length=1, max_length=60)


class Motivo(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, valor):
        texto = _texto(valor)
        if not texto or len(texto) < 3:
            raise ValueError("Escribe el motivo (al menos 3 caracteres): queda en el historial y le llega a cocina")
        return texto


class AgotarProducto(BaseModel):
    producto_id: uuid.UUID


# ---------- Salida ----------
class ItemOut(BaseModel):
    id: uuid.UUID
    comanda_id: uuid.UUID
    comanda_numero: int
    producto_id: uuid.UUID
    nombre: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    costo_unitario: Decimal | None = None
    modificadores: list[dict] = []
    nota: str | None = None
    va_a_cocina: bool
    anulado: bool
    anulado_motivo: str | None = None
    venta_id: uuid.UUID | None = None  # None = por cobrar


class ComandaOut(BaseModel):
    id: uuid.UUID
    numero: int
    estado: str
    va_a_cocina: bool
    created_at: datetime
    tomada_en: datetime | None = None
    tomada_por: str | None = None
    lista_en: datetime | None = None
    lista_por: str | None = None
    entregada_en: datetime | None = None
    entregada_por: str | None = None


class EventoOut(BaseModel):
    id: uuid.UUID
    tipo: str
    nota: str | None = None
    usuario_nombre: str | None = None
    created_at: datetime


class OrdenOut(BaseModel):
    id: uuid.UUID
    jornada: date
    numero: int
    codigo: str
    tipo: str
    origen: str
    mesa_id: uuid.UUID | None = None
    mesa_nombre: str | None = None
    cliente_nombre: str | None = None
    cliente_telefono: str | None = None
    cliente_direccion: str | None = None
    nota: str | None = None
    estado: str
    # Estado de cocina de la orden abierta: el de su comanda más atrasada.
    estado_cocina: str | None = None
    total: Decimal
    mesero_nombre: str | None = None
    anulada_motivo: str | None = None
    platos: int = 0
    resumen: str = ""
    created_at: datetime
    cerrada_en: datetime | None = None
    items: list[ItemOut] = []
    comandas: list[ComandaOut] = []
    eventos: list[EventoOut] = []


class MesaEstado(BaseModel):
    id: uuid.UUID
    nombre: str
    zona_id: uuid.UUID | None = None
    zona_nombre: str | None = None
    puestos: int
    estado: Literal["libre", "ocupada", "por_cobrar"]
    ordenes: list[dict] = []
