"""
Script: carga datos de ejemplo (demo) de RESTAURANTE para un tenant ya existente.

Qué deja cargado (fase 2, 2026-10-12; la fase 12 lo amplía con órdenes,
caja, gastos, mesas y un usuario por rol):
    - 6 categorías de la carta.
    - 12 insumos con su unidad (kg, g, L, unidad), grupo y mínimo.
    - 9 platos con receta completa (cantidades en g/ml aunque el insumo se
      lleve en kg/L, mermas donde se pela o se fríe) y modificadores
      ("sin tomate", "extra queso" con su insumo).
    - 1 combo de estudiante (hamburguesa + papas + gaseosa) con vigencia de
      lunes a viernes.
    - 3 proveedores (2 jurídicos con NIT y DV correctos, 1 natural con
      cédula), cada uno con los insumos que surte.
    - 6 compras CONFIRMADAS de insumos (3 de hace ~6 meses, 3 de las últimas
      semanas): la existencia y el costo promedio de cada insumo salen de
      ellas, con su fila en movimientos_insumo.
    - 9 ventas completadas que descuentan insumos POR RECETA: una por mes en
      los últimos 5 meses, una a mitad de semana, anteayer, ayer y HOY.

    FECHAS RELATIVAS A HOY EN CADA CORRIDA (2026-09-30): cada documento se
    re-ancla a sus "días atrás" contados desde el momento en que se corre el
    script, así el dashboard nunca queda en ceros.

Cómo lo hace:
    Todo pasa por los MISMOS esquemas Pydantic y servicios que usa la API:
    la existencia nunca se escribe a mano, la mueven compras y ventas.

Idempotente:
    Correrlo dos veces no duplica nada: cada registro se busca por su clave
    natural (nombre, NIT o documento) y los documentos por su nota
    "Datos de demostración · ...".

Uso (desde la carpeta backend, con su entorno virtual):
    venv\\Scripts\\python ..\\automatizaciones\\deploy\\seed_demo.py --email <correo con el que inicias sesión>
    venv\\Scripts\\python ..\\automatizaciones\\deploy\\seed_demo.py --tenant-id <uuid>
"""
import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # bajo pytest stdout es un objeto de captura
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.db.models import Tenant  # noqa: E402
from app.modules.seguridad.models import Usuario  # noqa: E402
from app.modules.catalogo import schemas as scat, services as svc_catalogo  # noqa: E402
from app.modules.catalogo.models import Categoria, Producto  # noqa: E402
from app.modules.compras import schemas as sc, services as svc_compras  # noqa: E402
from app.modules.compras.models import Compra, Proveedor  # noqa: E402
from app.modules.inventario import schemas as si  # noqa: E402
from app.modules.inventario.models import Insumo, MovimientoInsumo  # noqa: E402
from app.modules.inventario.unidades import legible  # noqa: E402
from app.modules.ventas import schemas as sv, services as svc_ventas  # noqa: E402
from app.modules.ventas.models import Venta  # noqa: E402

USUARIO = "Carga de demostración"
# "restaurante" en la nota: la demo del ERP heredado usaba las mismas notas
# ("venta 1 de 3") y el seed creía que ya existían (2026-10-12).
MARCA_NOTA = "Datos de demostración del restaurante"

# (nombre, descripción, orden en la toma de pedidos)
CATEGORIAS = [
    ("Almuerzos", "Platos fuertes del mediodía", 1),
    ("Hamburguesas", "Con pan artesanal", 2),
    ("Desayunos", "Hasta las 11 a. m.", 3),
    ("Acompañamientos", "Para agregar a cualquier plato", 4),
    ("Bebidas", "Venta directa: no pasan por cocina", 5),
    ("Combos", "Promociones para estudiantes", 6),
]

