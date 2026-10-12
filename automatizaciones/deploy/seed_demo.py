"""
Script: carga datos de ejemplo (demo) para un tenant ya existente.

Qué deja cargado:
    - 5 categorías y 5 marcas.
    - 5 proveedores: 3 personas jurídicas (NIT con dígito de verificación
      DIAN correcto) y 2 naturales (cédula de ciudadanía y de extranjería).
    - 5 productos, cada uno con categoría, marca y los proveedores que lo
      surten (tabla proveedor_productos).
    - 8 compras CONFIRMADAS (3 de hace ~6 meses y 5 de las últimas semanas):
      el stock de cada producto sale de ellas, con su fila en
      movimientos_inventario.
    - 9 ventas completadas: una por mes en los últimos 5 meses, una a mitad
      de semana, anteayer, ayer y HOY. Y 2 pedidos: uno "en proceso" y uno
      "pendiente" sin avanzar desde hace 4 días.

    FECHAS RELATIVAS A HOY EN CADA CORRIDA (2026-09-30): cada documento de la
    demo se re-ancla a sus "días atrás" contados desde el momento en que se
    corre el script. Antes la demo quedaba congelada en el día en que se
    cargó y a los dos días el dashboard mostraba "Hoy" en ceros. Correrlo
    antes de una demostración la deja siempre al día.

    Con eso el dashboard deja de estar en ceros: total vendido, gráfica,
    más vendidos, inventario por categoría y avisos (stock bajo el mínimo,
    pedido estancado y el más vendido de la semana).

Cómo lo hace:
    Todo pasa por los MISMOS esquemas Pydantic que usa la API (así cada dato
    cumple las validaciones: nombres, NIT, documentos, teléfono, fechas) y
    por las mismas funciones de servicio (crear_compra, crear_venta,
    crear_pedido, cambiar_estado_pedido): el stock nunca se escribe a mano,
    lo mueven las compras y ventas, igual que desde la pantalla.

Idempotente:
    Correrlo dos veces no duplica nada. Cada registro se busca antes por su
    clave natural (nombre de categoría/marca, NIT o documento del proveedor,
    SKU del producto) y las compras, ventas y pedidos por su nota
    "Datos de demostración · ...".

Uso (desde la carpeta backend, con su entorno virtual):
    venv\\Scripts\\python ..\\automatizaciones\\deploy\\seed_demo.py --email <correo con el que inicias sesión>
    venv\\Scripts\\python ..\\automatizaciones\\deploy\\seed_demo.py --tenant-id <uuid>

    --email elige la empresa de ese usuario. Sin ninguno de los dos usa la
    única empresa registrada; si hay varias, las lista para elegir.
"""
import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Evita UnicodeEncodeError al imprimir ✔/✘ en consolas de Windows que no
# usan UTF-8 por defecto (cp1252, etc.).
if hasattr(sys.stdout, "reconfigure"):  # bajo pytest stdout es un objeto de captura
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.db.models import Tenant  # noqa: E402
from app.modules.seguridad.models import Usuario  # noqa: E402
from app.modules.compras import schemas as sc, services as svc_compras  # noqa: E402
from app.modules.compras.models import Categoria, Compra, Marca, MovimientoInventario, Producto, Proveedor  # noqa: E402
from app.modules.ventas import schemas as sv, services as svc_ventas  # noqa: E402
from app.modules.ventas.models import Pedido, Venta  # noqa: E402

USUARIO = "Carga de demostración"
MARCA_NOTA = "Datos de demostración"

CATEGORIAS = [
    ("Bebidas", "Gaseosas, jugos y aguas"),
    ("Abarrotes", "Granos y básicos de despensa"),
    ("Aseo", "Limpieza del hogar"),
    ("Lácteos", "Leche y derivados"),
    ("Pasabocas", "Paquetes y snacks"),
]

MARCAS = [
    ("Sabana Fresca", "Bebidas y lácteos de la sabana"),
    ("Granos del Valle", "Arroz y granos"),
    ("Brillo Hogar", "Productos de aseo"),
    ("Campo Verde", "Lácteos de finca"),
    ("Crocante", "Pasabocas"),
]

