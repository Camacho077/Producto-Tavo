"""
IMÁGENES SUBIDAS (2026-10-12): validación, recorte y compresión en el SERVIDOR.

El navegador sube el archivo tal cual (cuerpo crudo con su Content-Type; sin
multipart, para no sumar dependencias). Aquí se decide si sirve:

1. Tipo: JPEG, PNG o WebP. Se comprueba el formato REAL con Pillow, no solo
   el Content-Type que declara el navegador (un .exe renombrado a .jpg no
   pasa).
2. Peso: máximo 5 MB de entrada.
3. Tamaño en píxeles: máximo 40 megapíxeles (protege contra las "bombas de
   descompresión": un PNG pequeño que se expande a gigas en memoria).

Y luego se normaliza: se respeta la orientación EXIF (las fotos del celular
llegan "acostadas"), los platos se recortan al CUADRADO central y se reducen
a 640 px; los logos se encogen dentro de 600 × 300 sin recortar. Todo sale en
WebP calidad 80: una foto de 4 MB del celular queda en ~40 KB.
"""
import io
import uuid

from fastapi import Request
from PIL import Image as PilImage, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.modules.imagenes.models import Imagen

TIPOS_PERMITIDOS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELES = 40_000_000
LADO_PLATO = 640
CAJA_LOGO = (600, 300)
CALIDAD_WEBP = 80


class ImagenInvalida(AppError):
    status_code = 422
    detail = "La imagen no es válida."


class ImagenDemasiadoGrande(AppError):
    status_code = 413
    detail = "La imagen pesa demasiado."


async def leer_imagen_subida(request: Request) -> tuple[bytes, str]:
    """Dependencia: cuerpo crudo de la petición + su Content-Type, con tope de
    peso ANTES de leer todo (si el navegador declara el tamaño)."""
    tipo = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > MAX_BYTES:
        raise ImagenDemasiadoGrande(_mensaje_peso(int(declarado)))
    contenido = await request.body()
    return contenido, tipo


def _mensaje_peso(bytes_: int) -> str:
    return (
        f"La imagen pesa {bytes_ / 1024 / 1024:.1f} MB y el máximo es {MAX_BYTES // 1024 // 1024} MB. "
        "Elige una foto más liviana o tómala con menos resolución."
    )


def procesar(contenido: bytes, tipo: str, uso: str) -> tuple[bytes, int, int]:
    """Valida y normaliza. Devuelve (webp, ancho, alto)."""
    if not contenido:
        raise ImagenInvalida("No llegó ninguna imagen: elige un archivo JPG, PNG o WebP.")
    if tipo not in TIPOS_PERMITIDOS:
        raise ImagenInvalida(
            f"El archivo es de tipo «{tipo or 'desconocido'}» y solo se aceptan imágenes JPG, PNG o WebP."
        )
    if len(contenido) > MAX_BYTES:
        raise ImagenDemasiadoGrande(_mensaje_peso(len(contenido)))
    try:
        with PilImage.open(io.BytesIO(contenido)) as abierta:
            formato = abierta.format
            ancho, alto = abierta.size
            if ancho * alto > MAX_PIXELES:
                raise ImagenInvalida(
                    f"La imagen mide {ancho} × {alto} píxeles y el máximo es {MAX_PIXELES // 1_000_000} megapíxeles."
                )
            if formato != TIPOS_PERMITIDOS[tipo]:
                raise ImagenInvalida(
                    f"El archivo dice ser {tipo} pero su contenido es {formato or 'otra cosa'}: súbelo de nuevo desde la galería."
                )
            imagen = ImageOps.exif_transpose(abierta)
            imagen.load()
    except UnidentifiedImageError:
        raise ImagenInvalida("El archivo no es una imagen que se pueda abrir (¿está dañado?). Prueba con otra foto.")
    except PilImage.DecompressionBombError:
        raise ImagenInvalida(f"La imagen es demasiado grande en píxeles (máximo {MAX_PIXELES // 1_000_000} megapíxeles).")

    imagen = imagen.convert("RGBA" if imagen.mode in ("RGBA", "LA", "P") else "RGB")
    if uso == "plato":
        lado = min(imagen.size)
        izquierda = (imagen.width - lado) // 2
        arriba = (imagen.height - lado) // 2
        imagen = imagen.crop((izquierda, arriba, izquierda + lado, arriba + lado))
        if lado > LADO_PLATO:
            imagen = imagen.resize((LADO_PLATO, LADO_PLATO), PilImage.LANCZOS)
    else:
        imagen.thumbnail(CAJA_LOGO, PilImage.LANCZOS)

    salida = io.BytesIO()
    imagen.save(salida, "WEBP", quality=CALIDAD_WEBP, method=6)
    return salida.getvalue(), imagen.width, imagen.height


def guardar(db: Session, tenant_id: uuid.UUID, contenido: bytes, tipo: str, uso: str, anterior_id: uuid.UUID | None = None) -> Imagen:
    """Procesa y guarda la imagen; si reemplaza a otra, borra la anterior."""
    webp, ancho, alto = procesar(contenido, tipo, uso)
    imagen = Imagen(tenant_id=tenant_id, uso=uso, contenido=webp, ancho=ancho, alto=alto, bytes=len(webp))
    db.add(imagen)
    if anterior_id:
        borrar(db, tenant_id, anterior_id)
    db.flush()
    return imagen


def borrar(db: Session, tenant_id: uuid.UUID, imagen_id: uuid.UUID | None) -> None:
    if imagen_id is None:
        return
    db.query(Imagen).filter(Imagen.id == imagen_id, Imagen.tenant_id == tenant_id).delete(synchronize_session=False)


def obtener_publica(db: Session, imagen_id: uuid.UUID) -> Imagen:
    imagen = db.get(Imagen, imagen_id)
    if imagen is None:
        raise NotFoundError("La imagen indicada no existe o fue reemplazada.")
    return imagen