# (nombre, unidad, grupo, mínimo)
INSUMOS = [
    ("Arroz", "kg", "Abarrotes", "5"),
    ("Fríjol", "kg", "Abarrotes", "2"),
    ("Aceite", "L", "Abarrotes", "1.5"),
    ("Carne de res molida", "kg", "Carnes", "3"),
    ("Pechuga de pollo", "kg", "Carnes", "4"),
    ("Queso mozzarella", "kg", "Lácteos", "1"),
    ("Huevo", "unidad", "Lácteos", "24"),
    ("Tomate", "kg", "Verduras", "2"),
    ("Lechuga", "unidad", "Verduras", "5"),
    ("Papa pastusa", "kg", "Verduras", "10"),
    ("Pan de hamburguesa", "unidad", "Panadería", "20"),
    ("Gaseosa 400 ml", "unidad", "Bebidas", "24"),
]

# Recetas por porción: (insumo, cantidad, unidad, merma %). Se escriben en g y
# ml (como se cocina) aunque el insumo se lleve en kg y L.
PLATOS = [
    {"nombre": "Hamburguesa clásica", "categoria": "Hamburguesas", "precio": "16000",
     "descripcion": "Carne de res, queso, tomate y lechuga",
     "receta": [("Pan de hamburguesa", "1", "unidad", "0"), ("Carne de res molida", "150", "g", "0"),
                ("Queso mozzarella", "30", "g", "0"), ("Tomate", "40", "g", "10"), ("Lechuga", "0.1", "unidad", "0")],
     "modificadores": [("sin", "Tomate", "0", "Tomate", None, None), ("sin", "Lechuga", "0", "Lechuga", None, None),
                       ("extra", "Queso", "2500", "Queso mozzarella", "30", "g")]},
    {"nombre": "Hamburguesa doble", "categoria": "Hamburguesas", "precio": "22000",
     "descripcion": "Doble carne y doble queso",
     "receta": [("Pan de hamburguesa", "1", "unidad", "0"), ("Carne de res molida", "300", "g", "0"),
                ("Queso mozzarella", "60", "g", "0"), ("Tomate", "40", "g", "10")],
     "modificadores": [("sin", "Tomate", "0", "Tomate", None, None), ("extra", "Queso", "2500", "Queso mozzarella", "30", "g")]},
    {"nombre": "Pollo a la plancha", "categoria": "Almuerzos", "precio": "15000",
     "descripcion": "Con arroz y papa salada",
     "receta": [("Pechuga de pollo", "200", "g", "0"), ("Arroz", "150", "g", "0"),
                ("Papa pastusa", "200", "g", "15"), ("Aceite", "20", "ml", "0")],
     "modificadores": [("extra", "Arroz", "2000", "Arroz", "100", "g")]},
    {"nombre": "Bandeja del día", "categoria": "Almuerzos", "precio": "13000",
     "descripcion": "Arroz, fríjol, carne molida y huevo",
     "receta": [("Arroz", "150", "g", "0"), ("Fríjol", "120", "g", "0"), ("Carne de res molida", "100", "g", "0"),
                ("Huevo", "1", "unidad", "0"), ("Aceite", "15", "ml", "0")],
     "modificadores": [("sin", "Huevo", "0", "Huevo", None, None)]},
    {"nombre": "Arroz con pollo", "categoria": "Almuerzos", "precio": "14000",
     "descripcion": "Con ensalada",
     "receta": [("Arroz", "200", "g", "0"), ("Pechuga de pollo", "150", "g", "0"), ("Aceite", "10", "ml", "0")],
     "modificadores": []},
    {"nombre": "Huevos pericos", "categoria": "Desayunos", "precio": "8000",
     "descripcion": "Con tomate y cebolla",
     "receta": [("Huevo", "2", "unidad", "0"), ("Tomate", "50", "g", "10"), ("Aceite", "10", "ml", "0")],
     "modificadores": [("extra", "Huevo", "1500", "Huevo", "1", "unidad")]},
    {"nombre": "Papas a la francesa", "categoria": "Acompañamientos", "precio": "6000",
     "descripcion": "Porción mediana",
     "receta": [("Papa pastusa", "250", "g", "15"), ("Aceite", "40", "ml", "0")],
     "modificadores": []},
    {"nombre": "Gaseosa 400 ml", "categoria": "Bebidas", "precio": "3500", "va_a_cocina": False,
     "descripcion": "Venta directa: sale de la nevera",
     "receta": [("Gaseosa 400 ml", "1", "unidad", "0")],
     "modificadores": []},
    {"nombre": "Ensalada de la casa", "categoria": "Acompañamientos", "precio": "5000",
     "descripcion": "Lechuga y tomate",
     "receta": [("Lechuga", "0.25", "unidad", "0"), ("Tomate", "80", "g", "10")],
     "modificadores": []},
]

