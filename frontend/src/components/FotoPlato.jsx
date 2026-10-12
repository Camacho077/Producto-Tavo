import Imagen3d from "@/components/Imagen3d";
import { urlImagen } from "@/lib/imagenes";

/**
 * Foto de un plato o combo. Si el restaurante subió una, se muestra (WebP
 * cuadrado de 640 px servido por el backend); si no, la imagen POR DEFECTO es
 * el render 3D monocromo del producto (siempre el mismo para el mismo plato),
 * así la carta nunca muestra huecos ni un estilo nuevo.
 */
export default function FotoPlato({ producto, tamano = 44, className = "", alt = "" }) {
  if (producto?.imagen_id) {
    return (
      <span className={`imagen-3d__marco ${className}`} style={{ width: tamano, height: tamano }}>
        <img
          src={urlImagen(producto.imagen_id)}
          alt={alt}
          width={tamano}
          height={tamano}
          className="foto-plato"
          loading="lazy"
          draggable={false}
        />
      </span>
    );
  }
  return <Imagen3d clave={producto?.id ?? producto?.nombre} tamano={tamano} className={className} alt={alt} />;
}
