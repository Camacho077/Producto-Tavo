/**
 * BRANDING DEL PRODUCTO (2026-10-12) — el ÚNICO archivo con el nombre y el
 * logo del producto. Cambiar de nombre o de logo es editar solo esto (más
 * su espejo `backend/app/core/branding.py`, que usa el mismo nombre en los
 * PDF; `backend/tests/test_branding.py` exige que coincidan).
 *
 * El producto se vende a varios restaurantes: aquí NO va el nombre de ningún
 * cliente. Lo de cada restaurante (nombre, NIT, dirección, logo de la comanda
 * y la factura) se configura por empresa en Ajustes.
 *
 * El logo es PROVISIONAL: una campana de servicio (cloché) sobre un sello
 * redondeado, monocromo como todo el producto. Se pinta con `currentColor`
 * y el fondo de la superficie, así sirve igual en claro y en oscuro.
 */
export const BRANDING = {
  nombre: "JS Restaurante",
  // Lo que acompaña al nombre bajo el logo del sidebar.
  lema: "Sistema para restaurantes",
  // Empresa que presta el servicio (soporte, contratos, política de datos).
  proveedor: "JS Company",
};

export function LogoProducto({ tamano = 28, className = "" }) {
  return (
    <svg
      viewBox="0 0 32 32"
      width={tamano}
      height={tamano}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <rect width="32" height="32" rx="9" fill="currentColor" />
      <g fill="none" stroke="var(--logo-trazo, var(--superficie))" strokeWidth="2" strokeLinecap="round">
        <path d="M8.5 21.5h15" />
        <path d="M10 20a6 6 0 0 1 12 0" />
        <path d="M16 12.2v1.8" />
      </g>
    </svg>
  );
}