COMBO = {
    "nombre": "Combo estudiante", "categoria": "Combos", "precio": "22000",
    "descripcion": "Hamburguesa clásica, papas y gaseosa. Lunes a viernes.",
    "componentes": [("Hamburguesa clásica", 1), ("Papas a la francesa", 1), ("Gaseosa 400 ml", 1)],
    "dias_semana": [0, 1, 2, 3, 4],
}

# NIT con dígito de verificación DIAN correcto (el esquema lo vuelve a
# verificar al cargar).
PROVEEDORES = [
    {"tipo_persona": "juridica", "nit": "900456781-6", "razon_social": "Distribuidora La Sabana",
     "representante_nombre": "Martha Lucía Pineda", "representante_documento": "52345678",
     "telefono": "3001234567", "email": "ventas@lasabana.com.co", "direccion": "Calle 80 # 45-12, Bogotá",
     "surte": ["Carne de res molida", "Pechuga de pollo", "Queso mozzarella", "Huevo"]},
    {"tipo_persona": "juridica", "nit": "901234567-7", "razon_social": "Comercializadora Granos del Valle",
     "representante_nombre": "Jorge Iván Salazar", "representante_documento": "16789012",
     "telefono": "6024456789", "email": "pedidos@granosdelvalle.co", "direccion": "Carrera 1 # 23-40, Cali",
     "surte": ["Arroz", "Fríjol", "Aceite", "Gaseosa 400 ml", "Pan de hamburguesa"]},
    {"tipo_persona": "natural", "tipo_documento": "CC", "numero_documento": "79845123",
     "nombres": "Carlos Andrés", "apellidos": "Rincón Gómez",
     "telefono": "3157894561", "email": "carlos.rincon@correo.co", "direccion": "Plaza de Paloquemao, local 12, Bogotá",
     "surte": ["Tomate", "Lechuga", "Papa pastusa", "Huevo"]},
]

# (días atrás, clave del proveedor, [(insumo, cantidad, unidad, precio por esa unidad)])
# Las del historial cubren de sobra las ventas de hace 150 a 40 días; las
# recientes, las de esta semana, y dejan tomate, lechuga y papa por debajo
# de su mínimo (dispara el aviso del dashboard). El huevo se le compra a dos
# proveedores a precios distintos (la IA lo compara).
COMPRAS_HISTORIAL = [
    (175, "900456781-6", [("Carne de res molida", "21", "kg", "24000"), ("Pechuga de pollo", "12", "kg", "15500"),
                          ("Queso mozzarella", "3", "kg", "27000"), ("Huevo", "60", "unidad", "560")]),
    (172, "901234567-7", [("Arroz", "19", "kg", "4100"), ("Fríjol", "7", "kg", "7600"), ("Aceite", "5", "L", "9200"),
                          ("Gaseosa 400 ml", "108", "unidad", "1850"), ("Pan de hamburguesa", "81", "unidad", "680")]),
    (170, "79845123", [("Tomate", "4.5", "kg", "3300"), ("Lechuga", "9", "unidad", "2400"),
                       ("Papa pastusa", "27", "kg", "2100"), ("Huevo", "40", "unidad", "500")]),
]
COMPRAS = [
    (24, "900456781-6", [("Carne de res molida", "20", "kg", "25000"), ("Pechuga de pollo", "11", "kg", "16000"),
                         ("Queso mozzarella", "3000", "g", "28.5"), ("Huevo", "55", "unidad", "580")]),
    (19, "901234567-7", [("Arroz", "18", "kg", "4300"), ("Fríjol", "6", "kg", "7900"), ("Aceite", "4", "L", "9600"),
                         ("Gaseosa 400 ml", "104", "unidad", "1900"), ("Pan de hamburguesa", "78", "unidad", "700")]),
    (14, "79845123", [("Tomate", "4.2", "kg", "3600"), ("Lechuga", "8", "unidad", "2500"),
                      ("Papa pastusa", "26", "kg", "2200"), ("Huevo", "40", "unidad", "510")]),
]