# stock_minimo alto en la leche a propósito: tras las ventas queda por debajo
# y dispara el aviso "stock bajo el mínimo" del dashboard.
PRODUCTOS = [
    {"sku": "DEMO-GAS-001", "nombre": "Gaseosa Cola Familiar", "precio": "5500", "stock_minimo": 10,
     "categoria": "Bebidas", "marca": "Sabana Fresca"},
    {"sku": "DEMO-ARR-001", "nombre": "Arroz Blanco Premium", "precio": "3200", "stock_minimo": 15,
     "categoria": "Abarrotes", "marca": "Granos del Valle"},
    {"sku": "DEMO-DET-001", "nombre": "Detergente en Polvo", "precio": "8900", "stock_minimo": 5,
     "categoria": "Aseo", "marca": "Brillo Hogar"},
    {"sku": "DEMO-LEC-001", "nombre": "Leche Entera en Bolsa", "precio": "4200", "stock_minimo": 20,
     "categoria": "Lácteos", "marca": "Campo Verde"},
    {"sku": "DEMO-PAP-001", "nombre": "Papas Fritas Onduladas", "precio": "2500", "stock_minimo": 8,
     "categoria": "Pasabocas", "marca": "Crocante"},
]

# NIT con dígito de verificación calculado con el algoritmo de la DIAN
# (app.core.validaciones.digito_verificacion_nit); el esquema lo vuelve a
# verificar al cargar, así que un dígito equivocado detiene el script.
PROVEEDORES = [
    {"tipo_persona": "juridica", "nit": "900456781-6", "razon_social": "Distribuidora La Sabana",
     "representante_nombre": "Martha Lucía Pineda", "representante_documento": "52345678",
     "telefono": "3001234567", "email": "ventas@lasabana.com.co", "direccion": "Calle 80 # 45-12, Bogotá",
     "surte": ["DEMO-GAS-001", "DEMO-LEC-001"]},
    {"tipo_persona": "juridica", "nit": "901234567-7", "razon_social": "Comercializadora Granos del Valle",
     "representante_nombre": "Jorge Iván Salazar", "representante_documento": "16789012",
     "telefono": "6024456789", "email": "pedidos@granosdelvalle.co", "direccion": "Carrera 1 # 23-40, Cali",
     "surte": ["DEMO-ARR-001", "DEMO-PAP-001"]},
    {"tipo_persona": "juridica", "nit": "830045672-4", "razon_social": "Químicos Brillo Hogar",
     "representante_nombre": "Ana María Ortiz", "representante_documento": "43210987",
     "telefono": "6046012345", "email": "contacto@brillohogar.co", "direccion": "Calle 10 Sur # 50-8, Medellín",
     "surte": ["DEMO-DET-001"]},
    {"tipo_persona": "natural", "tipo_documento": "CC", "numero_documento": "79845123",
     "nombres": "Carlos Andrés", "apellidos": "Rincón Gómez",
     "telefono": "3157894561", "email": "carlos.rincon@correo.co", "direccion": "Vereda El Rosal, Subachoque",
     "surte": ["DEMO-LEC-001", "DEMO-GAS-001"]},
    {"tipo_persona": "natural", "tipo_documento": "CE", "numero_documento": "456789",
     "nombres": "Valentina", "apellidos": "Márquez Duarte",
     "telefono": "3209876543", "email": "valentina.marquez@correo.co", "direccion": "Carrera 7 # 12-30, Tunja",
     "surte": ["DEMO-PAP-001", "DEMO-ARR-001"]},
]

# (días atrás, clave del proveedor, [(sku, cantidad, precio de compra)])
COMPRAS = [
    (24, "900456781-6", [("DEMO-GAS-001", 48, "3300"), ("DEMO-LEC-001", 30, "2600")]),
    (19, "901234567-7", [("DEMO-ARR-001", 60, "1900"), ("DEMO-PAP-001", 40, "1400")]),
    (14, "830045672-4", [("DEMO-DET-001", 25, "5400")]),
    (10, "79845123", [("DEMO-LEC-001", 12, "2500")]),
    (7, "456789", [("DEMO-PAP-001", 30, "1350")]),
]

