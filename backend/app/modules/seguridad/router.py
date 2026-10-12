import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.core import mensajes
from app.core.catalogo_permisos import ACCIONES, CATALOGO, ROLES_DE_EJEMPLO, frase_permiso, permisos_de_rol
from app.core.consultas import obtener_del_tenant
from app.core.legal import VERSIONES as VERSIONES_LEGALES
from app.core.errors import AuthError, ConflictError, ForbiddenError, NotFoundError
from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.permisos import es_administrador, permisos_efectivos, tenant_con_permiso, usuario_con_permiso
from app.db.models import Tenant
from app.db.session import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.modules.seguridad import models, schemas

router = APIRouter(prefix="/seguridad", tags=["Seguridad"])


# ---------- Auth ----------
@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == payload.email).first()
    if not usuario or not verify_password(payload.password, usuario.hashed_password):
        raise AuthError("Credenciales inválidas")
    if not usuario.activo:
        raise ForbiddenError("Usuario inactivo")

    duracion = timedelta(days=settings.ACCESS_TOKEN_RECORDARME_DIAS) if payload.recordarme else None
    token = create_access_token(
        data={"sub": str(usuario.id), "tenant_id": str(usuario.tenant_id)},
        expires_delta=duracion,
    )
    return schemas.TokenResponse(access_token=token)


