import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.imagenes import services

router = APIRouter(prefix="/imagenes", tags=["Imágenes"])


@router.get("/{imagen_id}")
def ver_imagen(imagen_id: uuid.UUID, db: Session = Depends(get_db)):
    """PÚBLICA (sin sesión): un `<img>` no manda el token. Son fotos de la carta
    y logos; el id es un UUID aleatorio. Una imagen nunca cambia (reemplazarla
    crea otra con otro id), así que se cachea para siempre."""
    imagen = services.obtener_publica(db, imagen_id)
    return Response(
        content=imagen.contenido,
        media_type=imagen.tipo,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