# (días atrás, cliente, documento, [(sku, cantidad)]) — se venden al precio del producto.
# Días CONSECUTIVOS (hace 2, ayer, hoy) y montos crecientes ($63.700 →
# $131.600 → $158.600): con días salteados la gráfica de 1M/1S dibujaba
# picos aislados en vez de una curva. Todas caen en el periodo "Mes" y el
# rango "1M" con los que abre el dashboard, y después de las compras.
VENTAS = [
    (2, "Laura Restrepo", "1020304050", [("DEMO-DET-001", 3), ("DEMO-GAS-001", 4), ("DEMO-PAP-001", 6)]),
    (1, "Tienda Don Pacho", "80123456", [("DEMO-GAS-001", 12), ("DEMO-ARR-001", 10), ("DEMO-LEC-001", 8)]),
    (0, "Minimercado La Esquina", "900987654-7", [("DEMO-LEC-001", 18), ("DEMO-PAP-001", 20), ("DEMO-GAS-001", 6)]),
]

# HISTORIAL (2026-09-30): sin él, "6 meses", "Año" y la proyección por
# regresión de 6 meses salían planos. Una compra grande hace ~6 meses y una
# venta por mes, con montos crecientes; más una venta a mitad de la semana.
# Notas NUEVAS ("del historial"): las de arriba no cambian, así una empresa
# que ya tenía la demo no recibe duplicados, solo lo que le falta.
# Cada venta del historial está cubierta por compras de fecha ANTERIOR
# (gaseosa 48 de 60, leche 37 de 40, arroz 59 de 80, papas 46 de 60,
# detergente 17 de 30): el historial de inventario queda en orden.
COMPRAS_HISTORIAL = [
    (175, "900456781-6", [("DEMO-GAS-001", 60, "3200"), ("DEMO-LEC-001", 40, "2500")]),
    (170, "901234567-7", [("DEMO-ARR-001", 80, "1850"), ("DEMO-PAP-001", 60, "1350")]),
    (165, "830045672-4", [("DEMO-DET-001", 30, "5300")]),
]
VENTAS_HISTORIAL = [
    (150, "Panadería La Espiga", "1032456789", [("DEMO-GAS-001", 6), ("DEMO-LEC-001", 5), ("DEMO-ARR-001", 8), ("DEMO-PAP-001", 6), ("DEMO-DET-001", 2)]),
    (120, "Cafetería El Parque", "52789123", [("DEMO-GAS-001", 8), ("DEMO-LEC-001", 6), ("DEMO-ARR-001", 10), ("DEMO-PAP-001", 8), ("DEMO-DET-001", 3)]),
    (90, "Restaurante Doña Rosa", "39456712", [("DEMO-GAS-001", 10), ("DEMO-LEC-001", 8), ("DEMO-ARR-001", 12), ("DEMO-PAP-001", 10), ("DEMO-DET-001", 3)]),
    (60, "Tienda La Económica", "1098765432", [("DEMO-GAS-001", 12), ("DEMO-LEC-001", 8), ("DEMO-ARR-001", 14), ("DEMO-PAP-001", 10), ("DEMO-DET-001", 4)]),
    (40, "Supermercado El Ahorro", "71234567", [("DEMO-GAS-001", 12), ("DEMO-LEC-001", 10), ("DEMO-ARR-001", 15), ("DEMO-PAP-001", 12), ("DEMO-DET-001", 5)]),
    (4, "Droguería Santa Fe", "43567890", [("DEMO-GAS-001", 5), ("DEMO-LEC-001", 3), ("DEMO-ARR-001", 6), ("DEMO-PAP-001", 8), ("DEMO-DET-001", 2)]),
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
    # A media mañana para que "hace 0 días" nunca quede en el futuro.
    return (ahora - timedelta(days=dias)).replace(hour=10, minute=30, second=0, microsecond=0) if dias else ahora


def cargar_catalogo(db, tenant_id, modelo, filas, esquema):
    por_nombre = {}
    creados = 0
    for nombre, descripcion in filas:
        obj = db.query(modelo).filter(modelo.tenant_id == tenant_id, modelo.nombre == nombre).first()
        if obj is None:
            datos = esquema(nombre=nombre, descripcion=descripcion)
            obj = modelo(tenant_id=tenant_id, **datos.model_dump())
            db.add(obj)
            db.flush()
            creados += 1
        por_nombre[nombre] = obj
    db.commit()
    return por_nombre, creados


def cargar_productos(db, tenant_id, categorias, marcas):
    por_sku = {}
    creados = 0
    for p in PRODUCTOS:
        producto = db.query(Producto).filter(Producto.tenant_id == tenant_id, Producto.sku == p["sku"]).first()
        if producto is None:
            datos = sc.ProductoCreate(
                nombre=p["nombre"],
                sku=p["sku"],
                precio=Decimal(p["precio"]),
                stock_minimo=p["stock_minimo"],
                categoria_id=categorias[p["categoria"]].id,
                marca_id=marcas[p["marca"]].id,
            )
            # El stock nace en 0: solo lo mueven compras y ventas.
            producto = Producto(tenant_id=tenant_id, stock=0, **datos.model_dump())
            db.add(producto)
            db.flush()
            creados += 1
        por_sku[p["sku"]] = producto
    db.commit()
    return por_sku, creados


def cargar_proveedores(db, tenant_id, productos):
    por_clave = {}
    creados = 0
    for p in PROVEEDORES:
        datos = {k: v for k, v in p.items() if k != "surte"}
        clave = p.get("nit") or p["numero_documento"]
        columna = Proveedor.nit if p["tipo_persona"] == "juridica" else Proveedor.numero_documento
        proveedor = db.query(Proveedor).filter(Proveedor.tenant_id == tenant_id, columna == clave).first()
        if proveedor is None:
            payload = sc.ProveedorCreate(**datos, producto_ids=[productos[s].id for s in p["surte"]])
            proveedor = Proveedor(
                tenant_id=tenant_id, nombre=payload.nombre_derivado, **payload.model_dump(exclude={"producto_ids"})
            )
            db.add(proveedor)
            db.flush()
            svc_compras.sincronizar_productos_proveedor(db, tenant_id, proveedor, payload.producto_ids)
            creados += 1
        por_clave[clave] = proveedor
    db.commit()
    return por_clave, creados


def existe(db, modelo, tenant_id, texto_nota) -> bool:
    return db.query(modelo.id).filter(modelo.tenant_id == tenant_id, modelo.notas == texto_nota).first() is not None


def linea_de_tiempo():
    """Todas las compras y ventas de la demo como (días atrás, tipo, nota,
    datos), en orden CRONOLÓGICO: así el historial de inventario de cada
    producto (stock_resultante) queda en el mismo orden que las fechas."""
    eventos = []
    for i, (dias, clave, lineas) in enumerate(COMPRAS, start=1):
        eventos.append((dias, "compra", nota(f"compra {i} de {len(COMPRAS)}"), (clave, lineas)))
    for i, (dias, clave, lineas) in enumerate(COMPRAS_HISTORIAL, start=1):
        eventos.append((dias, "compra", nota(f"compra del historial {i} de {len(COMPRAS_HISTORIAL)}"), (clave, lineas)))
    for i, (dias, cliente, documento, lineas) in enumerate(VENTAS, start=1):
        eventos.append((dias, "venta", nota(f"venta {i} de {len(VENTAS)}"), (cliente, documento, lineas)))
    for i, (dias, cliente, documento, lineas) in enumerate(VENTAS_HISTORIAL, start=1):
        eventos.append((dias, "venta", nota(f"venta del historial {i} de {len(VENTAS_HISTORIAL)}"), (cliente, documento, lineas)))
    # Más antiguo primero; el mismo día, la compra antes que la venta.
    return sorted(eventos, key=lambda e: (-e[0], e[1] != "compra"))


def cargar_compras_y_ventas(db, tenant_id, proveedores, productos, ahora):
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
                    sc.CompraItemCreate(producto_id=productos[sku].id, cantidad=cant, precio_unitario=Decimal(precio))
                    for sku, cant, precio in lineas
                ],
            )
            svc_compras.crear_compra(db, tenant_id, payload, USUARIO)
            compras += 1
        else:
            if existe(db, Venta, tenant_id, texto):
                continue
            cliente, documento, lineas = datos
            payload = sv.VentaCreate(
                cliente_nombre=cliente,
                cliente_documento=documento,
                fecha=hace(dias, ahora),
                notas=texto,
                confirmar=True,
                items=[
                    sv.ItemCreate(producto_id=productos[sku].id, cantidad=cant, precio_unitario=productos[sku].precio)
                    for sku, cant in lineas
                ],
            )
            svc_ventas.crear_venta(db, tenant_id, payload, USUARIO)
            ventas += 1
    return compras, ventas


