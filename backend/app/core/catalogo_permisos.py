"""
CATÁLOGO DE PERMISOS POR ROL — la única lista de módulos y acciones.

Cada rol guarda en `Rol.permisos` un diccionario `{modulo: [acciones]}` y cada
endpoint de negocio exige UNO de estos pares (ver `app/core/permisos.py`).
El frontend no tiene su propia lista: arma la matriz de roles con
GET /seguridad/permisos y decide qué mostrar con los permisos efectivos que
devuelve GET /seguridad/me.

Cada módulo trae SOLO las acciones que existen para él: compras y ventas no se
editan (se anulan), los pedidos no se eliminan, el dashboard solo se ve.

Módulo sin dependencias a propósito: lo importan los esquemas, las
dependencias de FastAPI y los tests sin riesgo de import circular.
"""

# modulo -> (nombre visible, objeto en las frases de error, acciones permitidas)
CATALOGO: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "dashboard": ("Dashboard", "el dashboard", ("ver",)),
    "compras": ("Compras", "compras", ("ver", "crear", "cambiar_estado", "anular")),
    "productos": ("Productos", "productos", ("ver", "crear", "editar", "cambiar_estado", "eliminar")),
    "categorias": ("Categorías", "categorías", ("ver", "crear", "editar", "cambiar_estado", "eliminar")),
    "marcas": ("Marcas", "marcas", ("ver", "crear", "editar", "cambiar_estado", "eliminar")),
    "proveedores": ("Proveedores", "proveedores", ("ver", "crear", "editar", "cambiar_estado", "eliminar")),
    "ventas": ("Ventas", "ventas", ("ver", "crear", "cambiar_estado", "anular")),
    "pedidos": ("Pedidos", "pedidos", ("ver", "crear", "editar", "cambiar_estado")),
    "usuarios": ("Usuarios", "usuarios", ("ver", "crear", "editar", "cambiar_estado", "eliminar")),
    "roles": ("Roles", "roles", ("ver", "crear", "editar", "eliminar")),
    "ia": ("Sugerencias IA", "las sugerencias de IA", ("ver",)),
}

# PLANES (2026-10-01). Cada módulo pertenece a un GRUPO del catálogo comercial
# (el mismo `key` de primer nivel de frontend/src/config/modules.js, que es el
# que se activa por empresa en `Tenant.modulos_activos`), y cada grupo tiene
# un plan mínimo. Antes el plan solo se aplicaba en el sidebar: una empresa en
# Básico podía llamar a /compras o a la IA directamente por la API.
# `tests/test_planes.py` exige que este mapa coincida con modules.js.
ORDEN_PLANES: tuple[str, ...] = ("basico", "estandar", "pro_ia")
NOMBRE_PLANES: dict[str, str] = {"basico": "Básico", "estandar": "Estándar", "pro_ia": "Pro + IA"}
GRUPO_DE_MODULO: dict[str, str] = {
    "dashboard": "dashboard",
    "compras": "compras",
    "productos": "compras",
    "categorias": "compras",
    "marcas": "compras",
    "proveedores": "compras",
    "ventas": "ventas",
    "pedidos": "ventas",
    "usuarios": "seguridad",
    "roles": "seguridad",
    "ia": "ia",
}
PLAN_MINIMO_DE_GRUPO: dict[str, str] = {
    "dashboard": "basico",
    "seguridad": "basico",
    "compras": "estandar",
    "ventas": "estandar",
    "ia": "pro_ia",
}
NOMBRE_GRUPO: dict[str, str] = {
    "dashboard": "el Dashboard",
    "seguridad": "Seguridad",
    "compras": "Compras",
    "ventas": "Ventas",
    "ia": "las Sugerencias IA",
}


def _nivel(plan: str | None) -> int:
    return ORDEN_PLANES.index(plan) if plan in ORDEN_PLANES else 0


def modulo_contratado(plan: str | None, modulos_activos: list | None, modulo: str) -> bool:
    """¿La empresa tiene este módulo, por su plan o como add-on contratado?"""
    grupo = GRUPO_DE_MODULO[modulo]
    if grupo in (modulos_activos or []):
        return True
    return _nivel(plan) >= _nivel(PLAN_MINIMO_DE_GRUPO[grupo])


