import cajaArena from "@/assets/3d/caja-arena.svg";
import cajaPizarra from "@/assets/3d/caja-pizarra.svg";
import capsulaArena from "@/assets/3d/capsula-arena.svg";
import conoPizarra from "@/assets/3d/cono-pizarra.svg";
import cuboArena from "@/assets/3d/cubo-arena.svg";
import cuboPizarra from "@/assets/3d/cubo-pizarra.svg";
import esferaArena from "@/assets/3d/esfera-arena.svg";
import esferaPizarra from "@/assets/3d/esfera-pizarra.svg";
import monedaArena from "@/assets/3d/moneda-arena.svg";
import toroPizarra from "@/assets/3d/toro-pizarra.svg";

/**
 * Renders 3D locales (src/assets/3d, CC0) como marcador de posición de la
 * imagen de producto. Cada producto recibe siempre la misma forma: se elige
 * por un hash estable de su nombre/SKU, así no cambia entre recargas.
 */
export const RENDERS = {
  esfera: esferaArena,
  "esfera-pizarra": esferaPizarra,
  cubo: cuboArena,
  "cubo-pizarra": cuboPizarra,
  toro: toroPizarra,
  capsula: capsulaArena,
  cono: conoPizarra,
  caja: cajaArena,
  "caja-pizarra": cajaPizarra,
  moneda: monedaArena,
};

const ROTACION = ["esfera", "cubo", "toro", "capsula", "cono", "esfera-pizarra", "cubo-pizarra", "caja"];

function hash(texto = "") {
  let h = 0;
  for (let i = 0; i < texto.length; i++) h = (h * 31 + texto.charCodeAt(i)) >>> 0;
  return h;
}

export function renderPara(clave) {
  return RENDERS[ROTACION[hash(String(clave)) % ROTACION.length]];
}

export default function Imagen3d({ clave, forma, tamano = 40, alt = "", className = "" }) {
  const src = forma ? RENDERS[forma] : renderPara(clave);
  return (
    <span className={`imagen-3d__marco ${className}`} style={{ width: tamano, height: tamano }}>
      <img src={src} alt={alt} width={tamano} height={tamano} className="imagen-3d" loading="lazy" draggable={false} />
    </span>
  );
}
