import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core import validaciones as v

# ---------------------------------------------------------------------------
# Catálogos fijos de la operación. El restaurante elige cuáles HABILITA; los
# valores posibles son del producto (el frontend los nombra con las mismas
# claves en src/config/restaurante.js).
# ---------------------------------------------------------------------------
TipoOrden = Literal["local", "llevar", "domicilio"]
OrigenOrden = Literal["local", "llamada", "whatsapp"]
MedioPago = Literal["efectivo", "transferencia", "nequi", "daviplata", "tarjeta"]
TIPOS_ORDEN: tuple[str, ...] = ("local", "llevar", "domicilio")
ORIGENES: tuple[str, ...] = ("local", "llamada", "whatsapp")
MEDIOS_PAGO: tuple[str, ...] = ("efectivo", "transferencia", "nequi", "daviplata", "tarjeta")

DIRECCION_RED_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}(:\d{2,5})?$")


def _sin_repetidos(lista: list, que: str) -> list:
    if len(set(lista)) != len(lista):
        raise ValueError(f"Hay {que} repetidos")
    return lista


class ImpuestoConsumo(BaseModel):
    """Impuesto nacional al consumo de restaurantes (8 % en Colombia).
    Si `incluido_en_precio`, la carta ya lo trae y la factura lo DESGLOSA; si
    no, se suma al subtotal. Confirmar con el contador del restaurante si es
    responsable (fase 6)."""
    aplica: bool = True
    tasa: Decimal = Decimal("8.00")
    incluido_en_precio: bool = True

    @field_validator("tasa")
    @classmethod
    def _tasa(cls, valor):
        return v.porcentaje(valor)


