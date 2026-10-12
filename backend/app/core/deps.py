"""
Dependencias de autenticación para FastAPI. Resuelven el usuario y el
tenant_id SIEMPRE a partir del JWT — nunca de un parámetro de query o del
body que el cliente pueda manipular. Cualquier endpoint de negocio debe
depender de `get_current_tenant_id` (o `get_current_usuario` si necesita más
datos del usuario) para filtrar/asignar sus datos.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.seguridad.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/seguridad/login")


@dataclass
class TokenData:
    usuario_id: uuid.UUID
    tenant_id: uuid.UUID


def get_current_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        payload = decode_access_token(token)
        usuario_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])
    except (JWTError, KeyError, ValueError, TypeError):
        raise AuthError("Token inválido o expirado")
    return TokenData(usuario_id=usuario_id, tenant_id=tenant_id)


def get_current_usuario(
    token_data: TokenData = Depends(get_current_token_data),
    db: Session = Depends(get_db),
) -> Usuario:
    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == token_data.usuario_id, Usuario.tenant_id == token_data.tenant_id)
        .first()
    )
    if usuario is None:
        raise AuthError("Token inválido o expirado")
    if not usuario.activo:
        raise AuthError("Usuario inactivo")
    return usuario


def get_current_tenant_id(usuario: Usuario = Depends(get_current_usuario)) -> uuid.UUID:
    return usuario.tenant_id