def reanclar_fechas(db, tenant_id, ahora):
    """
    Lleva CADA documento de la demo a su "días atrás" contado desde HOY, en
    cada corrida (2026-09-30). Antes la demo era idempotente pero quedaba
    congelada en el día en que se cargó: a los dos días "Hoy" mostraba ceros.
    Ahora correr el seed cualquier día deja ventas hoy, esta semana, este mes
    y en los últimos meses. Se mueven también sus movimientos de inventario
    y, en los pedidos, la entrega y la línea de tiempo.
    Solo toca registros marcados con la nota de demostración.
    """
    movidos = 0
    for dias, tipo, texto, _ in linea_de_tiempo():
        modelo = Compra if tipo == "compra" else Venta
        doc = db.query(modelo).filter(modelo.tenant_id == tenant_id, modelo.notas == texto).first()
        if doc is None:
            continue
        fecha = hace(dias, ahora)
        doc.fecha = fecha
        doc.created_at = fecha
        for mov in db.query(MovimientoInventario).filter(
            MovimientoInventario.tenant_id == tenant_id, MovimientoInventario.documento_id == doc.id
        ):
            mov.created_at = fecha
        movidos += 1

    # Pedidos: el "en proceso" se tomó ayer y se entrega en 2 días; el
    # "pendiente" lleva 4 días sin avanzar (dispara su aviso) y se entrega en 5.
    for texto, dias_atras, entrega_en in ((nota("pedido en proceso"), 1, 2), (nota("pedido pendiente"), 4, 5)):
        pedido = db.query(Pedido).filter(Pedido.tenant_id == tenant_id, Pedido.notas == texto).first()
        if pedido is None:
            continue
        fecha = hace(dias_atras, ahora)
        pedido.fecha = fecha
        pedido.created_at = fecha
        pedido.fecha_entrega = (ahora + timedelta(days=entrega_en)).replace(hour=15, minute=0, second=0, microsecond=0)
        for n, evento in enumerate(sorted(pedido.eventos, key=lambda e: e.created_at)):
            # Creación en la fecha del pedido; cada avance, unas horas después.
            evento.created_at = fecha + timedelta(hours=3 * n)
        movidos += 1
    db.commit()
    return movidos


