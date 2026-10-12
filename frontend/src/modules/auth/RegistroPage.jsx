import { useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import PieLegal from "@/components/PieLegal";
import { Button, Input } from "@/components/ui";
import { RUTAS_LEGALES } from "@/config/legal";
import { useAuth } from "@/context/AuthContext";
import { BRANDING, LogoProducto } from "@/config/branding";

const FALTA_ACEPTAR = "Para crear la cuenta debes aceptar la Política de tratamiento de datos y los Términos y condiciones.";

export default function RegistroPage() {
  const { registro, token, error } = useAuth();
  const [nombreEmpresa, setNombreEmpresa] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [acepta, setAcepta] = useState(false);
  const [errorAcepta, setErrorAcepta] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const refAcepta = useRef(null);

  if (token) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    // Autorización expresa y previa (Ley 1581, art. 9): sin la casilla no se
    // envía nada. El backend lo exige igual (422) por si llega otro cliente.
    if (!acepta) {
      setErrorAcepta(FALTA_ACEPTAR);
      refAcepta.current?.focus();
      return;
    }
    setEnviando(true);
    await registro(nombreEmpresa, email, password, acepta);
    setEnviando(false);
  }

  return (
    // Fondo negro sólido y esquema oscuro forzado (auth.css): el panel va
    // centrado y transparente, igual en móvil, tableta y escritorio.
    <div className="auth esquema-oscuro">
      <form onSubmit={handleSubmit} className="auth__panel">
        <p className="auth__marca">
          <LogoProducto tamano={26} />
          {BRANDING.nombre}
        </p>
        <h1 className="auth__titulo">Crea tu cuenta</h1>
        <p className="auth__subtitulo">Registra tu restaurante para empezar a usar {BRANDING.nombre}</p>

        <div className="auth__campos">
          <Input
            variante="linea"
            etiqueta="Nombre de la empresa"
            required
            value={nombreEmpresa}
            onChange={(e) => setNombreEmpresa(e.target.value)}
            placeholder="Mi Negocio"
            autoComplete="organization"
          />
          <Input
            variante="linea"
            etiqueta="Correo electrónico"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@negocio.com"
            autoComplete="email"
          />
          <Input
            variante="linea"
            etiqueta="Contraseña"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            ayuda="Mínimo 8 caracteres."
            error={error}
          />
        </div>

        {/* Casilla DESMARCADA por defecto. Los enlaces abren en otra pestaña
            para no perder lo ya escrito en el formulario. */}
        <div className="auth__aceptar">
          <label className="checkbox auth__aceptar-etiqueta">
            <input
              ref={refAcepta}
              type="checkbox"
              checked={acepta}
              onChange={(e) => {
                setAcepta(e.target.checked);
                if (e.target.checked) setErrorAcepta(null);
              }}
              aria-invalid={errorAcepta ? true : undefined}
              aria-describedby={errorAcepta ? "registro-aceptar-error" : undefined}
            />
            <span>
              Acepto la{" "}
              <a href={RUTAS_LEGALES.politica_datos} target="_blank" rel="noopener" className="auth__enlace">
                Política de tratamiento de datos
              </a>{" "}
              y los{" "}
              <a href={RUTAS_LEGALES.terminos} target="_blank" rel="noopener" className="auth__enlace">
                Términos y condiciones
              </a>
              .
            </span>
          </label>
          {errorAcepta && (
            <span className="campo__error" id="registro-aceptar-error" role="alert">
              {errorAcepta}
            </span>
          )}
        </div>

        <Button type="submit" tamano="lg" bloque cargando={enviando} className="mt-7">
          {enviando ? "Creando cuenta..." : "Crear cuenta"}
        </Button>

        <p className="auth__pie">
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" className="auth__enlace">
            Inicia sesión
          </Link>
        </p>
      </form>
      <PieLegal className="auth__pie-legal" />
    </div>
  );
}