def mensaje_no_contratado(plan: str | None, modulo: str) -> str:
    grupo = GRUPO_DE_MODULO[modulo]
    minimo = NOMBRE_PLANES[PLAN_MINIMO_DE_GRUPO[grupo]]
    actual = NOMBRE_PLANES.get(plan or "", plan or "sin plan")
    return (
        f"El plan {actual} de tu empresa no incluye {NOMBRE_GRUPO[grupo]}. "
        f"Está disponible desde el plan {minimo} o como módulo adicional: escríbele a JS Company para activarlo."
    )


# Orden y nombre visible de cada acción (columnas de la matriz de permisos).
ACCIONES: dict[str, str] = {
    "ver": "Ver",
    "crear": "Crear",
    "editar": "Editar",
    "cambiar_estado": "Cambiar estado",
    "anular": "Anular",
    "eliminar": "Eliminar",
}

# Verbo de cada acción para los mensajes de error ("… para anular compras").
_VERBOS = {
    "ver": "ver",
    "crear": "crear",
    "editar": "editar",
    "cambiar_estado": "cambiar el estado de",
    "anular": "anular",
    "eliminar": "eliminar",
}


def acciones_de(modulo: str) -> tuple[str, ...]:
    return CATALOGO[modulo][2]


def todos_los_permisos() -> dict[str, list[str]]:
    """Lo que tiene un Administrador: cada acción de cada módulo."""
    return {modulo: list(acciones) for modulo, (_, _, acciones) in CATALOGO.items()}


def frase_permiso(modulo: str, accion: str) -> str:
    """'cambiar el estado de productos', 'ver el dashboard', 'anular compras'."""
    return f"{_VERBOS[accion]} {CATALOGO[modulo][1]}"


def validar_permisos(permisos: dict | None) -> dict[str, list[str]]:
    """Limpia y valida un diccionario de permisos recibido del cliente: solo
    módulos del catálogo, solo acciones que existen para ESE módulo, sin
    duplicados y en el orden del catálogo. Los módulos sin acciones se omiten."""
    limpio: dict[str, list[str]] = {}
    for modulo, acciones in (permisos or {}).items():
        if modulo not in CATALOGO:
            raise ValueError(f"Módulo desconocido en permisos: '{modulo}'")
        if not isinstance(acciones, list):
            raise ValueError(f"Las acciones del módulo '{modulo}' deben ser una lista")
        validas = acciones_de(modulo)
        invalidas = [a for a in acciones if a not in validas]
        if invalidas:
            raise ValueError(
                f"El módulo '{CATALOGO[modulo][0]}' no tiene la acción: {', '.join(invalidas)}. "
                f"Acciones posibles: {', '.join(validas)}."
            )
        if acciones:
            limpio[modulo] = [a for a in validas if a in set(acciones)]
    return limpio


def permisos_de_rol(es_administrador: bool, permisos: dict | None) -> dict[str, list[str]]:
    """Permisos EFECTIVOS: todo para el administrador; para el resto, solo lo
    que sigue existiendo en el catálogo (un permiso viejo o mal escrito en la
    base de datos no concede nada)."""
    if es_administrador:
        return todos_los_permisos()
    efectivos: dict[str, list[str]] = {}
    for modulo, acciones in (permisos or {}).items():
        if modulo in CATALOGO and isinstance(acciones, list):
            validas = [a for a in acciones_de(modulo) if a in set(acciones)]
            if validas:
                efectivos[modulo] = validas
    return efectivos


# Roles de ejemplo que se crean con cada empresa nueva (y en las existentes,
# por la migración de permisos). Permisos limitados y realistas; el
# administrador puede ajustarlos desde Seguridad → Roles.
ROLES_DE_EJEMPLO: dict[str, tuple[str, dict[str, list[str]]]] = {
    "Cajero": (
        "Registra ventas y atiende pedidos. No ve compras, costos ni márgenes.",
        {
            "ventas": ["ver", "crear", "cambiar_estado"],
            "pedidos": ["ver", "crear", "editar", "cambiar_estado"],
            "productos": ["ver"],
            "categorias": ["ver"],
            "marcas": ["ver"],
        },
    ),
    "Bodega": (
        "Recibe compras y mantiene el catálogo. No vende ni ve el dashboard.",
        {
            "compras": ["ver", "crear", "cambiar_estado"],
            "productos": ["ver", "crear", "editar", "cambiar_estado"],
            "categorias": ["ver", "crear", "editar"],
            "marcas": ["ver", "crear", "editar"],
            "proveedores": ["ver"],
            "pedidos": ["ver"],
        },
    ),
}