def cargar_pedidos(db, tenant_id, productos, ahora):
    creados = 0

    # Pedido 1: ya avanzó a "en proceso".
    texto = nota("pedido en proceso")
    if not existe(db, Pedido, tenant_id, texto):
        pedido = svc_ventas.crear_pedido(
            db,
            tenant_id,
            sv.PedidoCreate(
                cliente_nombre="Restaurante El Fogón",
                cliente_telefono="3112223344",
                cliente_direccion="Calle 45 # 13-20, Bogotá",
                fecha=ahora,
                fecha_entrega=ahora + timedelta(days=2),
                prioridad="alta",
                notas=texto,
                items=[
                    sv.ItemCreate(producto_id=productos["DEMO-GAS-001"].id, cantidad=24, precio_unitario=productos["DEMO-GAS-001"].precio),
                    sv.ItemCreate(producto_id=productos["DEMO-ARR-001"].id, cantidad=20, precio_unitario=productos["DEMO-ARR-001"].precio),
                ],
            ),
            USUARIO,
        )
        svc_ventas.cambiar_estado_pedido(
            db, tenant_id, pedido.id, sv.PedidoCambioEstado(estado="en_proceso", nota="Alistando en bodega"), USUARIO
        )
        creados += 1

    # Pedido 2: pendiente y sin moverse desde hace 4 días → dispara el aviso
    # "pedidos abiertos sin avanzar" (umbral: 3 días).
    texto = nota("pedido pendiente")
    if not existe(db, Pedido, tenant_id, texto):
        pedido = svc_ventas.crear_pedido(
            db,
            tenant_id,
            sv.PedidoCreate(
                cliente_nombre="Colegio San Martín",
                cliente_telefono="6017654321",
                cliente_direccion="Carrera 15 # 100-22, Bogotá",
                fecha=ahora,
                fecha_entrega=ahora + timedelta(days=5),
                prioridad="media",
                notas=texto,
                items=[
                    sv.ItemCreate(producto_id=productos["DEMO-LEC-001"].id, cantidad=40, precio_unitario=productos["DEMO-LEC-001"].precio),
                    sv.ItemCreate(producto_id=productos["DEMO-PAP-001"].id, cantidad=30, precio_unitario=productos["DEMO-PAP-001"].precio),
                ],
            ),
            USUARIO,
        )
        # El esquema no deja registrar un pedido con fecha pasada; se lleva
        # atrás DESPUÉS de crearlo para simular que lleva días sin avanzar.
        antes = ahora - timedelta(days=4)
        pedido.fecha = antes
        pedido.created_at = antes
        for evento in pedido.eventos:
            evento.created_at = antes
        db.commit()
        creados += 1

    return creados


