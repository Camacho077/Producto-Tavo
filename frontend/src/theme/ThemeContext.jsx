import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { MODO_CLARO, MODO_OSCURO } from "@/theme/tokens";

const CLAVE_MODO = "js_company_modo";

const ThemeContext = createContext(null);

function modoInicial() {
  try {
    const guardado = localStorage.getItem(CLAVE_MODO);
    if (guardado === MODO_CLARO || guardado === MODO_OSCURO) return guardado;
  } catch {
    // localStorage bloqueado (ventana privada, cookies deshabilitadas)
  }
  return MODO_CLARO; // claro por defecto (paleta monocromática, 2026-10-01)
}

export function ThemeProvider({ children }) {
  const [modo, setModo] = useState(modoInicial);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", modo);
    try {
      localStorage.setItem(CLAVE_MODO, modo);
    } catch {
      // si no se puede persistir, el modo sigue funcionando en esta sesión
    }
  }, [modo]);

  const alternarModo = useCallback(() => {
    setModo((actual) => (actual === MODO_OSCURO ? MODO_CLARO : MODO_OSCURO));
  }, []);

  const valor = useMemo(
    () => ({ modo, alternarModo, esOscuro: modo === MODO_OSCURO }),
    [modo, alternarModo]
  );

  return <ThemeContext.Provider value={valor}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme debe usarse dentro de un ThemeProvider");
  }
  return ctx;
}
