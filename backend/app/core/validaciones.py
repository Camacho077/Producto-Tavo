"""
Reglas de validación de negocio compartidas por todos los schemas Pydantic.

El frontend replica exactamente estas reglas y mensajes en
frontend/src/lib/validaciones.js; si cambias algo aquí, cámbialo allá. La
validación del backend es la que manda: la del frontend es comodidad.
"""
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# ---------- Textos ----------
# Nombres de persona: letras (con tildes/ñ/ü), espacios y apóstrofes.
NOMBRE_PERSONA_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]+$")
# Nombres de producto/categoría/marca/rol/razón social: el mismo alfabeto que
# los de persona (letras, tildes, ñ, espacios y apóstrofe), sin dígitos ni
# símbolos. Decisión del usuario del 2026-09-27; el bloqueo al teclear del
# frontend (filtro "nombre") ya aplicaba esta regla.
NOMBRE_ITEM_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]+$")
# SKU: letras, números, guion y guion bajo.
SKU_RE = re.compile(r"^[A-Za-z0-9_-]+$")

MSG_NOMBRE_PERSONA = "Solo letras, espacios, tildes y apóstrofes (entre 2 y 80 caracteres)"
MSG_NOMBRE_ITEM = "Solo letras, espacios, tildes y apóstrofes; sin espacios al inicio o al final"
MSG_SKU = "Solo letras, números, guion y guion bajo (entre 2 y 50 caracteres)"

# ---------- Números ----------
STOCK_MAX = 1_000_000
CANTIDAD_MAX = 100_000
PRECIO_MAX = Decimal("999999999.99")
MSG_ENTERO = "Debe ser un número entero entre {minimo} y {maximo}"
MSG_PRECIO = "Debe ser un monto positivo con máximo 2 decimales (hasta $ 999.999.999,99)"
MSG_PORCENTAJE = "Debe ser un porcentaje entre 0 y 100"

# ---------- Contacto ----------
# Celular colombiano: 10 dígitos empezando por 3. Fijo: indicativo nacional
# 60 + indicativo de área + 7 dígitos (10 dígitos en total).
TELEFONO_RE = re.compile(r"^(3\d{9}|60\d{8})$")
MSG_TELEFONO = "Debe ser un celular de 10 dígitos que empiece por 3 o un fijo con indicativo (60 + 8 dígitos)"
MSG_EMAIL = "Debe ser un correo electrónico válido"

# ---------- Documentos (Colombia) ----------
TIPOS_DOCUMENTO = ("CC", "CE", "PA", "TI")
NOMBRES_DOCUMENTO = {
    "CC": "Cédula de ciudadanía",
    "CE": "Cédula de extranjería",
    "PA": "Pasaporte",
    "TI": "Tarjeta de identidad",
}
REGLAS_DOCUMENTO = {
    "CC": (re.compile(r"^\d{6,10}$"), "La cédula de ciudadanía tiene entre 6 y 10 dígitos"),
    "CE": (re.compile(r"^\d{6,7}$"), "La cédula de extranjería tiene entre 6 y 7 dígitos"),
    "PA": (re.compile(r"^[A-Z0-9]{6,12}$"), "El pasaporte tiene entre 6 y 12 letras o números"),
    "TI": (re.compile(r"^\d{10,11}$"), "La tarjeta de identidad tiene 10 u 11 dígitos"),
}
NIT_RE = re.compile(r"^(\d{6,10})-(\d)$")
MSG_NIT_FORMATO = "El NIT debe tener el formato 900123456-7 (número y dígito de verificación)"
MSG_NIT_DV = "El dígito de verificación del NIT no coincide: para {base} debería ser {dv}"

_PESOS_NIT = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def digito_verificacion_nit(base: str) -> int:
    """Algoritmo oficial de la DIAN: pesos de derecha a izquierda, módulo 11."""
    suma = sum(int(d) * p for d, p in zip(reversed(base), _PESOS_NIT))
    resto = suma % 11
    return resto if resto < 2 else 11 - resto


