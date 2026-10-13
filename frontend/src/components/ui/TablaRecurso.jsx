import BotonExportar from "@/components/ui/BotonExportar";
import Buscador from "@/components/ui/Buscador";
import Card from "@/components/ui/Card";
import EstadoCarga from "@/components/ui/EstadoCarga";
import Paginacion from "@/components/ui/Paginacion";
import { SkeletonTabla } from "@/components/ui/Skeleton";
import Table from "@/components/ui/Table";

/**
 * Tarjeta de listado estándar: buscador + tabla + paginación, alimentada por
 * useListadoPaginado. Mientras carga por PRIMERA vez muestra un marcador
 * estático con las mismas columnas; en las recargas siguientes (buscar,
 * paginar) las filas actuales se quedan tal cual hasta que llegan las
 * nuevas: nada se atenúa ni parpadea.
 *
 * `exportar` (nombre del archivo, p. ej. "productos") agrega el botón
 * "Exportar CSV" junto a los filtros: baja todas las filas de la búsqueda
 * y los filtros actuales (2026-10-01).
 */
export default function TablaRecurso({
  listado,
  columnas,
  titulo,
  descripcion,
  acciones,
  filtros,
  placeholderBusqueda = "Buscar...",
  vacio = "Sin registros.",
  idFila,
  exportar,
}) {
  const { items, total, pagina, paginas, porPagina, cargando, cargaInicial, error, busqueda, setBusqueda, setPagina } = listado;
  const vacioBusqueda = busqueda ? `Nada coincide con "${busqueda}".` : vacio;

  return (
    <Card titulo={titulo} descripcion={descripcion} acciones={acciones}>
      <div className="barra-listado">
        <Buscador valor={busqueda} onCambiar={setBusqueda} placeholder={placeholderBusqueda} className="barra-listado__buscador" />
        {filtros}
        {exportar && <BotonExportar listado={listado} nombre={exportar} />}
      </div>

      {error && <EstadoCarga error={error} />}
      {!error && (
        <div aria-busy={cargando}>
          {cargaInicial ? (
            <SkeletonTabla columnas={columnas} filas={Math.min(porPagina, 6)} />
          ) : (
            <Table columnas={columnas} filas={items} vacio={vacioBusqueda} idFila={idFila} />
          )}
        </div>
      )}

      <Paginacion pagina={pagina} paginas={paginas} total={total} porPagina={porPagina} onCambiar={setPagina} />
    </Card>
  );
}
