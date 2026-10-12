import { Link } from "react-router-dom";

import { EMPRESA } from "@/config/empresa";
import { RUTAS_LEGALES } from "@/config/legal";

import "./pie-legal.css";

/**
 * Pie con los datos de la empresa (nombre, NIT, correo, ciudad) y los
 * enlaces a la Política de tratamiento de datos y a los Términos. Va en
 * login, registro, los documentos legales y el marco de la aplicación.
 * Los datos salen de config/empresa.js (hoy con marcadores POR COMPLETAR).
 */
export default function PieLegal({ className = "" }) {
  return (
    <footer className={`pie-legal ${className}`}>
      <nav className="pie-legal__enlaces" aria-label="Documentos legales">
        <Link to={RUTAS_LEGALES.politica_datos}>Política de tratamiento de datos</Link>
        <Link to={RUTAS_LEGALES.terminos}>Términos y condiciones</Link>
      </nav>
      <p className="pie-legal__datos">
        <span>{EMPRESA.razonSocial}</span>
        <span>NIT {EMPRESA.nit}</span>
        <span>{EMPRESA.correo}</span>
        <span>{EMPRESA.ciudad}</span>
      </p>
    </footer>
  );
}
