import { CatalogoDetalle, CatalogoEditar, CatalogoLista, CatalogoNuevo } from "@/modules/carta/catalogo";

const CONFIG = {
  titulo: "Categorías",
  descripcion: "Secciones de la carta: son las pestañas al tomar un pedido.",
  singular: "categoría",
  articulo: "la",
  url: "/catalogo/categorias",
  ruta: "/carta/categorias",
  placeholder: "Buscar por nombre o descripción...",
};

export const CategoriasLista = () => <CatalogoLista config={CONFIG} />;
export const CategoriaNueva = () => <CatalogoNuevo config={CONFIG} />;
export const CategoriaDetalle = () => <CatalogoDetalle config={CONFIG} />;
export const CategoriaEditar = () => <CatalogoEditar config={CONFIG} />;
