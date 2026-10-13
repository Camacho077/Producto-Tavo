import { useCallback, useMemo, useRef, useState } from "react";

/**
 * Estado + validación de un formulario con un esquema Zod (objeto).
 *
 * Comportamiento acordado:
 *  - Valida al SALIR del campo (blur), no en cada tecla. Tras el primer
 *    intento de envío, los errores de todos los campos quedan visibles.
 *  - `props(campo)` entrega value/onChange/onBlur/error/required listos
 *    para <Input>, <Select> y <Textarea>.
 *  - `hayErrores` deshabilita el botón de guardar mientras haya errores
 *    visibles.
 *  - `enviar(fn)` valida todo; si falla, lleva el foco al primer campo
 *    inválido (por data-campo). Si `fn` lanza un 422 del backend, los
 *    mensajes se pintan bajo el campo correspondiente.
 */
export function useFormulario(esquema, inicial, { normalizadores = {} } = {}) {
  const [form, setFormEstado] = useState(inicial);
  const [formInicial, setFormInicial] = useState(inicial);
  const [tocados, setTocados] = useState({});
  const [enviado, setEnviado] = useState(false);
  const [erroresBackend, setErroresBackend] = useState({});
  const raiz = useRef(null);

  const resultado = useMemo(() => esquema.safeParse(form), [esquema, form]);
  const erroresZod = useMemo(() => {
    if (resultado.success) return {};
    const mapa = {};
    for (const issue of resultado.error.issues) {
      const clave = issue.path.join(".");
      if (!(clave in mapa)) mapa[clave] = issue.message;
    }
    return mapa;
  }, [resultado]);

  const errores = useMemo(() => ({ ...erroresZod, ...erroresBackend }), [erroresZod, erroresBackend]);

  const errorVisible = useCallback(
    (campo) => (enviado || tocados[campo] || campo in erroresBackend ? errores[campo] : undefined),
    [enviado, tocados, errores, erroresBackend]
  );
  const hayErrores = Object.keys(errores).some((campo) => errorVisible(campo));
  const sucio = JSON.stringify(form) !== JSON.stringify(formInicial);

  const reiniciar = useCallback((valores) => {
    setFormEstado(valores);
    setFormInicial(valores);
    setTocados({});
    setEnviado(false);
    setErroresBackend({});
  }, []);

  const setCampo = useCallback(
    (campo, valor) => {
      const normalizar = normalizadores[campo];
      setFormEstado((prev) => ({ ...prev, [campo]: normalizar ? normalizar(valor, prev) : valor }));
      setErroresBackend((prev) => {
        if (!(campo in prev)) return prev;
        const { [campo]: _omitido, ...resto } = prev;
        return resto;
      });
    },
    [normalizadores]
  );

  // Cambios masivos (ítems, tipo de persona): se limpian los errores que
  // devolvió el backend porque ya no describen el estado actual.
  const setForm = useCallback((actualizador) => {
    setFormEstado((prev) => (typeof actualizador === "function" ? actualizador(prev) : actualizador));
    setErroresBackend({});
  }, []);

  const tocar = useCallback((campo) => setTocados((prev) => (prev[campo] ? prev : { ...prev, [campo]: true })), []);

  const props = useCallback(
    (campo, { requerido = true } = {}) => ({
      value: form[campo] ?? "",
      onChange: (e) => setCampo(campo, e?.target ? (e.target.type === "checkbox" ? e.target.checked : e.target.value) : e),
      onBlur: () => tocar(campo),
      error: errorVisible(campo),
      required: requerido,
      "data-campo": campo,
    }),
    [form, setCampo, tocar, errorVisible]
  );

  // Enfoca el primer campo inválido EN ORDEN VISUAL (orden del DOM), no en
  // el orden en que el esquema reporta los errores.
  function enfocarPrimerInvalido(claves) {
    const contenedor = raiz.current ?? document;
    const invalidas = new Set(claves.flatMap((c) => [c, c.split(".")[0]]));
    const el = Array.from(contenedor.querySelectorAll("[data-campo]")).find((n) => invalidas.has(n.getAttribute("data-campo")));
    if (el) {
      el.focus({ preventScroll: false });
      el.scrollIntoView?.({ block: "center", behavior: "smooth" });
    }
  }

  /** Devuelve true si se envió; false si había errores (y enfoca el primero). */
  const enviar = useCallback(
    async (fn) => {
      setEnviado(true);
      const parse = esquema.safeParse(form);
      if (!parse.success) {
        const claves = parse.error.issues.map((i) => i.path.join("."));
        enfocarPrimerInvalido(claves);
        return false;
      }
      try {
        await fn(parse.data);
        return true;
      } catch (err) {
        const detalle = err?.response?.data;
        if (err?.response?.status === 422 && Array.isArray(detalle?.errores)) {
          const mapa = {};
          const generales = [];
          for (const e of detalle.errores) {
            if (e.campo) mapa[e.campo] = e.mensaje;
            else generales.push(e.mensaje);
          }
          setErroresBackend(mapa);
          enfocarPrimerInvalido(Object.keys(mapa));
          if (generales.length) {
            // Error de nivel formulario (sin campo): la página lo muestra
            // con su manejo normal de errores del backend.
            throw Object.assign(new Error(generales[0]), { response: { status: 422, data: { detail: generales.join(" · ") } } });
          }
          return false;
        }
        throw err;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [esquema, form]
  );

  return { form, setCampo, setForm, props, tocar, errores, errorVisible, hayErrores, valido: resultado.success, sucio, enviar, reiniciar, raiz };
}