# Lo que se vende en un día "normal" (factor 1). Cada venta escala estas
# cantidades: montos crecientes mes a mes y una semana con días seguidos.
VENTA_BASE = [
    ("Hamburguesa clásica", 10), ("Hamburguesa doble", 4), ("Pollo a la plancha", 8), ("Bandeja del día", 12),
    ("Papas a la francesa", 10), ("Gaseosa 400 ml", 20), ("Huevos pericos", 5), ("Arroz con pollo", 6),
    ("Combo estudiante", 4),
]
# (días atrás, cliente, documento, factor)
VENTAS_HISTORIAL = [
    (150, "Cierre de caja", "1032456789", "0.6"),
    (120, "Cierre de caja", "1032456789", "0.7"),
    (90, "Cierre de caja", "1032456789", "0.8"),
    (60, "Cierre de caja", "1032456789", "0.9"),
    (40, "Cierre de caja", "1032456789", "1.0"),
    (4, "Cierre de caja", "1032456789", "0.5"),
]
VENTAS = [
    (2, "Cierre de caja", "1032456789", "0.8"),
    (1, "Cierre de caja", "1032456789", "1.0"),
    (0, "Cierre de caja", "1032456789", "1.2"),
]


def salir(mensaje: str):
    # print y no SystemExit(mensaje): SystemExit escribe en stderr, que en
    # consolas cp1252 no muestra ✘ ni tildes.
    print(mensaje)
    raise SystemExit(1)


def elegir_tenant(db, tenant_id: str | None, email: str | None) -> Tenant:
    if email:
        usuario = db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()
        if usuario is None:
            salir(f"✘ No hay ningún usuario con el correo {email}")
        return db.query(Tenant).filter(Tenant.id == usuario.tenant_id).one()

    if tenant_id:
        try:
            tid = uuid.UUID(tenant_id)
        except ValueError:
            salir("✘ --tenant-id debe ser un UUID válido")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if tenant is None:
            salir(f"✘ No existe un tenant con id={tid}")
        return tenant

    tenants = db.query(Tenant).order_by(Tenant.created_at).all()
    if len(tenants) == 1:
        return tenants[0]
    if not tenants:
        salir("✘ No hay empresas registradas: crea una con alta_tenant.py o desde la pantalla de registro")
    lista = "\n".join(f"   {t.id}  {t.nombre_empresa}" for t in tenants)
    salir(f"✘ Hay {len(tenants)} empresas; indica cuál con --email (tu correo de acceso) o --tenant-id:\n{lista}")


def nota(texto: str) -> str:
    return f"{MARCA_NOTA} · {texto}"


