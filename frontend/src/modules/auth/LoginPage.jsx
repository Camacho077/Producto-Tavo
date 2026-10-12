import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import PieLegal from "@/components/PieLegal";
import { Button, Checkbox, Input, Modal } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { login, token, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [recordarme, setRecordarme] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [ayudaAbierta, setAyudaAbierta] = useState(false);

  if (token) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setEnviando(true);
    await login(email, password, recordarme);
    setEnviando(false);
  }

  return (
    // Fondo negro sólido y esquema oscuro forzado (auth.css): el panel va
    // centrado y transparente, igual en móvil, tableta y escritorio.
    <div className="auth esquema-oscuro">
      <form onSubmit={handleSubmit} className="auth__panel">
        <p className="auth__marca">JS Company</p>
        <h1 className="auth__titulo">Bienvenido de nuevo</h1>
        <p className="auth__subtitulo">Ingresa con tu cuenta para continuar</p>

        <div className="auth__campos">
          <Input
            variante="linea"
            etiqueta="Correo electrónico"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@negocio.com"
            autoComplete="email"
          />
          <Input
            variante="linea"
            etiqueta="Contraseña"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            error={error}
          />
        </div>

        <div className="auth__fila">
          <Checkbox
            etiqueta="Recordarme"
            checked={recordarme}
            onChange={(e) => setRecordarme(e.target.checked)}
          />
          <button type="button" className="auth__enlace" onClick={() => setAyudaAbierta(true)}>
            ¿Olvidaste tu contraseña?
          </button>
        </div>

        <Button type="submit" tamano="lg" bloque cargando={enviando} className="mt-6">
          {enviando ? "Ingresando..." : "Ingresar"}
        </Button>

        <p className="auth__pie">
          ¿Aún no tienes cuenta?{" "}
          <Link to="/registro" className="auth__enlace">
            Regístrate
          </Link>
        </p>
      </form>
      <PieLegal className="auth__pie-legal" />

      <Modal
        abierto={ayudaAbierta}
        onCerrar={() => setAyudaAbierta(false)}
        titulo="Recuperar el acceso"
        pie={
          <Button variante="secundario" onClick={() => setAyudaAbierta(false)}>
            Entendido
          </Button>
        }
      >
        <p className="text-[13px] text-[var(--texto-secundario)] leading-relaxed">
          Por seguridad, las contraseñas de este sistema solo puede restablecerlas el
          administrador de tu empresa: escríbele y pídele que te genere una nueva desde{" "}
          <strong className="text-[var(--texto)]">Seguridad → Usuarios</strong>.
        </p>
        <p className="text-[13px] text-[var(--texto-secundario)] leading-relaxed mt-3">
          Si tú eres el administrador y perdiste el acceso, contacta al soporte de JS Company
          para verificar tu identidad y recuperar la cuenta.
        </p>
      </Modal>
    </div>
  );
}