def cargar_demo(db, tenant_id, ahora):
    """Carga lo que falte y lleva todas las fechas a "hoy". La usan main() y
    tests/test_seed_demo.py, para que la prueba corra EXACTAMENTE lo mismo."""
    categorias, n_cat = cargar_catalogo(db, tenant_id, Categoria, CATEGORIAS, sc.CategoriaCreate)
    marcas, n_mar = cargar_catalogo(db, tenant_id, Marca, MARCAS, sc.MarcaCreate)
    productos, n_prod = cargar_productos(db, tenant_id, categorias, marcas)
    proveedores, n_prov = cargar_proveedores(db, tenant_id, productos)
    n_com, n_ven = cargar_compras_y_ventas(db, tenant_id, proveedores, productos, ahora)
    n_ped = cargar_pedidos(db, tenant_id, productos, ahora)
    n_fechas = reanclar_fechas(db, tenant_id, ahora)
    return {
        "productos": productos, "categorias": n_cat, "marcas": n_mar, "n_productos": n_prod,
        "proveedores": n_prov, "compras": n_com, "ventas": n_ven, "pedidos": n_ped, "reanclados": n_fechas,
    }


def main():
    parser = argparse.ArgumentParser(description="Carga datos de ejemplo para una empresa existente")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--email", help="Correo de un usuario: se carga en SU empresa")
    grupo.add_argument("--tenant-id", help="UUID de la empresa (opcional si solo hay una)")
    args = parser.parse_args()

    # Igual que created_at en la base: UTC sin zona.
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    db = SessionLocal()
    try:
        tenant = elegir_tenant(db, args.tenant_id, args.email)
        tid = tenant.id

        r = cargar_demo(db, tid, ahora)
        productos = r["productos"]
        n_cat, n_mar, n_prod, n_prov = r["categorias"], r["marcas"], r["n_productos"], r["proveedores"]
        n_com, n_ven, n_ped, n_fechas = r["compras"], r["ventas"], r["pedidos"], r["reanclados"]

        print(f"✔ Empresa '{tenant.nombre_empresa}' (id={tid})")
        print(f"   Nuevos en esta corrida: {n_cat} categorías, {n_mar} marcas, {n_prod} productos, "
              f"{n_prov} proveedores, {n_com} compras, {n_ven} ventas, {n_ped} pedidos")
        print(f"   Fechas llevadas a hoy: {n_fechas} documentos (ventas hoy, esta semana, este mes y los últimos 6 meses)")
        print("   Stock resultante:")
        for p in PRODUCTOS:
            prod = productos[p["sku"]]
            db.refresh(prod)
            marca = "  ← bajo el mínimo" if prod.stock < prod.stock_minimo else ""
            print(f"     {prod.sku:<14} {prod.nombre:<26} {prod.stock:>4} (mínimo {prod.stock_minimo}){marca}")
    except Exception as e:
        db.rollback()
        print(f"✘ Error cargando datos de ejemplo: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