def hace(dias: int, ahora: datetime) -> datetime:
    # A mediodía para que "hace 0 días" nunca quede en el futuro.
    return (ahora - timedelta(days=dias)).replace(hour=17, minute=30, second=0, microsecond=0) if dias else ahora


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
def cargar_categorias(db, tenant_id):
    por_nombre, creadas = {}, 0
    for nombre, descripcion, orden in CATEGORIAS:
        obj = db.query(Categoria).filter(Categoria.tenant_id == tenant_id, Categoria.nombre == nombre).first()
        if obj is None:
            datos = scat.CategoriaCreate(nombre=nombre, descripcion=descripcion, orden=orden)
            obj = Categoria(tenant_id=tenant_id, **datos.model_dump())
            db.add(obj)
            db.flush()
            creadas += 1
        por_nombre[nombre] = obj
    db.commit()
    return por_nombre, creadas


def cargar_insumos(db, tenant_id):
    por_nombre, creados = {}, 0
    for nombre, unidad, grupo, minimo in INSUMOS:
        obj = db.query(Insumo).filter(Insumo.tenant_id == tenant_id, Insumo.nombre == nombre).first()
        if obj is None:
            datos = si.InsumoCreate(nombre=nombre, unidad=unidad, grupo=grupo, minimo=Decimal(minimo))
            # Sin existencia ni costo: los ponen las compras.
            obj = Insumo(tenant_id=tenant_id, existencia=Decimal("0"), **datos.model_dump(exclude={"existencia_inicial"}))
            db.add(obj)
            db.flush()
            creados += 1
        por_nombre[nombre] = obj
    db.commit()
    return por_nombre, creados


def cargar_platos(db, tenant_id, categorias, insumos):
    por_nombre, creados = {}, 0
    for p in PLATOS:
        obj = db.query(Producto).filter(Producto.tenant_id == tenant_id, Producto.nombre == p["nombre"]).first()
        if obj is None:
            payload = scat.ProductoCreate(
                tipo="plato",
                nombre=p["nombre"],
                descripcion=p["descripcion"],
                precio=Decimal(p["precio"]),
                categoria_id=categorias[p["categoria"]].id,
                va_a_cocina=p.get("va_a_cocina", True),
                receta=[
                    scat.RecetaItemIn(insumo_id=insumos[i].id, cantidad=Decimal(c), unidad=u, merma_porcentaje=Decimal(m))
                    for i, c, u, m in p["receta"]
                ],
                modificadores=[
                    scat.ModificadorIn(
                        tipo=t, nombre=n, precio=Decimal(precio), insumo_id=insumos[i].id if i else None,
                        cantidad=Decimal(c) if c else None, unidad=u,
                    )
                    for t, n, precio, i, c, u in p["modificadores"]
                ],
            )
            obj = Producto(tenant_id=tenant_id, **payload.model_dump(exclude={"receta", "modificadores", "componentes"}))
            db.add(obj)
            db.flush()
            svc_catalogo.guardar_receta(db, tenant_id, obj, payload.receta)
            db.flush()
            svc_catalogo.guardar_modificadores(db, tenant_id, obj, payload.modificadores)
            creados += 1
        por_nombre[p["nombre"]] = obj
    db.commit()

    combo = db.query(Producto).filter(Producto.tenant_id == tenant_id, Producto.nombre == COMBO["nombre"]).first()
    if combo is None:
        payload = scat.ProductoCreate(
            tipo="combo",
            nombre=COMBO["nombre"],
            descripcion=COMBO["descripcion"],
            precio=Decimal(COMBO["precio"]),
            categoria_id=categorias[COMBO["categoria"]].id,
            dias_semana=COMBO["dias_semana"],
            componentes=[scat.ComboItemIn(producto_id=por_nombre[n].id, cantidad=c) for n, c in COMBO["componentes"]],
        )
        combo = Producto(tenant_id=tenant_id, **payload.model_dump(exclude={"receta", "modificadores", "componentes", "va_a_cocina"}), va_a_cocina=False)
        db.add(combo)
        db.flush()
        svc_catalogo.guardar_componentes(db, tenant_id, combo, payload.componentes)
        creados += 1
        db.commit()
    por_nombre[COMBO["nombre"]] = combo
    return por_nombre, creados


