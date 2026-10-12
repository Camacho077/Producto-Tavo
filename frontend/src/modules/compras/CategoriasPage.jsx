import { CatalogoDetalle, CatalogoEditar, CatalogoLista, CatalogoNuevo } from "@/modules/compras/catalogo";

const CONFIG = {
  titulo: "Categorías",
  descripcion: "Agrupan los productos del catálogo.",
  singular: "categoría",
  articulo: "la",
  url: "/compras/categorias",
  ruta: "/compras/categorias",
  placeholder: "Buscar por nombre o descripción...",
};

export const CategoriasLista = () => <CatalogoLista config={CONFIG} />;
export const CategoriaNueva = () => <CatalogoNuevo config={CONFIG} />;
export const CategoriaDetalle = () => <CatalogoDetalle config={CONFIG} />;
export const CategoriaEditar = () => <CatalogoEditar config={CONFIG} />;