def validar_nit(valor: str) -> str:
    texto = (valor or "").strip().replace(".", "").replace(" ", "")
    m = NIT_RE.match(texto)
    if not m:
        raise ValueError(MSG_NIT_FORMATO)
    base, dv = m.group(1), int(m.group(2))
    esperado = digito_verificacion_nit(base)
    if dv != esperado:
        raise ValueError(MSG_NIT_DV.format(base=base, dv=esperado))
    return f"{base}-{dv}"


def validar_documento(tipo: str, numero: str) -> str:
    if tipo not in REGLAS_DOCUMENTO:
        raise ValueError("Tipo de documento desconocido")
    texto = (numero or "").strip().upper()
    patron, mensaje = REGLAS_DOCUMENTO[tipo]
    if not patron.match(texto):
        raise ValueError(mensaje)
    return texto


# ---------- Validadores reutilizables ----------
def nombre_persona(valor: str) -> str:
    texto = " ".join((valor or "").split())
    if not (2 <= len(texto) <= 80) or not NOMBRE_PERSONA_RE.match(texto):
        raise ValueError(MSG_NOMBRE_PERSONA)
    return texto


def nombre_item(valor: str, maximo: int = 100) -> str:
    texto = valor or ""
    if texto != texto.strip() or not (2 <= len(texto) <= maximo) or not NOMBRE_ITEM_RE.match(texto):
        raise ValueError(MSG_NOMBRE_ITEM)
    return texto


def sku(valor: str) -> str:
    texto = (valor or "").strip().upper()
    if not (2 <= len(texto) <= 50) or not SKU_RE.match(texto):
        raise ValueError(MSG_SKU)
    return texto


def telefono(valor: str | None) -> str | None:
    if valor is None or valor == "":
        return None
    digitos = re.sub(r"\D", "", valor)
    if not TELEFONO_RE.match(digitos):
        raise ValueError(MSG_TELEFONO)
    return digitos


def email_normalizado(valor: str) -> str:
    return valor.strip().lower()


def precio(valor: Decimal, permitir_cero: bool = False) -> Decimal:
    if valor is None:
        raise ValueError(MSG_PRECIO)
    if (valor <= 0 and not permitir_cero) or valor < 0 or valor > PRECIO_MAX:
        raise ValueError(MSG_PRECIO)
    if valor != valor.quantize(Decimal("0.01")):
        raise ValueError(MSG_PRECIO)
    return valor.quantize(Decimal("0.01"))


def entero(valor: int, minimo: int, maximo: int) -> int:
    if not isinstance(valor, int) or valor < minimo or valor > maximo:
        raise ValueError(MSG_ENTERO.format(minimo=minimo, maximo=maximo))
    return valor


def porcentaje(valor: Decimal) -> Decimal:
    if valor is None or valor < 0 or valor > 100 or valor != valor.quantize(Decimal("0.01")):
        raise ValueError(MSG_PORCENTAJE)
    return valor.quantize(Decimal("0.01"))


def _a_utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def fecha_no_futura(fecha: datetime) -> datetime:
    # 5 minutos de margen por desfase de reloj entre el navegador y el servidor.
    ahora = datetime.now(timezone.utc)
    if (_a_utc(fecha) - ahora).total_seconds() > 300:
        raise ValueError("La fecha no puede ser futura")
    return fecha


# "Hoy" es el día calendario del negocio (Colombia), no el de UTC: de 19:00 a
# 24:00 en Bogotá UTC ya va en el día siguiente. Colombia no tiene horario de
# verano, así que el desfase fijo es exacto y no depende de tzdata (Windows no
# lo trae). Espejo: ZONA_NEGOCIO en frontend/src/lib/validaciones.js.
ZONA_NEGOCIO = timezone(timedelta(hours=-5), "America/Bogota")


def fecha_no_pasada(fecha: datetime | None) -> datetime | None:
    if fecha is None:
        return None
    hoy = datetime.now(ZONA_NEGOCIO).date()
    if _a_utc(fecha).astimezone(ZONA_NEGOCIO).date() < hoy:
        raise ValueError("La fecha de entrega no puede ser anterior a hoy")
    return fecha