def cargar_proveedores(db, tenant_id, insumos):
    por_clave, creados = {}, 0
    for p in PROVEEDORES:
        datos = {k: v for k, v in p.items() if k != "surte"}
        clave = p.get("nit") or p["numero_documento"]
        columna = Proveedor.nit if p["tipo_persona"] == "juridica" else Proveedor.numero_documento
        proveedor = db.query(Proveedor).filter(Proveedor.tenant_id == tenant_id, columna == clave).first()
        if proveedor is None:
            payload = sc.ProveedorCreate(**datos, insumo_ids=[insumos[s].id for s in p["surte"]])
            proveedor = Proveedor(tenant_id=tenant_id, nombre=payload.nombre_derivado, **payload.model_dump(exclude={"insumo_ids"}))
            db.add(proveedor)
            db.flush()
            svc_compras.sincronizar_insumos_proveedor(db, tenant_id, proveedor, payload.insumo_ids)
            creados += 1
        por_clave[clave] = proveedor
    db.commit()
    return por_clave, creados


# ---------------------------------------------------------------------------
# Compras y ventas en orden cronológico
# ---------------------------------------------------------------------------
def existe(db, modelo, tenant_id, texto_nota) -> bool:
    return db.query(modelo.id).filter(modelo.tenant_id == tenant_id, modelo.notas == texto_nota).first() is not None


def lineas_de_venta(factor: str) -> list[tuple[str, int]]:
    f = Decimal(factor)
    return [(nombre, max(1, int((Decimal(cant) * f).to_integral_value()))) for nombre, cant in VENTA_BASE]


def linea_de_tiempo():
    """Todas las compras y ventas como (días atrás, tipo, nota, datos), en
    orden CRONOLÓGICO: el historial de cada insumo (existencia_resultante)
    queda en el mismo orden que las fechas."""
    eventos = []
    for i, (dias, clave, lineas) in enumerate(COMPRAS, start=1):
        eventos.append((dias, "compra", nota(f"compra {i} de {len(COMPRAS)}"), (clave, lineas)))
    for i, (dias, clave, lineas) in enumerate(COMPRAS_HISTORIAL, start=1):
        eventos.append((dias, "compra", nota(f"compra del historial {i} de {len(COMPRAS_HISTORIAL)}"), (clave, lineas)))
    for i, (dias, cliente, documento, factor) in enumerate(VENTAS, start=1):
        eventos.append((dias, "venta", nota(f"venta {i} de {len(VENTAS)}"), (cliente, documento, factor)))
    for i, (dias, cliente, documento, factor) in enumerate(VENTAS_HISTORIAL, start=1):
        eventos.append((dias, "venta", nota(f"venta del historial {i} de {len(VENTAS_HISTORIAL)}"), (cliente, documento, factor)))
    # Más antiguo primero; el mismo día, la compra antes que la venta.
    return sorted(eventos, key=lambda e: (-e[0], e[1] != "compra"))


def cargar_compras_y_ventas(db, tenant_id, proveedores, insumos, productos, ahora):
    compras = ventas = 0
    for dias, tipo, texto, datos in linea_de_tiempo():
        if tipo == "compra":
            if existe(db, Compra, tenant_id, texto):
                continue
            clave, lineas = datos
            payload = sc.CompraCreate(
                proveedor_id=proveedores[clave].id,
                fecha=hace(dias, ahora),
                notas=texto,
                confirmar=True,
                items=[
                    sc.CompraItemCreate(insumo_id=insumos[n].id, cantidad=Decimal(c), unidad=u, precio_unitario=Decimal(p))
                    for n, c, u, p in lineas
                ],
            )
            svc_compras.crear_compra(db, tenant_id, payload, USUARIO)
            compras += 1
        else:
            if existe(db, Venta, tenant_id, texto):
                continue
            cliente, documento, factor = datos
            payload = sv.VentaCreate(
                cliente_nombre=cliente,
                cliente_documento=documento,
                fecha=hace(dias, ahora),
                notas=texto,
                confirmar=True,
                items=[
                    sv.ItemCreate(producto_id=productos[n].id, cantidad=c, precio_unitario=productos[n].precio)
                    for n, c in lineas_de_venta(factor)
                ],
            )
            svc_ventas.crear_venta(db, tenant_id, payload, USUARIO)
            ventas += 1
    return compras, ventas


