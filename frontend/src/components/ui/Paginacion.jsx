import { ChevronLeft, ChevronRight } from "lucide-react";
import Button from "@/components/ui/Button";
import { formatearNumero } from "@/lib/formato";

export default function Paginacion({ pagina, paginas, total, porPagina, onCambiar }) {
  if (!total) return null;
  const desde = (pagina - 1) * porPagina + 1;
  const hasta = Math.min(pagina * porPagina, total);

  return (
    <nav className="paginacion" aria-label="Paginación">
      <span className="paginacion__resumen">
        <span className="cifra">
          {formatearNumero(desde)}–{formatearNumero(hasta)}
        </span>{" "}
        de <span className="cifra">{formatearNumero(total)}</span>
      </span>
      <div className="flex items-center gap-1">
        <Button
          variante="terciario"
          tamano="sm"
          soloIcono
          onClick={() => onCambiar(pagina - 1)}
          disabled={pagina <= 1}
          aria-label="Página anterior"
        >
          <ChevronLeft size={14} />
        </Button>
        <span className="paginacion__pagina cifra">
          {pagina} / {paginas}
        </span>
        <Button
          variante="terciario"
          tamano="sm"
          soloIcono
          onClick={() => onCambiar(pagina + 1)}
          disabled={pagina >= paginas}
          aria-label="Página siguiente"
        >
          <ChevronRight size={14} />
        </Button>
      </div>
    </nav>
  );
}
