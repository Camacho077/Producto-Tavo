import { Link, Navigate } from "react-router-dom";
import { ShieldOff } from "lucide-react";

import { Card, PageHeader } from "@/components/ui";
import { etiquetaDePlan, inicioDeRol, moduloContratado, modulosVisibles, planMinimoDe } from "@/config/modules";
import { useAuth } from "@/context/AuthContext";
import { fraseDePermiso } from "@/lib/permisos";

/**
 * BLOQUEO DE RUTAS POR PLAN Y POR ROL (comodidad, no seguridad: el backend
 * responde 403 de todos modos). Primero el plan de la empresa (2026-10-01:
 * antes una URL escrita a mano abría un módulo no contratado), luego el rol.
 * En lugar de la pantalla se muestra por qué no está disponible y a dónde sí
 * puede ir.
 */
export default function ConPermiso({ modulo, accion = "ver", children }) {
  const { puede, tenant } = useAuth();
  if (tenant && !moduloContratado(tenant.plan, tenant.modulos_activos, modulo)) {
    return <SinAcceso modulo={modulo} accion={accion} motivo="plan" />;
  }
  if (puede(modulo, accion)) return children;
  return <SinAcceso modulo={modulo} accion={accion} />;
}

/**
 * La raíz "/" es el dashboard; quien no puede verlo (Cajero, Bodega) entra
 * directo a su primera pantalla permitida en vez de chocar con un aviso.
 */
export function InicioSegunPermiso({ children }) {
  const { puede, tenant } = useAuth();
  if (puede("dashboard", "ver")) return children;
  const destino = inicioDeRol(modulosVisibles(tenant?.plan, tenant?.modulos_activos, puede), puede);
  if (destino && destino !== "/") return <Navigate to={destino} replace />;
  return <SinAcceso modulo="dashboard" accion="ver" />;
}

export function SinAcceso({ modulo, accion, motivo = "rol" }) {
  const { puede, tenant, usuario } = useAuth();
  const destino = inicioDeRol(modulosVisibles(tenant?.plan, tenant?.modulos_activos, puede), puede);
  const porPlan = motivo === "plan";
  return (
    <div className="pantalla-estrecha">
      <PageHeader
        titulo="Sin acceso"
        descripcion={porPlan ? "El plan de tu empresa no incluye esta pantalla." : "Tu rol no incluye esta pantalla."}
      />
      <Card>
        <div className="sin-acceso" role="alert">
          <ShieldOff size={20} aria-hidden="true" className="sin-acceso__icono" />
          <div>
            {porPlan ? (
              <p className="sin-acceso__texto">
                El plan <strong>{etiquetaDePlan(tenant?.plan)}</strong> de tu empresa no incluye esta pantalla. Está
                disponible desde el plan <strong>{planMinimoDe(modulo)}</strong> o como módulo adicional: escríbele a
                JS Company para activarlo.
              </p>
            ) : (
              <p className="sin-acceso__texto">
                Tu rol{usuario?.rol_nombre ? ` «${usuario.rol_nombre}»` : ""} no tiene permiso para{" "}
                <strong>{fraseDePermiso(modulo, accion)}</strong>. Pídele a un administrador de tu empresa que te lo
                asigne en Seguridad → Roles.
              </p>
            )}
            {destino && (
              <Link className="enlace" to={destino}>
                Ir a una pantalla disponible
              </Link>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