def reanclar_fechas(db, tenant_id, ahora):
    """Lleva CADA documento de la demo (y sus movimientos de insumos) a su
    "días atrás" contado desde HOY, en cada corrida (2026-09-30)."""
    movidos = 0
    for dias, tipo, texto, _ in linea_de_tiempo():
        modelo = Compra if tipo == "compra" else Venta
        doc = db.query(modelo).filter(modelo.tenant_id == tenant_id, modelo.notas == texto).first()
        if doc is None:
            continue
        fecha = hace(dias, ahora)
        doc.fecha = fecha
        doc.created_at = fecha
        for mov in db.query(MovimientoInsumo).filter(MovimientoInsumo.tenant_id == tenant_id, MovimientoInsumo.documento_id == doc.id):
            mov.created_at = fecha
        movidos += 1

    db.commit()
    return movidos


def cargar_demo(db, tenant_id, ahora):
    """Carga lo que falte y lleva todas las fechas a "hoy". La usan main() y
    tests/test_seed_demo.py, para que la prueba corra EXACTAMENTE lo mismo."""
    categorias, n_cat = cargar_categorias(db, tenant_id)
    insumos, n_ins = cargar_insumos(db, tenant_id)
    productos, n_prod = cargar_platos(db, tenant_id, categorias, insumos)
    proveedores, n_prov = cargar_proveedores(db, tenant_id, insumos)
    n_com, n_ven = cargar_compras_y_ventas(db, tenant_id, proveedores, insumos, productos, ahora)
    n_fechas = reanclar_fechas(db, tenant_id, ahora)
    return {
        "productos": productos, "insumos": insumos, "categorias": n_cat, "n_insumos": n_ins, "n_productos": n_prod,
        "proveedores": n_prov, "compras": n_com, "ventas": n_ven, "reanclados": n_fechas,
    }


def main():
    parser = argparse.ArgumentParser(description="Carga datos de ejemplo de restaurante para una empresa existente")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--email", help="Correo de un usuario: se carga en SU empresa")
    grupo.add_argument("--tenant-id", help="UUID de la empresa (opcional si solo hay una)")
    args = parser.parse_args()

    # Igual que created_at en la base: UTC sin zona.
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    db = SessionLocal()
    try:
        tenant = elegir_tenant(db, args.tenant_id, args.email)
        r = cargar_demo(db, tenant.id, ahora)
        print(f"✔ Empresa '{tenant.nombre_empresa}' (id={tenant.id})")
        print(f"   Nuevos en esta corrida: {r['categorias']} categorías, {r['n_insumos']} insumos, {r['n_productos']} platos y combos, "
              f"{r['proveedores']} proveedores, {r['compras']} compras, {r['ventas']} ventas")
        print(f"   Fechas llevadas a hoy: {r['reanclados']} documentos")
        print("   Existencias:")
        for insumo in r["insumos"].values():
            db.refresh(insumo)
            aviso = "  ← bajo el mínimo" if insumo.existencia <= insumo.minimo else ""
            print(f"     {insumo.nombre:<22} {legible(insumo.existencia, insumo.unidad):>14} (mínimo {legible(insumo.minimo, insumo.unidad)}){aviso}")
    except Exception as e:
        db.rollback()
        print(f"✘ Error cargando datos de ejemplo: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
