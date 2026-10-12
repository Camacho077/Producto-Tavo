import { ArrowLeft } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import PieLegal from "@/components/PieLegal";
import { EMPRESA } from "@/config/empresa";
import { VERSIONES_LEGALES } from "@/config/legal";
import { Markdown, rellenar } from "@/modules/legal/markdown";
import politicaDatos from "@/modules/legal/textos/politica-datos.md?raw";
import terminos from "@/modules/legal/textos/terminos.md?raw";

import "./legal.css";

const TEXTOS = { politica_datos: politicaDatos, terminos };

/**
 * Documento legal en pantalla propia y PÚBLICA (se lee antes de tener
 * cuenta, desde el registro). Ruta diferida: no pesa en el login.
 */
function LegalPage({ documento }) {
  const navigate = useNavigate();
  const texto = rellenar(TEXTOS[documento], { ...EMPRESA, version: VERSIONES_LEGALES[documento] });

  return (
    <div className="legal">
      <div className="legal__columna">
        <nav className="legal__barra" aria-label="Navegación">
          <button
            type="button"
            className="iconbtn"
            onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/login"))}
            aria-label="Volver"
          >
            <ArrowLeft size={16} aria-hidden="true" />
          </button>
          <Link to="/" className="legal__marca">
            {EMPRESA.marca}
          </Link>
        </nav>
        <article className="legal__documento">
          <Markdown texto={texto} />
        </article>
        <PieLegal />
      </div>
    </div>
  );
}

export function PoliticaDatosPage() {
  return <LegalPage documento="politica_datos" />;
}

export function TerminosPage() {
  return <LegalPage documento="terminos" />;
}
