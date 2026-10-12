import { useEffect, useMemo, useState } from "react";
import { Eye, Pencil, Plus, Power } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import FormularioPantalla, { Seccion } from "@/components/FormularioPantalla";
import Imagen3d from "@/components/Imagen3d";
import PantallaDetalle from "@/components/PantallaDetalle";
import { api } from "@/lib/api";
import { useApiResource } from "@/hooks/useApiResource";
import { useCatalogo } from "@/hooks/useCatalogo";
import { useFormulario } from "@/hooks/useFormulario";
import { useGuardarPantalla } from "@/hooks/useGuardarPantalla";
import { useListadoPaginado } from "@/hooks/useListadoPaginado";
import { useAuth } from "@/context/AuthContext";
import {
  formatearFecha,
  formatearMoneda,
  formatearNumero,
} from "@/lib/formato";
import { MIGAS, migasDe } from "@/lib/migas";
import { STOCK_MAX, esquemas } from "@/lib/validaciones";
import {
  AccionesFila,
  Badge,
  BotonAccion,
  Button,
  Card,
  Detalle,
  EstadoBadge,
  Input,
  ModalConfirmar,
  PageHeader,
  Select,
  TablaRecurso,
  Textarea,
} from "@/components/ui";

const RUTA = "/compras/productos";
const URL = "/compras/productos";

const FORM_VACIO = {
  nombre: "",
  sku: "",
  descripcion: "",
  precio: "",
  precio_compra: "",
  stock_minimo: "0",
  categoria_id: "",
};

// El stock NO se edita aquí: nace en 0 y solo se mueve con compras y ventas.
const ESQUEMA = z.object({
  nombre: esquemas.nombreItem(150),
  sku: esquemas.sku(),
  descripcion: esquemas.descripcion(500),
  precio: esquemas.precio(),
  precio_compra: esquemas.precio({ permitirCero: true, obligatorio: false }),
  stock_minimo: esquemas.entero(0, STOCK_MAX),
  categoria_id: z.string(),
});

const TIPOS_MOVIMIENTO = {
  compra: { etiqueta: "Compra", variante: "positivo" },
  anulacion_compra: { etiqueta: "Anulación de compra", variante: "neutro" },
  venta: { etiqueta: "Venta", variante: "neutro" },
  anulacion_venta: { etiqueta: "Anulación de venta", variante: "neutro" },
  ajuste_inicial: { etiqueta: "Saldo inicial", variante: "neutro" },
};

const migas = (...resto) => migasDe(MIGAS.productos, ...resto);

function cuerpoDe(d) {
  return {
    nombre: d.nombre,
    sku: d.sku,
    descripcion: d.descripcion || null,
    precio: d.precio,
    precio_compra: d.precio_compra === "" ? null : d.precio_compra,
    stock_minimo: Number(d.stock_minimo || 0),
    categoria_id: d.categoria_id || null,
  };
}

function ModalEstadoProducto({ producto, abierto, onCerrar, onConfirmar }) {
  return (
    <ModalConfirmar
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={producto?.activo ? "Desactivar producto" : "Activar producto"}
      textoConfirmar={producto?.activo ? "Desactivar" : "Activar"}
      mensaje={
        producto?.activo
          ? `"${producto?.nombre}" dejará de ofrecerse en compras, ventas y pedidos. Su historial se conserva.`
          : `"${producto?.nombre}" volverá a estar disponible.`
      }
      accion={`cambiar el estado del producto ${producto?.nombre ?? ""}`.trim()}
      mensajeExito={`${producto?.nombre} ${producto?.activo ? "desactivado" : "activado"}`}
      onConfirmar={onConfirmar}
    />
  );
}

