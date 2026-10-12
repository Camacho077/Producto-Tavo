import { CatalogoDetalle, CatalogoEditar, CatalogoLista, CatalogoNuevo } from "@/modules/compras/catalogo";

const CONFIG = {
  titulo: "Marcas",
  descripcion: "Fabricantes o marcas comerciales de los productos.",
  singular: "marca",
  articulo: "la",
  url: "/compras/marcas",
  ruta: "/compras/marcas",
  placeholder: "Buscar por nombre o descripción...",
};

export const MarcasLista = () => <CatalogoLista config={CONFIG} />;
export const MarcaNueva = () => <CatalogoNuevo config={CONFIG} />;
export const MarcaDetalle = () => <CatalogoDetalle config={CONFIG} />;
export const MarcaEditar = () => <CatalogoEditar config={CONFIG} />;
