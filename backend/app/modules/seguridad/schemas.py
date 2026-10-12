import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.core import validaciones as v
from app.modules.ajustes.schemas import ConfiguracionRestaurante
from app.core.catalogo_permisos import validar_permisos as _validar_permisos

# El catálogo de módulos y acciones vive en app/core/catalogo_permisos.py; el
# frontend lo lee de GET /seguridad/permisos.


class RolBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    permisos: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_item(valor, 100)

    @field_validator("permisos")
    @classmethod
    def _permisos_validos(cls, v):
        return _validar_permisos(v)


class RolCreate(RolBase):
    pass


class RolUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    permisos: dict[str, list[str]] | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_item(valor, 100)

    @field_validator("permisos")
    @classmethod
    def _permisos_validos(cls, v):
        return None if v is None else _validar_permisos(v)


class RolOut(BaseModel):
    """Salida: NO hereda los validadores de entrada. Un rol guardado antes de
    una regla nueva (p. ej. un nombre con dígitos) debe poder LEERSE; si la
    salida re-validara como la entrada, el listado entero respondería 500."""

    model_config = ConfigDict(from_attributes=True)
    nombre: str
    descripcion: str | None = None
    permisos: dict[str, list[str]] = Field(default_factory=dict)
    id: uuid.UUID
    es_administrador: bool = False
    usuarios_count: int = 0
    created_at: datetime | None = None


class UsuarioBase(BaseModel):
    nombre_completo: str = Field(min_length=2, max_length=80)
    email: EmailStr

    @field_validator("nombre_completo")
    @classmethod
    def _nombre(cls, valor):
        return v.nombre_persona(valor)

    @field_validator("email")
    @classmethod
    def _email(cls, valor):
        return v.email_normalizado(valor)


class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=8, max_length=72)
    rol_id: uuid.UUID


class UsuarioUpdate(BaseModel):
    nombre_completo: str | None = Field(default=None, min_length=2, max_length=80)
    email: EmailStr | None = None
    # Solo si se quiere cambiar la contraseña.
    password: str | None = Field(default=None, min_length=8, max_length=72)
    rol_id: uuid.UUID | None = None

    @field_validator("nombre_completo")
    @classmethod
    def _nombre(cls, valor):
        return None if valor is None else v.nombre_persona(valor)

    @field_validator("email")
    @classmethod
    def _email(cls, valor):
        return None if valor is None else v.email_normalizado(valor)


class UsuarioCambioEstado(BaseModel):
    activo: bool


class UsuarioOut(BaseModel):
    """Salida sin los validadores de entrada (mismo motivo que RolOut)."""

    model_config = ConfigDict(from_attributes=True)
    nombre_completo: str
    email: str
    id: uuid.UUID
    activo: bool
    rol_id: uuid.UUID
    rol_nombre: str | None = None
    rol_es_administrador: bool = False
    created_at: datetime | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    # "Recordarme": alarga la sesión de 8 horas a 30 días (ver config).
    recordarme: bool = False


class RegistroRequest(BaseModel):
    """Alta inicial de una empresa (self-service): crea el Tenant, su rol
    Administrador y el primer usuario, todo en una sola transacción."""

    nombre_empresa: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    # Autorización expresa (Ley 1581 de 2012, art. 9): la casilla del
    # registro, desmarcada por defecto. Sin ella no se crea la cuenta; con
    # ella se guarda qué versión se aceptó y cuándo (AceptacionLegal).
    # validate_default: si el campo NO viene, también se rechaza (un cliente
    # viejo no puede saltarse la aceptación omitiéndolo).
    acepta_condiciones: bool = Field(default=False, validate_default=True)

    @field_validator("acepta_condiciones")
    @classmethod
    def _debe_aceptar(cls, valor: bool) -> bool:
        if valor is not True:
            raise ValueError(
                "Para crear la cuenta debes aceptar la Política de tratamiento de datos "
                "y los Términos y condiciones"
            )
        return valor


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre_empresa: str
    plan: str
    theme_config: dict
    modulos_activos: list
    # Datos del negocio y configuración operativa (2026-10-12): la comanda,
    # la factura y la toma de pedidos los necesitan aunque el rol no pueda
    # VER Ajustes (un mesero no edita la configuración, pero la usa).
    nit: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    telefono: str | None = None
    correo: str | None = None
    logo_id: uuid.UUID | None = None
    configuracion: ConfiguracionRestaurante | None = None


class MeResponse(BaseModel):
    usuario: UsuarioOut
    tenant: TenantOut
    # Permisos EFECTIVOS del usuario ({modulo: [acciones]}): el frontend los
    # usa para ocultar lo que el rol no permite. La verificación real la hace
    # cada endpoint (app/core/permisos.py).
    permisos: dict[str, list[str]] = Field(default_factory=dict)
    es_administrador: bool = False