class Impresora(BaseModel):
    """Impresora térmica. `navegador`: imprime con el diálogo del navegador
    (CSS de 58/80 mm). `ip`: ESC/POS directo a IP:puerto, para cuando exista
    el conector (la interfaz de impresión del frontend ya está separada)."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    nombre: str = Field(min_length=2, max_length=40)
    uso: Literal["comanda", "factura", "ambos"] = "ambos"
    ancho_mm: Literal[58, 80] = 80
    conexion: Literal["navegador", "ip"] = "navegador"
    direccion: str | None = Field(default=None, max_length=30, validate_default=True)
    activa: bool = True

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 40)

    @field_validator("direccion")
    @classmethod
    def _direccion(cls, valor, info):
        if info.data.get("conexion") != "ip":
            return None
        if not valor or not DIRECCION_RED_RE.match(valor.strip()):
            raise ValueError("Escribe la dirección IP de la impresora, p. ej. 192.168.1.50:9100")
        return valor.strip()


class Jornada(BaseModel):
    """Horario del servicio. La JORNADA empieza a la hora de `inicio`: una
    orden de las 01:00 con inicio a las 06:00 cuenta en la jornada de ayer
    (así un servicio que pasa de medianoche no reinicia el consecutivo)."""
    inicio: str = "06:00"
    fin: str = "22:00"

    @field_validator("inicio", "fin")
    @classmethod
    def _hora(cls, valor):
        return v.hora(valor)

    @model_validator(mode="after")
    def _distintas(self):
        if self.inicio == self.fin:
            raise ValueError("La hora de inicio y la de cierre de la jornada no pueden ser iguales")
        return self


class ConfiguracionRestaurante(BaseModel):
    """Toda la configuración operativa de un restaurante, con sus valores por
    defecto: `Tenant.configuracion` siempre se LEE a través de este modelo, así
    un restaurante creado antes de que existiera un campo recibe su valor por
    defecto en vez de un KeyError."""
    tipos_orden: list[TipoOrden] = Field(default_factory=lambda: list(TIPOS_ORDEN), min_length=1)
    origenes: list[OrigenOrden] = Field(default_factory=lambda: list(ORIGENES), min_length=1)
    medios_pago: list[MedioPago] = Field(default_factory=lambda: list(MEDIOS_PAGO), min_length=1)
    impuesto_consumo: ImpuestoConsumo = Field(default_factory=ImpuestoConsumo)
    propina_sugerida: Decimal = Decimal("10.00")
    alerta_cocina_minutos: int = 15
    sonido_cocina: bool = True
    jornada: Jornada = Field(default_factory=Jornada)
    impresoras: list[Impresora] = Field(default_factory=list, max_length=10)
    # Por defecto NO se vende lo que no hay: si un insumo no alcanza, la orden
    # se rechaza con la causa ("quedan 200 g de queso…"). En True el
    # inventario puede quedar en negativo (útil mientras se carga la bodega
    # real) y el panel de avisos lo señala.
    vender_sin_existencias: bool = False

    @field_validator("tipos_orden")
    @classmethod
    def _tipos(cls, valor):
        return _sin_repetidos(valor, "tipos de orden")

    @field_validator("origenes")
    @classmethod
    def _origenes(cls, valor):
        return _sin_repetidos(valor, "orígenes")

    @field_validator("medios_pago")
    @classmethod
    def _medios(cls, valor):
        return _sin_repetidos(valor, "medios de pago")

    @field_validator("propina_sugerida")
    @classmethod
    def _propina(cls, valor):
        valor = v.porcentaje(valor)
        if valor > 30:
            raise ValueError("La propina sugerida no puede pasar del 30 %")
        return valor

    @field_validator("alerta_cocina_minutos")
    @classmethod
    def _alerta(cls, valor):
        return v.entero(valor, 1, 180)


def configuracion_de(tenant) -> ConfiguracionRestaurante:
    """Configuración vigente del tenant, con los valores por defecto de lo que
    no haya guardado. Si lo guardado ya no valida (un campo que cambió de
    reglas), se ignora ESE campo, no toda la configuración."""
    guardada = dict(tenant.configuracion or {})
    try:
        return ConfiguracionRestaurante.model_validate(guardada)
    except ValueError:
        limpia = {}
        for campo, valor in guardada.items():
            try:
                ConfiguracionRestaurante.model_validate({campo: valor})
                limpia[campo] = valor
            except ValueError:
                continue
        return ConfiguracionRestaurante.model_validate(limpia)


# ---------------------------------------------------------------------------
# Datos del negocio
# ---------------------------------------------------------------------------
class NegocioUpdate(BaseModel):
    nombre_empresa: str = Field(min_length=2, max_length=80)
    nit: str | None = Field(default=None, max_length=20)
    direccion: str | None = Field(default=None, max_length=150)
    ciudad: str | None = Field(default=None, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)
    correo: EmailStr | None = None

    @field_validator("nombre_empresa")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 80)

    @field_validator("nit")
    @classmethod
    def _nit(cls, valor):
        return None if valor in (None, "") else v.validar_nit(valor)

    @field_validator("direccion")
    @classmethod
    def _direccion(cls, valor):
        texto = " ".join((valor or "").split())
        return texto or None

    @field_validator("ciudad")
    @classmethod
    def _ciudad(cls, valor):
        return None if valor in (None, "") else v.nombre_persona(valor)

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, valor):
        return v.telefono(valor)

    @field_validator("correo", mode="before")
    @classmethod
    def _correo(cls, valor):
        return None if valor in (None, "") else v.email_normalizado(valor)


class NegocioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre_empresa: str
    nit: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    telefono: str | None = None
    correo: str | None = None
    logo_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Zonas y mesas
# ---------------------------------------------------------------------------
class ZonaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=40)
    orden: int = 0

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_carta(valor, 40)

    @field_validator("orden")
    @classmethod
    def _orden(cls, valor):
        return v.entero(valor, 0, 999)


class ZonaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=40)
    orden: int | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_carta(valor, 40)

    @field_validator("orden")
    @classmethod
    def _orden(cls, valor):
        return None if valor is None else v.entero(valor, 0, 999)


class ZonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    orden: int
    mesas_count: int = 0
    created_at: datetime | None = None


class MesaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=20)
    zona_id: uuid.UUID | None = None
    puestos: int = 4

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_mesa(valor)

    @field_validator("puestos")
    @classmethod
    def _puestos(cls, valor):
        return v.entero(valor, 1, 30)


class MesaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=20)
    zona_id: uuid.UUID | None = None
    puestos: int | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_mesa(valor)

    @field_validator("puestos")
    @classmethod
    def _puestos(cls, valor):
        return None if valor is None else v.entero(valor, 1, 30)


class MesaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    zona_id: uuid.UUID | None = None
    zona_nombre: str | None = None
    puestos: int
    activo: bool
    created_at: datetime | None = None


class CambioEstado(BaseModel):
    activo: bool
