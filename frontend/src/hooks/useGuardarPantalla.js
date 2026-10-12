import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAviso } from "@/context/AvisoContext";
import { mensajeDeError } from "@/lib/errores";

/**
 * Envío de una pantalla de crear/editar: valida con useFormulario, llama a
 * `fn(datos)`, y si todo sale bien vuelve a `volver` con la alerta verde
 * `mensaje`.
 *
 * Es el embudo único de crear y editar, así que si falla emite la alerta
 * roja con la causa concreta que devolvió el backend. El mismo texto queda
 * además en `errorGeneral`, al pie del formulario, para que siga a la vista
 * cuando la alerta se cierre sola.
 *
 * `accion` ("guardar el producto") solo se usa si el error no trae mensaje
 * propio (por ejemplo, si el servidor no respondió).
 */
export function useGuardarPantalla(f, { volver, mensaje, accion }) {
  const navigate = useNavigate();
  const { exito, error } = useAviso();
  const [guardando, setGuardando] = useState(false);
  const [errorGeneral, setErrorGeneral] = useState(null);

  async function guardar(e, fn) {
    e?.preventDefault?.();
    setErrorGeneral(null);
    setGuardando(true);
    try {
      const ok = await f.enviar(fn);
      if (ok) {
        exito(mensaje);
        navigate(volver);
      }
    } catch (err) {
      const texto = mensajeDeError(err, accion);
      setErrorGeneral(texto);
      error(texto);
    } finally {
      setGuardando(false);
    }
  }

  return { guardando, errorGeneral, guardar };
}
