import { createElement, lazy } from "react";

/**
 * CARGA DIFERIDA CON PRECARGA (2026-10-01).
 *
 * `lazy()` a secas SIEMPRE suspende la primera vez que se pinta, aunque su
 * archivo ya esté descargado, y React 19 retiene la revelación de un límite
 * de Suspense hasta ~300 ms (throttle de fallbacks). Medido en el dashboard:
 * su trozo llegaba a los 258 ms y no se pintaba hasta los ~550 ms; las
 * peticiones a la API salían a los 607 ms.
 *
 * `modulo()` guarda el módulo en cuanto llega y `perezoso()` lo pinta DIRECTO
 * si ya está: sin suspender, sin fallback y sin esa espera. Si todavía no
 * está, se comporta exactamente como `lazy()`. Precargar (`mod.cargar()`)
 * solo adelanta una descarga que la ruta iba a pedir de todos modos.
 */
export function modulo(importar) {
  const mod = { valor: null, promesa: null };
  mod.cargar = () => {
    mod.promesa ??= importar().then((valor) => {
      mod.valor = valor;
      return valor;
    });
    return mod.promesa;
  };
  return mod;
}

/** Componente diferido que exporta `nombre` (por defecto `default`) de `mod`. */
export function perezoso(mod, nombre = "default") {
  const Diferido = lazy(() => mod.cargar().then((valor) => ({ default: valor[nombre] })));
  function Pantalla(props) {
    const Cargado = mod.valor?.[nombre];
    return createElement(Cargado ?? Diferido, props);
  }
  Pantalla.displayName = `Perezoso(${nombre})`;
  return Pantalla;
}