@router.post("/registro", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def registro(payload: schemas.RegistroRequest, db: Session = Depends(get_db)):
    """
    Alta inicial self-service: crea el Tenant, su rol Administrador (acceso
    total), los roles de ejemplo Cajero y Bodega, y el primer usuario, en una
    sola transacción — si algo falla (ej. el correo ya existe), no queda nada
    a medias. Devuelve un token igual que /login para que el frontend pueda
    loguear automáticamente tras registrarse.
    """
    tenant = Tenant(nombre_empresa=payload.nombre_empresa)
    db.add(tenant)

    try:
        db.flush()  # asigna tenant.id sin cerrar la transacción todavía

        rol_admin = models.Rol(
            tenant_id=tenant.id, nombre="Administrador", descripcion="Acceso total", es_administrador=True
        )
        db.add(rol_admin)
        for nombre, (descripcion, permisos) in ROLES_DE_EJEMPLO.items():
            db.add(models.Rol(tenant_id=tenant.id, nombre=nombre, descripcion=descripcion, permisos=permisos))
        db.flush()

        usuario = models.Usuario(
            tenant_id=tenant.id,
            nombre_completo="Administrador",
            email=payload.email,
            hashed_password=hash_password(payload.password),
            rol_id=rol_admin.id,
        )
        db.add(usuario)
        db.flush()

        # Prueba de la autorización: documento, versión vigente y fecha/hora.
        for documento, version in VERSIONES_LEGALES.items():
            db.add(
                models.AceptacionLegal(
                    tenant_id=tenant.id, usuario_id=usuario.id, email=usuario.email, documento=documento, version=version
                )
            )

        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Ya existe una cuenta registrada con ese correo electrónico")

    token = create_access_token(data={"sub": str(usuario.id), "tenant_id": str(tenant.id)})
    return schemas.TokenResponse(access_token=token)


@router.get("/me", response_model=schemas.MeResponse)
def obtener_sesion_actual(
    usuario: models.Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    """Sesión actual. No exige permisos: todo usuario activo puede saber
    quién es y qué puede hacer."""
    tenant = db.query(Tenant).filter(Tenant.id == usuario.tenant_id).first()
    if tenant is None:
        raise NotFoundError("La empresa de tu usuario ya no existe: vuelve a iniciar sesión.")
    return schemas.MeResponse(
        usuario=_serializar_usuario(usuario),
        tenant=tenant,
        permisos=permisos_efectivos(usuario),
        es_administrador=es_administrador(usuario),
    )


# ---------- Helpers ----------
def _serializar_usuario(u: models.Usuario) -> dict:
    return {
        "id": u.id,
        "nombre_completo": u.nombre_completo,
        "email": u.email,
        "activo": u.activo,
        "rol_id": u.rol_id,
        "rol_nombre": u.rol.nombre if u.rol else None,
        "rol_es_administrador": bool(u.rol and u.rol.es_administrador),
        "created_at": u.created_at,
    }


def _serializar_rol(r: models.Rol, usuarios_count: int = 0) -> dict:
    return {
        "id": r.id,
        "nombre": r.nombre,
        "descripcion": r.descripcion,
        # El administrador muestra lo que de verdad tiene: todo.
        "permisos": permisos_de_rol(bool(r.es_administrador), r.permisos),
        "es_administrador": bool(r.es_administrador),
        "usuarios_count": usuarios_count,
        "created_at": r.created_at,
    }


def _obtener_usuario_o_404(db: Session, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> models.Usuario:
    return obtener_del_tenant(db, models.Usuario, tenant_id, usuario_id, "El usuario indicado")


def _obtener_rol_o_404(db: Session, tenant_id: uuid.UUID, rol_id: uuid.UUID) -> models.Rol:
    return obtener_del_tenant(db, models.Rol, tenant_id, rol_id, "El rol indicado")


def _conteo_usuarios_por_rol(db: Session, tenant_id: uuid.UUID) -> dict:
    filas = (
        db.query(models.Usuario.rol_id, func.count(models.Usuario.id))
        .filter(models.Usuario.tenant_id == tenant_id)
        .group_by(models.Usuario.rol_id)
        .all()
    )
    return {rol_id: total for rol_id, total in filas}


def _administradores_activos(db: Session, tenant_id: uuid.UUID) -> int:
    return (
        db.query(func.count(models.Usuario.id))
        .join(models.Rol, models.Usuario.rol_id == models.Rol.id)
        .filter(models.Usuario.tenant_id == tenant_id, models.Usuario.activo.is_(True), models.Rol.es_administrador.is_(True))
        .scalar()
    )


# ---------- Reglas contra la escalada de privilegios ----------
# Tener "usuarios: editar" o "roles: editar" no debe servir para darse más
# poder del que el administrador concedió. Estas reglas lo impiden.
def _exigir_admin_para_tocar_admin(actor: models.Usuario, objetivo: models.Usuario) -> None:
    if objetivo.rol and objetivo.rol.es_administrador and not es_administrador(actor):
        raise ForbiddenError("Solo un administrador puede modificar a un usuario con rol Administrador.")


def _exigir_admin_para_asignar(actor: models.Usuario, rol: models.Rol) -> None:
    if rol.es_administrador and not es_administrador(actor):
        raise ForbiddenError("Solo un administrador puede asignar el rol Administrador.")


def _no_dejar_sin_administradores(db: Session, tenant_id: uuid.UUID, objetivo: models.Usuario) -> None:
    """Quitarle el acceso al ÚLTIMO administrador activo dejaría a la empresa
    sin nadie que pueda gestionar usuarios y roles."""
    if objetivo.activo and objetivo.rol and objetivo.rol.es_administrador and _administradores_activos(db, tenant_id) <= 1:
        raise ConflictError(
            f"{objetivo.nombre_completo} es el único administrador activo de la empresa. "
            "Asigna el rol Administrador a otro usuario antes de hacerlo."
        )


def _no_conceder_mas_de_lo_propio(actor: models.Usuario, permisos: dict) -> None:
    if es_administrador(actor):
        return
    propios = permisos_efectivos(actor)
    ajenos = [
        frase_permiso(modulo, accion)
        for modulo, acciones in (permisos or {}).items()
        for accion in acciones
        if accion not in propios.get(modulo, [])
    ]
    if ajenos:
        raise ForbiddenError(
            "No puedes conceder permisos que tu rol no tiene: " + "; ".join(ajenos) + ". "
            "Pídele a un administrador que lo haga."
        )


# ---------- Catálogo de permisos ----------
@router.get("/permisos")
def catalogo_permisos(_: uuid.UUID = Depends(tenant_con_permiso("roles", "ver"))):
    """Módulos y acciones disponibles para armar la matriz de permisos de un
    rol. Cada módulo trae solo las acciones que existen para él."""
    return {
        "modulos": [
            {"clave": clave, "nombre": nombre, "acciones": list(acciones)}
            for clave, (nombre, _, acciones) in CATALOGO.items()
        ],
        "acciones": [{"clave": clave, "nombre": nombre} for clave, nombre in ACCIONES.items()],
    }


# Columnas de la exportación a CSV (`?formato=csv`, app/core/exportar.py).
# Nunca la contraseña: el esquema de salida no la tiene.
COLUMNAS_USUARIOS = [
    ("Nombre", campo("nombre_completo")),
    ("Correo", campo("email")),
    ("Rol", campo("rol_nombre")),
    ("Estado", lambda f: "Activo" if f.get("activo") else "Inactivo"),
    ("Creado", campo("created_at")),
]


def _permisos_legibles(fila: dict) -> str:
    if fila.get("es_administrador"):
        return "Todos"
    return " | ".join(
        f"{CATALOGO[m][0]}: {', '.join(ACCIONES[a].lower() for a in acciones)}"
        for m, acciones in (fila.get("permisos") or {}).items()
        if m in CATALOGO
    )


COLUMNAS_ROLES = [
    ("Nombre", campo("nombre")),
    ("Descripción", campo("descripcion")),
    ("Administrador", campo("es_administrador")),
    ("Usuarios", campo("usuarios_count")),
    ("Permisos", _permisos_legibles),
]


# ---------- Usuarios ----------
@router.get("/usuarios", response_model=Pagina[schemas.UsuarioOut])
def listar_usuarios(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("usuarios", "ver")),
):
    query = db.query(models.Usuario).filter(models.Usuario.tenant_id == tenant_id)
    if activo is not None:
        query = query.filter(models.Usuario.activo == activo)
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Usuario.nombre_completo, models.Usuario.email),
        orden=models.Usuario.nombre_completo,
    )
    pagina["items"] = [_serializar_usuario(u) for u in pagina["items"]]
    return responder(pagina, params, schemas.UsuarioOut, COLUMNAS_USUARIOS, "usuarios")


