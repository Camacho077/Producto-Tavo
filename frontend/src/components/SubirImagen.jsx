import { useId, useRef, useState } from "react";
import { ImagePlus, Trash2 } from "lucide-react";

import { Button, ModalConfirmar } from "@/components/ui";
import { useAviso } from "@/context/AvisoContext";
import { api } from "@/lib/api";
import { mensajeDeError } from "@/lib/errores";
import { errorArchivoImagen, urlImagen } from "@/lib/imagenes";

/**
 * Subir o quitar UNA imagen (foto de un plato, logo del restaurante).
 *
 * Es el embudo de esta escritura, como `useGuardarPantalla` lo es de crear y
 * editar: la alerta verde o roja (con la causa del backend) se emite aquí.
 * El archivo se revisa ANTES de subirlo (tipo y peso, mismos topes que el
 * backend) y se manda crudo con su Content-Type; el servidor lo recorta, lo
 * comprime a WebP y responde el registro actualizado (`onCambio(datos)`).
 * Quitar la imagen pasa por `ModalConfirmar`.
 *
 * `forma`: "cuadrada" (platos) o "ancha" (logos).
 */
export default function SubirImagen({
  imagenId,
  urlSubir,
  urlQuitar,
  onCambio,
  etiqueta = "Imagen",
  ayuda = "JPG, PNG o WebP de hasta 5 MB.",
  forma = "cuadrada",
  textoAlt = "",
  mensajeExito = "Imagen actualizada",
  mensajeQuitada = "Imagen quitada",
  deshabilitado = false,
}) {
  const id = useId();
  const entrada = useRef(null);
  const { exito, error } = useAviso();
  const [subiendo, setSubiendo] = useState(false);
  const [confirmarQuitar, setConfirmarQuitar] = useState(false);
  const [problema, setProblema] = useState(null);

  async function alElegir(e) {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    const invalido = errorArchivoImagen(archivo);
    if (invalido) {
      setProblema(invalido);
      error(invalido);
      return;
    }
    setProblema(null);
    setSubiendo(true);
    try {
      const { data } = await api.put(urlSubir, archivo, { headers: { "Content-Type": archivo.type } });
      onCambio?.(data);
      exito(mensajeExito);
    } catch (err) {
      const texto = mensajeDeError(err, "subir la imagen");
      setProblema(texto);
      error(texto);
    } finally {
      setSubiendo(false);
    }
  }

  const url = urlImagen(imagenId);
  return (
    <div className="campo">
      <span className="campo__etiqueta" id={`${id}-etiqueta`}>
        {etiqueta}
      </span>
      <div className="subir-imagen">
        <div className={`subir-imagen__vista subir-imagen__vista--${forma}`}>
          {url ? <img src={url} alt={textoAlt} /> : <ImagePlus size={22} aria-hidden="true" />}
        </div>
        <div className="subir-imagen__acciones">
          <input
            ref={entrada}
            id={id}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={alElegir}
            aria-labelledby={`${id}-etiqueta`}
            aria-describedby={`${id}-ayuda`}
            disabled={deshabilitado || subiendo}
          />
          <Button variante="secundario" tamano="sm" cargando={subiendo} disabled={deshabilitado} onClick={() => entrada.current?.click()}>
            <ImagePlus size={14} aria-hidden="true" /> {url ? "Cambiar imagen" : "Subir imagen"}
          </Button>
          {url && urlQuitar && (
            <Button variante="terciario" tamano="sm" disabled={deshabilitado || subiendo} onClick={() => setConfirmarQuitar(true)}>
              <Trash2 size={14} aria-hidden="true" /> Quitar
            </Button>
          )}
          <span className={problema ? "campo__error" : "campo__ayuda"} id={`${id}-ayuda`} role={problema ? "alert" : undefined}>
            {problema ?? ayuda}
          </span>
        </div>
      </div>

      <ModalConfirmar
        abierto={confirmarQuitar}
        onCerrar={() => setConfirmarQuitar(false)}
        destructivo
        titulo={`Quitar ${etiqueta.toLowerCase()}`}
        textoConfirmar="Quitar"
        mensaje="La imagen se borra del sistema. Puedes subir otra cuando quieras."
        accion="quitar la imagen"
        mensajeExito={mensajeQuitada}
        onConfirmar={async () => {
          const { data } = await api.delete(urlQuitar);
          onCambio?.(data);
        }}
      />
    </div>
  );
}
