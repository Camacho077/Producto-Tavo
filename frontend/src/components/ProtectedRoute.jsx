import { Navigate, Outlet } from "react-router-dom";

import { Spinner } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute() {
  const { token, cargando } = useAuth();

  if (cargando) {
    return (
      <div className="flex h-screen w-full items-center justify-center gap-2 bg-[var(--fondo)] text-[13px] text-[var(--texto-secundario)]">
        <Spinner tamano="sm" />
        Cargando...
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