@router.get("/usuarios/{usuario_id}", response_model=schemas.UsuarioOut)
def obtener_usuario(
    usuario_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("usuarios", "ver")),
):
    return _serializar_usuario(_obtener_usuario_o_404(db, tenant_id, usuario_id))


@router.post("/usuarios", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    payload: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(usuario_con_permiso("usuarios", "crear")),
):
    tenant_id = actor.tenant_id
    rol = _obtener_rol_o_404(db, tenant_id, payload.rol_id)
    _exigir_admin_para_asignar(actor, rol)

    nuevo = models.Usuario(
        tenant_id=tenant_id,
        nombre_completo=payload.nombre_completo,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        rol_id=payload.rol_id,
    )
    db.add(nuevo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un usuario", "correo", payload.email))
    db.refresh(nuevo)
    return _serializar_usuario(nuevo)


@router.put("/usuarios/{usuario_id}", response_model=schemas.UsuarioOut)
def actualizar_usuario(
    usuario_id: uuid.UUID,
    payload: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(usuario_con_permiso("usuarios", "editar")),
):
    tenant_id = actor.tenant_id
    usuario = _obtener_usuario_o_404(db, tenant_id, usuario_id)
    _exigir_admin_para_tocar_admin(actor, usuario)
    datos = payload.model_dump(exclude_unset=True)
    password = datos.pop("password", None)
    nuevo_rol_id = datos.get("rol_id")
    if nuevo_rol_id is not None and nuevo_rol_id != usuario.rol_id:
        if usuario.id == actor.id:
            raise ConflictError("No puedes cambiar tu propio rol: pídele a otro administrador que lo haga.")
        nuevo_rol = _obtener_rol_o_404(db, tenant_id, nuevo_rol_id)
        _exigir_admin_para_asignar(actor, nuevo_rol)
        if not nuevo_rol.es_administrador:
            _no_dejar_sin_administradores(db, tenant_id, usuario)
    for campo, valor in datos.items():
        if valor is not None:
            setattr(usuario, campo, valor)
    if password:
        usuario.hashed_password = hash_password(password)
    email = usuario.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un usuario", "correo", email))
    db.refresh(usuario)
    return _serializar_usuario(usuario)


@router.patch("/usuarios/{usuario_id}/estado", response_model=schemas.UsuarioOut)
def cambiar_estado_usuario(
    usuario_id: uuid.UUID,
    payload: schemas.UsuarioCambioEstado,
    db: Session = Depends(get_db),
    actual: models.Usuario = Depends(usuario_con_permiso("usuarios", "cambiar_estado")),
):
    if usuario_id == actual.id and not payload.activo:
        raise ConflictError("No puedes desactivar tu propio usuario: te quedarías sin acceso al sistema.")
    usuario = _obtener_usuario_o_404(db, actual.tenant_id, usuario_id)
    _exigir_admin_para_tocar_admin(actual, usuario)
    if not payload.activo:
        _no_dejar_sin_administradores(db, actual.tenant_id, usuario)
    usuario.activo = payload.activo
    db.commit()
    db.refresh(usuario)
    return _serializar_usuario(usuario)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    usuario_id: uuid.UUID,
    db: Session = Depends(get_db),
    actual: models.Usuario = Depends(usuario_con_permiso("usuarios", "eliminar")),
):
    if usuario_id == actual.id:
        raise ConflictError("No puedes eliminar tu propio usuario: pide a otro administrador que lo haga.")
    usuario = _obtener_usuario_o_404(db, actual.tenant_id, usuario_id)
    _exigir_admin_para_tocar_admin(actual, usuario)
    _no_dejar_sin_administradores(db, actual.tenant_id, usuario)
    db.delete(usuario)
    db.commit()