export function ProductosLista() {
  const navigate = useNavigate();
  const { puede } = useAuth();
  const [filtroEstado, setFiltroEstado] = useState("");
  // El buscador del dashboard entra por aquí: /compras/productos?q=texto.
  const [parametros] = useSearchParams();
  const listado = useListadoPaginado(URL, {
    filtros: filtroEstado ? { activo: filtroEstado === "activo" } : {},
    busquedaInicial: parametros.get("q") ?? "",
  });
  const [registro, setRegistro] = useState(null);

  const columnas = [
    {
      // Columna solo visual: la misma imagen 3D local del detalle (misma
      // clave, misma forma), en miniatura de 44 px. No pide datos nuevos.
      clave: "imagen",
      titulo: "Imagen",
      ajustar: true,
      render: (r) => <Imagen3d clave={r.sku} tamano={44} className="miniatura" />,
    },
    {
      clave: "nombre",
      titulo: "Producto",
      render: (r) => (
        <Link to={`${RUTA}/${r.id}`} className="enlace">
          {r.nombre}
        </Link>
      ),
    },
    {
      clave: "sku",
      ajustar: true,
      titulo: "SKU",
      render: (r) => <span className="cifra">{r.sku}</span>,
    },
    {
      clave: "categoria_nombre",
      titulo: "Categoría",
      render: (r) => r.categoria_nombre || "—",
    },
    {
      clave: "precio",
      titulo: "Precio",
      cifra: true,
      render: (r) => formatearMoneda(r.precio),
    },
    {
      clave: "stock",
      titulo: "Stock",
      cifra: true,
      render: (r) => (
        <span
          className={
            r.stock <= r.stock_minimo ? "text-[var(--negativo-texto)]" : ""
          }
          title={
            r.stock <= r.stock_minimo ? "Por debajo del mínimo" : undefined
          }
        >
          {formatearNumero(r.stock)}
        </span>
      ),
    },
    {
      clave: "activo",
      ajustar: true,
      titulo: "Estado",
      render: (r) => <EstadoBadge activo={r.activo} />,
    },
    {
      clave: "acciones",
      titulo: "Acciones",
      render: (r) => (
        <AccionesFila>
          <BotonAccion icono={Eye} etiqueta="Ver detalle" onClick={() => navigate(`${RUTA}/${r.id}`)} />
          {puede("productos", "editar") && (
            <BotonAccion icono={Pencil} etiqueta="Editar" onClick={() => navigate(`${RUTA}/${r.id}/editar`)} />
          )}
          {puede("productos", "cambiar_estado") && (
            <BotonAccion icono={Power} etiqueta={r.activo ? "Desactivar" : "Activar"} onClick={() => setRegistro(r)} />
          )}
        </AccionesFila>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        titulo="Productos"
        descripcion="Catálogo con precio y categoría. El stock se mueve solo con compras y ventas."
        migas={migas()}
        acciones={
          puede("productos", "crear") && (
            <Button onClick={() => navigate(`${RUTA}/nuevo`)}>
              <Plus size={14} /> Nuevo producto
            </Button>
          )
        }
      />

      <TablaRecurso
        exportar="productos"
        listado={listado}
        columnas={columnas}
        placeholderBusqueda="Buscar por nombre, SKU o descripción..."
        vacio="Todavía no hay productos registrados."
        filtros={
          <Select
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
            className="w-40"
            aria-label="Filtrar por estado"
          >
            <option value="">Todos los estados</option>
            <option value="activo">Solo activos</option>
            <option value="inactivo">Solo inactivos</option>
          </Select>
        }
      />

      <ModalEstadoProducto
        producto={registro}
        abierto={registro !== null}
        onCerrar={() => setRegistro(null)}
        onConfirmar={async () => {
          await api.patch(`${URL}/${registro.id}/estado`, {
            activo: !registro.activo,
          });
          listado.recargar();
        }}
      />
    </div>
  );
}

function CamposProducto({ f, categorias, stockActual }) {
  // El costo delata el margen: solo lo ve y lo escribe quien puede ver
  // compras (el backend lo oculta y lo ignora igual para los demás).
  const { puede } = useAuth();
  const veCosto = puede("compras", "ver");
  return (
    <>
      <Seccion
        titulo="Identificación"
        descripcion="Los campos marcados con * son obligatorios."
      >
        <Input
          etiqueta="Nombre"
          {...f.props("nombre")}
          permitir="nombre"
          maxLength={150}
          autoComplete="off"
        />
        <div className="fila-campos">
          <Input
            etiqueta="SKU"
            {...f.props("sku")}
            permitir="sku"
            maxLength={50}
            ayuda="Letras, números, guion"
            cifra
          />
          <Select
            etiqueta="Categoría"
            {...f.props("categoria_id", { requerido: false })}
          >
            <option value="">Sin categoría</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Select>
        </div>
        <Textarea
          etiqueta="Descripción"
          {...f.props("descripcion", { requerido: false })}
          maxLength={500}
          ayuda="Opcional"
        />
      </Seccion>

      <Seccion
        titulo="Precios e inventario"
        descripcion="El stock no se edita: nace en 0 y lo mueven las compras confirmadas y las ventas."
      >
        <div className="fila-campos">
          <Input
            etiqueta="Precio de venta"
            cifra
            permitir="decimal"
            {...f.props("precio")}
            ayuda="Máximo 2 decimales"
          />
          {veCosto && (
            <Input
              etiqueta="Costo de compra"
              cifra
              permitir="decimal"
              {...f.props("precio_compra", { requerido: false })}
              ayuda="Opcional"
            />
          )}
        </div>
        <div className="fila-campos">
          <Input
            etiqueta="Stock actual"
            cifra
            value={formatearNumero(stockActual ?? 0)}
            disabled
            readOnly
            ayuda="Solo lectura: se mueve con compras y ventas"
          />
          <Input
            etiqueta="Stock mínimo"
            cifra
            permitir="entero"
            maxLength={7}
            {...f.props("stock_minimo")}
            ayuda="Alerta cuando el stock baja de aquí"
          />
        </div>
      </Seccion>
    </>
  );
}

export function ProductoNuevo() {
  const { items: categorias } = useCatalogo("/compras/categorias");
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: RUTA,
    mensaje: "Producto creado",
    accion: "crear el producto",
  });

  return (
    <div className="pantalla-estrecha">
      <PageHeader
        volver={RUTA}
        titulo="Nuevo producto"
        descripcion="El stock inicial es 0; ingresa existencias registrando una compra."
        migas={migas({ etiqueta: "Nuevo producto" })}
      />
      <FormularioPantalla
        id="form-producto"
        onSubmit={(e) => guardar(e, (d) => api.post(URL, cuerpoDe(d)))}
        volver={RUTA}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        errorGeneral={errorGeneral}
      >
        <CamposProducto
          f={f}
          categorias={categorias}
          stockActual={0}
        />
      </FormularioPantalla>
    </div>
  );
}

export function ProductoEditar() {
  const { id } = useParams();
  const { data, error } = useApiResource(`${URL}/${id}`);
  const { items: categorias } = useCatalogo("/compras/categorias");
  const esquema = useMemo(() => ESQUEMA, []);
  const f = useFormulario(esquema, FORM_VACIO);
  const { guardando, errorGeneral, guardar } = useGuardarPantalla(f, {
    volver: `${RUTA}/${id}`,
    mensaje: "Cambios guardados",
    accion: "guardar el producto",
  });

  useEffect(() => {
    if (!data) return;
    f.reiniciar({
      nombre: data.nombre,
      sku: data.sku,
      descripcion: data.descripcion ?? "",
      precio: String(data.precio),
      precio_compra:
        data.precio_compra == null ? "" : String(data.precio_compra),
      stock_minimo: String(data.stock_minimo ?? 0),
      categoria_id: data.categoria_id ?? "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <PantallaDetalle
      estrecha
      volver={RUTA}
      titulo={data ? `Editar ${data.nombre}` : "Editar producto"}
      migas={migas(
        { etiqueta: data?.nombre ?? "…", a: `${RUTA}/${id}` },
        { etiqueta: "Editar" },
      )}
      error={error}
      datos={data}
    >
      <FormularioPantalla
        id="form-producto"
        onSubmit={(e) =>
          guardar(e, (d) => api.put(`${URL}/${id}`, cuerpoDe(d)))
        }
        volver={`${RUTA}/${id}`}
        refRaiz={f.raiz}
        hayErrores={f.hayErrores}
        guardando={guardando}
        textoGuardar="Guardar cambios"
        errorGeneral={errorGeneral}
      >
        <CamposProducto
          f={f}
          categorias={categorias}
          stockActual={data?.stock}
        />
      </FormularioPantalla>
    </PantallaDetalle>
  );
}

/** Historial de movimientos de inventario del producto (paginado). */
function MovimientosProducto({ productoId }) {
  const listado = useListadoPaginado(`${URL}/${productoId}/movimientos`);
  const columnas = [
    {
      clave: "created_at",
      ajustar: true,
      titulo: "Fecha",
      render: (m) => formatearFecha(m.created_at),
    },
    {
      clave: "tipo",
      ajustar: true,
      titulo: "Tipo",
      render: (m) => {
        const t = TIPOS_MOVIMIENTO[m.tipo] ?? {
          etiqueta: m.tipo,
          variante: "neutro",
        };
        return <Badge variante={t.variante}>{t.etiqueta}</Badge>;
      },
    },
    {
      clave: "cantidad",
      titulo: "Cantidad",
      cifra: true,
      render: (m) => (
        <span className={m.cantidad < 0 ? "text-[var(--negativo-texto)]" : ""}>
          {m.cantidad > 0 ? "+" : ""}
          {formatearNumero(m.cantidad)}
        </span>
      ),
    },
    {
      clave: "stock_resultante",
      ajustar: true,
      titulo: "Stock resultante",
      cifra: true,
      render: (m) => formatearNumero(m.stock_resultante),
    },
    {
      clave: "documento_codigo",
      titulo: "Documento",
      render: (m) => {
        const ruta =
          m.documento_tipo === "compra"
            ? `/compras/${m.documento_id}`
            : m.documento_tipo === "venta"
              ? `/ventas/${m.documento_id}`
              : null;
        return ruta ? (
          <Link to={ruta} className="enlace cifra">
            {m.documento_codigo}
          </Link>
        ) : (
          <span className="cifra">{m.documento_codigo}</span>
        );
      },
    },
    {
      clave: "usuario_nombre",
      titulo: "Usuario",
      render: (m) => m.usuario_nombre || "—",
    },
  ];
  return (
    <TablaRecurso
      listado={listado}
      columnas={columnas}
      titulo="Movimientos de inventario"
      descripcion="Cada entrada y salida de stock, del más reciente al más antiguo. La suma explica el stock actual."
      placeholderBusqueda="Buscar por número de documento..."
      vacio="Sin movimientos todavía: el stock entra al confirmar una compra."
    />
  );
}

export function ProductoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error, recargar } = useApiResource(`${URL}/${id}`);
  const [dialogoEstado, setDialogoEstado] = useState(false);
  const { puede } = useAuth();

  return (
    <PantallaDetalle
      volver={RUTA}
      titulo={data?.nombre ?? "Detalle del producto"}
      descripcion={data ? `SKU ${data.sku}` : undefined}
      migas={migas({ etiqueta: data?.nombre ?? "…" })}
      error={error}
      datos={data}
      acciones={
        <>
          {puede("productos", "cambiar_estado") && (
            <Button variante="terciario" onClick={() => setDialogoEstado(true)}>
              <Power size={14} /> {data?.activo ? "Desactivar" : "Activar"}
            </Button>
          )}
          {puede("productos", "editar") && (
            <Button onClick={() => navigate(`${RUTA}/${id}/editar`)}>
              <Pencil size={14} /> Editar
            </Button>
          )}
        </>
      }
    >
      {data && (
        <div className="space-y-4">
          <div className="detalle-rejilla">
            <Card titulo="Datos generales">
              <div className="flex items-start gap-5">
                <Imagen3d clave={data.sku} tamano={96} className="shrink-0" />
                <div className="flex-1 min-w-0">
                  <Detalle
                    campos={[
                      { etiqueta: "Nombre", valor: data.nombre },
                      { etiqueta: "SKU", valor: data.sku, cifra: true },
                      { etiqueta: "Categoría", valor: data.categoria_nombre },
                      {
                        etiqueta: "Precio de venta",
                        valor: formatearMoneda(data.precio),
                        cifra: true,
                      },
                      ...(puede("compras", "ver")
                        ? [
                            {
                              etiqueta: "Costo de compra",
                              valor: data.precio_compra == null ? null : formatearMoneda(data.precio_compra),
                              cifra: true,
                            },
                          ]
                        : []),
                      {
                        etiqueta: "Estado",
                        valor: <EstadoBadge activo={data.activo} />,
                      },
                      {
                        etiqueta: "Creado",
                        valor: formatearFecha(data.created_at),
                      },
                      { etiqueta: "Descripción", valor: data.descripcion },
                    ]}
                  />
                </div>
              </div>
            </Card>

            <div className="space-y-4">
              <Card
                titulo="Inventario"
                descripcion="Solo lectura: lo mueven compras y ventas."
              >
                <p
                  className={`dato-grande cifra ${data.stock <= data.stock_minimo ? "text-[var(--negativo-texto)]" : ""}`}
                >
                  {formatearNumero(data.stock)}
                </p>
                <p className="text-[12px] text-[var(--texto-terciario)] mt-1">
                  Mínimo:{" "}
                  <span className="cifra">
                    {formatearNumero(data.stock_minimo ?? 0)}
                  </span>
                  {data.stock <= data.stock_minimo &&
                    " · por debajo del mínimo"}
                </p>
              </Card>

              <Card
                titulo="Proveedores"
                descripcion="Quiénes surten este producto."
              >
                {data.proveedores?.length ? (
                  <ul className="fichas" style={{ marginTop: 0 }}>
                    {data.proveedores.map((p) => (
                      <li key={p.id} className="ficha">
                        <Link
                          to={`/compras/proveedores/${p.id}`}
                          className="enlace"
                        >
                          {p.nombre}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[13px] text-[var(--texto-terciario)]">
                    Ningún proveedor lo tiene registrado todavía.
                  </p>
                )}
              </Card>
            </div>
          </div>

          <MovimientosProducto productoId={id} />
        </div>
      )}

      <ModalEstadoProducto
        producto={data}
        abierto={dialogoEstado}
        onCerrar={() => setDialogoEstado(false)}
        onConfirmar={async () => {
          await api.patch(`${URL}/${id}/estado`, { activo: !data.activo });
          recargar();
        }}
      />
    </PantallaDetalle>
  );
}