# ---------- Roles ----------
@router.get("/roles", response_model=Pagina[schemas.RolOut])
def listar_roles(
    params: ParametrosPagina = Depends(),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("roles", "ver")),
):
    query = db.query(models.Rol).filter(models.Rol.tenant_id == tenant_id)
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Rol.nombre, models.Rol.descripcion),
        orden=models.Rol.nombre,
    )
    conteos = _conteo_usuarios_por_rol(db, tenant_id)
    pagina["items"] = [_serializar_rol(r, conteos.get(r.id, 0)) for r in pagina["items"]]
    return responder(pagina, params, schemas.RolOut, COLUMNAS_ROLES, "roles")


@router.get("/roles/{rol_id}", response_model=schemas.RolOut)
def obtener_rol(
    rol_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("roles", "ver")),
):
    rol = _obtener_rol_o_404(db, tenant_id, rol_id)
    return _serializar_rol(rol, _conteo_usuarios_por_rol(db, tenant_id).get(rol.id, 0))


@router.post("/roles", response_model=schemas.RolOut, status_code=status.HTTP_201_CREATED)
def crear_rol(
    payload: schemas.RolCreate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(usuario_con_permiso("roles", "crear")),
):
    _no_conceder_mas_de_lo_propio(actor, payload.permisos)
    nuevo = models.Rol(
        tenant_id=actor.tenant_id, nombre=payload.nombre, descripcion=payload.descripcion, permisos=payload.permisos
    )
    db.add(nuevo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un rol", "nombre", payload.nombre))
    db.refresh(nuevo)
    return _serializar_rol(nuevo)


@router.put("/roles/{rol_id}", response_model=schemas.RolOut)
def actualizar_rol(
    rol_id: uuid.UUID,
    payload: schemas.RolUpdate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(usuario_con_permiso("roles", "editar")),
):
    tenant_id = actor.tenant_id
    rol = _obtener_rol_o_404(db, tenant_id, rol_id)
    datos = payload.model_dump(exclude_unset=True)
    if rol.es_administrador:
        if not es_administrador(actor):
            raise ForbiddenError("Solo un administrador puede modificar el rol Administrador.")
        if datos.get("permisos") is not None:
            raise ConflictError("El rol Administrador tiene siempre acceso total: sus permisos no se editan.")
    elif not es_administrador(actor):
        if rol.id == actor.rol_id:
            raise ForbiddenError("No puedes editar los permisos de tu propio rol: pídele a un administrador que lo haga.")
        if datos.get("permisos") is not None:
            _no_conceder_mas_de_lo_propio(actor, datos["permisos"])
    for campo, valor in datos.items():
        if valor is not None or campo == "descripcion":
            setattr(rol, campo, valor)
    nombre = rol.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un rol", "nombre", nombre))
    db.refresh(rol)
    return _serializar_rol(rol, _conteo_usuarios_por_rol(db, tenant_id).get(rol.id, 0))


@router.delete("/roles/{rol_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_rol(
    rol_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("roles", "eliminar")),
):
    rol = _obtener_rol_o_404(db, tenant_id, rol_id)
    if rol.es_administrador:
        raise ConflictError("El rol Administrador no se puede eliminar: es el que garantiza que alguien pueda gestionar la empresa.")
    asociados = db.query(func.count(models.Usuario.id)).filter(models.Usuario.rol_id == rol.id).scalar()
    if asociados:
        raise ConflictError(
            mensajes.no_se_puede_eliminar(
                "el rol", rol.nombre, asociados, "usuario", "usuarios",
                "Reasígnalos a otro rol antes de eliminarlo.",
            )
        )
    db.delete(rol)
    db.commit()
