"""
DATOS DE DEMOSTRACIÓN (2026-10-12) — dos restaurantes completos para ver y
probar cada pantalla, el dashboard, los reportes, la IA y la vista de cada rol.

    · "Donde Tavo" (universitario): 90 días de historia.
    · "Café Central": pequeño, para comprobar que ninguno ve los datos del otro.

TODO PASA POR LA LÓGICA DEL SISTEMA: las mismas funciones que usa la API
(crear insumos y platos con receta, comprar, tomar órdenes que descuentan
insumos, cocina, entregar, cobrar en caja, cerrar caja, mermas, conteo,
gastos). Nada de existencias, costos ni totales escritos a mano: por eso el
inventario, los costos y las utilidades cuadran de verdad. Los eventos se
ejecutan en ORDEN CRONOLÓGICO con su fecha (`ahora=`), así cada movimiento
queda en su día y la existencia nunca pasa por negativo.

FECHAS RELATIVAS A HOY, en hora de Colombia: hay datos de hoy, de la semana,
del mes y de los últimos 90 días. Hoy hay órdenes en todos los estados
(entrantes, en preparación, listas, entregadas por cobrar, cobradas y una
anulada) y la caja de hoy está abierta.

HISTORIAS QUE LA IA Y EL DASHBOARD DEBEN ENCONTRAR (no son datos planos):
    1. Demanda alta de lunes a jueves, menor el viernes, muy baja el sábado y
       casi nada el domingo; picos a las 7 a. m. y de 12 a 2 p. m.
    2. Hace ~5 semanas, semana de parciales: más órdenes y muchas más comidas
       rápidas. La semana pasada, floja (inicio de vacaciones).
    3. "Almuerzo ejecutivo" y "Hamburguesa clásica": se venden mucho y dejan
       poco margen.
    4. "Arroz con leche" casi no se vende.
    5. La carne de res subió ~30 % hace un mes: bajó el margen de la
       hamburguesa, la bandeja y la carne asada.
    6. Mermas anormales de lechuga en las últimas 2 semanas.
    7. Las 3 diferencias de caja del mes son del turno de la misma cajera.
    8. El queso mozzarella se acaba en pocos días al ritmo actual.

IDEMPOTENTE: si la demo ya está al día (tiene órdenes de hoy) no hace nada;
si es de otro día, la recrea con fechas de hoy. `--reset` la borra y la
recrea siempre. Solo toca las dos empresas de demostración.

SOLO EN DESARROLLO: con ENV=production se niega a correr.

Uso (desde backend/, con su entorno virtual):
    venv\\Scripts\\python ..\\automatizaciones\\deploy\\seed_demo.py
    venv\\Scripts\\python ..\\automatizaciones\\deploy\\seed_demo.py --reset
"""
import argparse
import io
import random
import sys
import time as reloj
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_UP, Decimal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # bajo pytest stdout es un objeto de captura
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import update  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.errors import AppError, ConflictError  # noqa: E402
from app.core.tiempo import ahora_utc  # noqa: E402
from app.core.validaciones import digito_verificacion_nit  # noqa: E402
from app.db.models import Tenant  # noqa: E402
from app.db.session import Base, SessionLocal  # noqa: E402
from app.modules.ajustes import router as r_ajustes, schemas as s_ajustes  # noqa: E402
from app.modules.caja import schemas as s_caja, services as caja  # noqa: E402
from app.modules.catalogo import recetas, router as r_catalogo, schemas as s_cat  # noqa: E402
from app.modules.catalogo.models import Producto  # noqa: E402
from app.modules.catalogo.services import opciones_carga_producto  # noqa: E402
from app.modules.cocina import services as cocina  # noqa: E402
from app.modules.compras import router as r_compras, schemas as s_compras, services as compras  # noqa: E402
from app.modules.gastos import schemas as s_gastos, services as gastos  # noqa: E402
from app.modules.inventario import router as r_inv, schemas as s_inv, services as inventario  # noqa: E402
from app.modules.inventario.models import Insumo  # noqa: E402
from app.modules.ordenes import models as m_ordenes, schemas as s_ord, services as ordenes  # noqa: E402
from app.modules.seguridad import alta, router as r_seg, schemas as s_seg  # noqa: E402
from app.modules.seguridad.models import Rol, Usuario  # noqa: E402

COLOMBIA = timedelta(hours=-5)


def salir(mensaje: str):
    print(f"✖ {mensaje}")
    sys.exit(1)


def utc(dia: date, hora: int, minuto: int = 0, segundo: int = 0) -> datetime:
    """Hora de Colombia → UTC sin zona (como las columnas)."""
    return datetime(dia.year, dia.month, dia.day, hora, minuto, segundo) - COLOMBIA


def nit(base: str) -> str:
    return f"{base}-{digito_verificacion_nit(base)}"


# ===========================================================================
# Donde Tavo: catálogo
# ===========================================================================
EMPRESA = {
    "nombre": "Donde Tavo",
    "nit": nit("901234567"),
    "direccion": "Universidad, bloque de cafeterías, local 3",
    "ciudad": "Bogotá",
    "telefono": "6017004455",
    "correo": "contacto@dondetavo.demo",
}
# (clave, correo, contraseña, nombre, rol)
USUARIOS = [
    ("admin", "admin@dondetavo.demo", "Tavo2026*Admin", "Gustavo Rincón", "Administrador"),
    ("caja", "caja@dondetavo.demo", "Tavo2026*Caja", "Carla Ruiz", "Cajero"),
    ("mesero", "mesero@dondetavo.demo", "Tavo2026*Mesero", "Marta Gómez", "Mesero"),
    ("mesero2", "mesero2@dondetavo.demo", "Tavo2026*Mesero", "Andrés Pérez", "Mesero"),
    ("mesero3", "mesero3@dondetavo.demo", "Tavo2026*Mesero", "Luisa Torres", "Mesero"),
    ("cocina", "cocina@dondetavo.demo", "Tavo2026*Cocina", "Óscar Díaz", "Cocinero"),
    ("cocina2", "cocina2@dondetavo.demo", "Tavo2026*Cocina", "Rosa Medina", "Cocinero"),
]
CATEGORIAS = [("Desayunos", 1), ("Almuerzos", 2), ("Rápidas", 3), ("Bebidas", 4), ("Postres", 5)]

# clave: (nombre, unidad, grupo, costo base por unidad, mínimo, proveedor)
INSUMOS = {
    "arroz": ("Arroz", "kg", "Abarrotes", 4200, 12, "andina"),
    "frijol": ("Fríjol", "kg", "Abarrotes", 7200, 5, "andina"),
    "aceite": ("Aceite", "L", "Abarrotes", 9800, 8, "andina"),
    "azucar": ("Azúcar", "kg", "Abarrotes", 4600, 4, "andina"),
    "cafe": ("Café molido", "g", "Abarrotes", 46, 1500, "andina"),
    "harina": ("Harina de trigo", "kg", "Abarrotes", 3900, 3, "andina"),
    "gaseosa": ("Gaseosa 400 ml", "unidad", "Bebidas", 1600, 60, "andina"),
    "agua": ("Agua 600 ml", "unidad", "Bebidas", 1100, 30, "andina"),
    "salchicha": ("Salchicha", "unidad", "Carnes", 1150, 30, "carnes"),
    "res": ("Carne de res", "kg", "Carnes", 22000, 6, "carnes"),
    "pollo": ("Pechuga de pollo", "kg", "Carnes", 17500, 8, "carnes"),
    "costilla": ("Costilla de res", "kg", "Carnes", 16000, 3, "carnes"),
    "huevo": ("Huevo", "unidad", "Lácteos y panadería", 560, 90, "lacteos"),
    "leche": ("Leche", "L", "Lácteos y panadería", 4300, 15, "lacteos"),
    "queso": ("Queso mozzarella", "kg", "Lácteos y panadería", 24500, 4, "lacteos"),
    "arepa": ("Arepa", "unidad", "Lácteos y panadería", 650, 50, "lacteos"),
    "pan": ("Pan de hamburguesa", "unidad", "Lácteos y panadería", 820, 40, "lacteos"),
    "papa": ("Papa pastusa", "kg", "Fruver", 2700, 25, "fruver"),
    "platano": ("Plátano", "unidad", "Fruver", 950, 40, "fruver"),
    "tomate": ("Tomate", "kg", "Fruver", 4100, 6, "fruver"),
    "cebolla": ("Cebolla cabezona", "kg", "Fruver", 3200, 5, "fruver"),
    "lechuga": ("Lechuga", "unidad", "Fruver", 2600, 8, "fruver"),
    "mora": ("Mora", "kg", "Fruver", 9200, 3, "fruver"),
    "fresa": ("Fresa", "kg", "Fruver", 10500, 3, "fruver"),
    "limon": ("Limón", "unidad", "Fruver", 350, 30, "fruver"),
}
# La carne de res sube en el último mes (historia 5).
PRECIO_RES_ALZA = 28600
DIAS_ALZA = 30

# clave: (tipo, nombre o razón social, documento, extra)
PROVEEDORES = {
    "andina": {"tipo_persona": "juridica", "nit": nit("900456789"), "razon_social": "Distribuidora Andina SAS",
               "representante_nombre": "Claudia Herrera", "telefono": "6015558899", "email": "pedidos@andina.demo",
               "direccion": "Calle 13 # 68-40, Bogotá"},
    "carnes": {"tipo_persona": "juridica", "nit": nit("900765432"), "razon_social": "Carnes El Llano SAS",
               "representante_nombre": "Hernán Castro", "telefono": "3104445566", "email": "ventas@carneselllano.demo",
               "direccion": "Av. Las Américas # 50-12, Bogotá"},
    "lacteos": {"tipo_persona": "natural", "tipo_documento": "CC", "numero_documento": "52345678", "nombres": "María Fernanda",
                "apellidos": "Ortiz", "telefono": "3157778899", "email": "mfortiz@lacteos.demo", "direccion": "Plaza de Paloquemao, local 22"},
    "fruver": {"tipo_persona": "natural", "tipo_documento": "CC", "numero_documento": "79876543", "nombres": "Pedro",
               "apellidos": "Gómez", "telefono": "3209990011", "email": "pedrogomez@fruver.demo", "direccion": "Corabastos, bodega 18"},
}
# Cada cuántos días le compra el restaurante a cada uno (≈ 30 compras en 90 días).
CADENCIA = {"fruver": 8, "carnes": 12, "lacteos": 12, "andina": 16}
# El tomate también lo vende la Andina, más caro: la última compra de tomate
# fue con ella (la IA sugiere volver con Pedro).
TOMATE_ANDINA = 4950

# Platos: nombre → (categoría, precio, descripción, va a cocina, receta, modificadores)
# receta: (insumo, cantidad, unidad, merma %); modificador: (tipo, nombre, precio, insumo, cantidad, unidad)
PLATOS = {
    "Huevos pericos": ("Desayunos", 8500, "Con arepa y tomate", True,
                       [("huevo", 2, "unidad", 0), ("tomate", 40, "g", 0), ("cebolla", 25, "g", 0), ("aceite", 10, "ml", 0), ("arepa", 1, "unidad", 0)],
                       [("sin", "Sin cebolla", 0, "cebolla", None, None), ("extra", "Extra huevo", 1800, "huevo", 1, "unidad")]),
    "Calentado paisa": ("Desayunos", 12000, "Arroz, fríjol, huevo y arepa", True,
                        [("arroz", 120, "g", 0), ("frijol", 100, "g", 0), ("huevo", 1, "unidad", 0), ("arepa", 1, "unidad", 0), ("aceite", 15, "ml", 0)],
                        [("extra", "Extra huevo", 1800, "huevo", 1, "unidad")]),
    "Arepa con queso": ("Desayunos", 6500, "Arepa asada con mozzarella", True,
                        [("arepa", 1, "unidad", 0), ("queso", 60, "g", 0)],
                        [("extra", "Extra queso", 2500, "queso", 40, "g")]),
    "Almuerzo ejecutivo": ("Almuerzos", 11500, "Arroz, pollo, fríjol, maduro y ensalada", True,
                           [("arroz", 150, "g", 0), ("pollo", 150, "g", 0), ("frijol", 80, "g", 0), ("platano", 1, "unidad", 0),
                            ("lechuga", "0.1", "unidad", 0), ("tomate", 30, "g", 0), ("aceite", 15, "ml", 0)],
                           [("sin", "Sin ensalada", 0, "lechuga", None, None)]),
    "Bandeja del día": ("Almuerzos", 19000, "Carne, arroz, fríjol, huevo, maduro y arepa", True,
                        [("arroz", 150, "g", 0), ("res", 180, "g", 0), ("frijol", 120, "g", 0), ("platano", 1, "unidad", 0),
                         ("huevo", 1, "unidad", 0), ("arepa", 1, "unidad", 0), ("aceite", 20, "ml", 0)],
                        [("sin", "Sin huevo", 0, "huevo", None, None)]),
    "Arroz con pollo": ("Almuerzos", 14000, "Con papa a la francesa", True,
                        [("arroz", 180, "g", 0), ("pollo", 140, "g", 0), ("cebolla", 30, "g", 0), ("tomate", 30, "g", 0), ("aceite", 15, "ml", 0)], []),
    "Pollo a la plancha": ("Almuerzos", 16000, "Pechuga con papa y ensalada", True,
                           [("pollo", 220, "g", 0), ("papa", 200, "g", 10), ("lechuga", "0.15", "unidad", 0), ("tomate", 50, "g", 0), ("limon", "0.5", "unidad", 0)],
                           [("sin", "Sin ensalada", 0, "lechuga", None, None)]),
    "Carne asada": ("Almuerzos", 18000, "Con papa y ensalada", True,
                    [("res", 200, "g", 0), ("papa", 200, "g", 10), ("lechuga", "0.1", "unidad", 0), ("aceite", 10, "ml", 0), ("limon", "0.5", "unidad", 0)], []),
    "Sopa de costilla": ("Almuerzos", 9000, "Caldo de costilla con papa", True,
                         [("costilla", 150, "g", 0), ("papa", 150, "g", 10), ("cebolla", 30, "g", 0)], []),
    "Hamburguesa clásica": ("Rápidas", 13500, "Carne de res, queso, tomate y lechuga", True,
                            [("pan", 1, "unidad", 0), ("res", 140, "g", 0), ("queso", 30, "g", 0), ("tomate", 30, "g", 0),
                             ("lechuga", "0.1", "unidad", 0), ("cebolla", 20, "g", 0)],
                            [("sin", "Sin cebolla", 0, "cebolla", None, None), ("sin", "Sin tomate", 0, "tomate", None, None),
                             ("extra", "Extra queso", 2500, "queso", 30, "g")]),
    "Salchipapa": ("Rápidas", 10000, "Salchicha y papas a la francesa", True,
                   [("salchicha", 1, "unidad", 0), ("papa", 250, "g", 10), ("aceite", 30, "ml", 0)],
                   [("extra", "Extra queso", 2500, "queso", 30, "g")]),
    "Papas a la francesa": ("Rápidas", 6000, "Porción grande", True, [("papa", 250, "g", 10), ("aceite", 30, "ml", 0)], []),
    "Gaseosa 400 ml": ("Bebidas", 4000, "Fría, de botella", False, [("gaseosa", 1, "unidad", 0)], []),
    "Agua 600 ml": ("Bebidas", 3000, "Sin gas", False, [("agua", 1, "unidad", 0)], []),
    "Jugo de mora": ("Bebidas", 5500, "En agua o en leche", True, [("mora", 150, "g", 0), ("azucar", 25, "g", 0)], []),
    "Jugo de fresa": ("Bebidas", 5500, "En agua o en leche", True, [("fresa", 150, "g", 0), ("azucar", 25, "g", 0)], []),
    "Tinto": ("Bebidas", 1800, "Café de la casa", True, [("cafe", 10, "g", 0), ("azucar", 8, "g", 0)], []),
    "Café con leche": ("Bebidas", 3800, "Grande", True, [("cafe", 12, "g", 0), ("leche", 180, "ml", 0), ("azucar", 10, "g", 0)], []),
    "Brownie de la casa": ("Postres", 5000, "Tibio", True, [("harina", 50, "g", 0), ("azucar", 40, "g", 0), ("huevo", 1, "unidad", 0), ("leche", 30, "ml", 0)], []),
    "Arroz con leche": ("Postres", 4500, "Receta de la abuela", True, [("arroz", 50, "g", 0), ("leche", 200, "ml", 0), ("azucar", 30, "g", 0)], []),
}
# (nombre, precio, componentes, días de la semana (0 = lunes) o None, desde (días atrás), hasta (días atrás) o None)
COMBOS = [
    ("Combo estudiante almuerzo", 14500, [("Almuerzo ejecutivo", 1), ("Jugo de fresa", 1)], [0, 1, 2, 3, 4], 75, None),
    ("Combo estudiante desayuno", 9000, [("Huevos pericos", 1), ("Tinto", 1)], None, 60, None),
    ("Combo parciales", 19000, [("Hamburguesa clásica", 1), ("Papas a la francesa", 1), ("Gaseosa 400 ml", 1)], None, "parciales", "parciales"),
]
PLATO_INACTIVO, DIAS_INACTIVO = "Sopa de costilla", 45
PLATO_AGOTADO = "Jugo de mora"  # su insumo, la mora, se acabó (historia de "agotado hoy")
PLATO_RARO = "Arroz con leche"  # casi no se vende (historia 4)

# Existencia objetivo al terminar, en días de consumo reciente (o fija).
DIAS_OBJETIVO = {"queso": 3, "lechuga": 2.5, "leche": 2}  # bajo el mínimo (historias 8 y 6)
SIN_EXISTENCIA = {"mora"}

# ===========================================================================
# Demanda
# ===========================================================================
ORDENES_POR_DIA = {0: 36, 1: 35, 2: 35, 3: 33, 4: 24, 5: 10, 6: 3}  # lunes = 0 (historia 1)
PESO_HORA = {6: .6, 7: 2.6, 8: 1.4, 9: .7, 10: .6, 11: 1.3, 12: 3.2, 13: 3.0, 14: 1.3, 15: .6, 16: .9, 17: .7, 18: .4, 19: .2}
PESO_HORA_SABADO = {8: 1, 9: 1, 10: 1, 11: 1.2, 12: 1.6, 13: 1.4, 14: .8}
PESO_HORA_DOMINGO = {10: 1, 11: 1, 12: 1.2}
SEMANAS_ATRAS_PARCIALES = 5  # semanas completas antes de la actual (historia 2)
SEMANAS_ATRAS_FLOJA = 1
MIN_COBRADAS_HOY = 5
MENU = {
    "desayuno": ([("Huevos pericos", 30), ("Calentado paisa", 25), ("Arepa con queso", 30)], [("Tinto", 45), ("Café con leche", 45), ("Jugo de fresa", 6), ("Jugo de mora", 4)]),
    "almuerzo": ([("Almuerzo ejecutivo", 40), ("Hamburguesa clásica", 16), ("Bandeja del día", 16), ("Arroz con pollo", 15), ("Pollo a la plancha", 11), ("Carne asada", 9), ("Sopa de costilla", 6)],
                 [("Gaseosa 400 ml", 35), ("Jugo de mora", 14), ("Jugo de fresa", 14), ("Agua 600 ml", 15), (None, 22)]),
    "tarde": ([("Hamburguesa clásica", 45), ("Salchipapa", 25), ("Papas a la francesa", 30)], [("Gaseosa 400 ml", 50), ("Agua 600 ml", 15), ("Tinto", 10), (None, 25)]),
}
MOTIVOS_ANULACION = ["El cliente se fue antes de que saliera", "Orden duplicada por error", "El cliente cambió de opinión"]
CLIENTES = ["Valentina Ríos", "Santiago Mejía", "Camila Vargas", "Juan David Rojas", "Daniela Cárdenas", "Felipe Osorio",
            "Laura Salazar", "Mateo Quintero", "Sara Londoño", "Nicolás Herrera", "Isabella Muñoz", "Tomás Arango"]
DIRECCIONES = ["Bloque 7, oficina 302", "Biblioteca central, piso 2", "Edificio de Ingeniería, sala 4", "Residencias, torre B apto 12",
               "Calle 45 # 13-20", "Carrera 7 # 40-62, apto 501"]
MEDIOS = [("efectivo", 42), ("nequi", 22), ("tarjeta", 14), ("daviplata", 12), ("transferencia", 10)]


def elegir(rng, opciones):
    return rng.choices([o for o, _ in opciones], weights=[p for _, p in opciones], k=1)[0]


@dataclass
class OrdenPlan:
    t: datetime
    tipo: str
    origen: str
    toma: str  # clave del usuario que la tomó
    items: list  # [(producto, cantidad, [nombres de modificadores], nota)]
    mesa: str | None = None
    cliente: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    destino: str = "cobrada"  # cobrada | anulada | entrante | en_preparacion | lista | entregada
    t_tomar: datetime | None = None
    t_lista: datetime | None = None
    t_entrega: datetime | None = None
    t_cobro: datetime | None = None
    pagos: list = field(default_factory=list)  # [(medio, fracción)]
    propina: bool = False
    anular_item: str | None = None
    id: object = None


def semana_de(hoy: date, semanas_atras: int) -> range:
    """Días atrás que cubre una semana de calendario (lunes a domingo)."""
    lunes = hoy.weekday() + 7 * semanas_atras
    return range(lunes - 6, lunes + 1)


def planear_ordenes(rng, hoy: date, ahora_local: datetime, dias: int) -> list[OrdenPlan]:
    planes: list[OrdenPlan] = []
    parciales, floja = semana_de(hoy, SEMANAS_ATRAS_PARCIALES), semana_de(hoy, SEMANAS_ATRAS_FLOJA)
    for atras in range(dias, -1, -1):
        dia = hoy - timedelta(days=atras)
        wd = dia.weekday()
        n = ORDENES_POR_DIA[wd] * rng.uniform(0.85, 1.15)
        if atras in parciales:
            n *= 1.3
        if atras in floja:
            n *= 0.55
        pesos = PESO_HORA_SABADO if wd == 5 else PESO_HORA_DOMINGO if wd == 6 else PESO_HORA
        if atras == 0:  # hoy: solo hasta ahora
            limite = ahora_local.hour + ahora_local.minute / 60
            pesos = {h: p * min(1, max(0, limite - h)) for h, p in pesos.items()}
            if sum(pesos.values()) == 0:
                continue
            n *= sum(pesos.values()) / sum((PESO_HORA_SABADO if wd == 5 else PESO_HORA_DOMINGO if wd == 6 else PESO_HORA).values())
        n = max(1, round(n)) if wd != 6 or rng.random() < 0.6 else 0
        horas = list(pesos)
        for _ in range(n):
            h = rng.choices(horas, weights=[pesos[x] for x in horas], k=1)[0]
            minuto = rng.randint(0, 59)
            t = utc(dia, h, minuto, rng.randint(0, 59))
            if atras == 0 and t > ahora_local - COLOMBIA - timedelta(minutes=3):
                t = ahora_local - COLOMBIA - timedelta(minutes=rng.randint(4, 30))
            planes.append(armar_orden(rng, t, h, wd, atras, atras in parciales))
    planes.sort(key=lambda p: p.t)
    return planes


def armar_orden(rng, t: datetime, hora: int, wd: int, atras: int, en_parciales: bool = False) -> OrdenPlan:
    franja = "desayuno" if hora < 11 else "almuerzo" if hora < 15 else "tarde"
    if en_parciales and franja == "almuerzo" and rng.random() < 0.35:
        franja = "tarde"  # en parciales se come rápido (historia 2)
    principales, bebidas = MENU[franja]
    items = []
    combo = None
    if wd < 5 and franja == "almuerzo" and atras <= 75 and rng.random() < 0.18:
        combo = "Combo estudiante almuerzo"
    elif franja == "desayuno" and atras <= 60 and rng.random() < 0.15:
        combo = "Combo estudiante desayuno"
    elif franja == "tarde" and en_parciales and rng.random() < 0.35:
        combo = "Combo parciales"
    if combo:
        items.append((combo, 1, [], None))
    else:
        opciones = [(p, w) for p, w in principales if not (p == PLATO_INACTIVO and atras <= DIAS_INACTIVO)]
        principal = elegir(rng, opciones)
        mods = []
        if PLATOS[principal][5] and rng.random() < 0.22:
            mods = [rng.choice(PLATOS[principal][5])[1]]
        nota = rng.choice(["Bien cocido", "Sin sal", "Para llevar en icopor", None, None, None, None, None]) if rng.random() < 0.08 else None
        items.append((principal, 2 if rng.random() < 0.12 else 1, mods, nota))
        bebida = elegir(rng, [(b, w) for b, w in bebidas if not (b == PLATO_AGOTADO and atras == 0)])
        if bebida:
            items.append((bebida, 1, [], None))
    if franja in ("almuerzo", "tarde") and rng.random() < 0.12:
        items.append(("Brownie de la casa", 1, [], None))
    elif franja in ("almuerzo", "tarde") and rng.random() < 0.002:
        items.append((PLATO_RARO, 1, [], None))
    tipo = elegir(rng, [("local", 62), ("llevar", 28), ("domicilio", 10)])
    p = OrdenPlan(t=t, tipo=tipo, origen="local", toma="caja", items=items)
    if tipo == "local":
        p.toma = elegir(rng, [("mesero", 45), ("mesero2", 35), ("mesero3", 20)])
        p.mesa = rng.choice([f"S{i}" for i in range(1, 9)] + [f"T{i}" for i in range(1, 5)])
        p.propina = rng.random() < 0.3
    elif tipo == "domicilio":
        p.origen = elegir(rng, [("llamada", 55), ("whatsapp", 45)])
        p.cliente = rng.choice(CLIENTES)
        p.telefono = f"3{rng.randint(0, 2)}{rng.randint(10000000, 99999999)}"
        p.direccion = rng.choice(DIRECCIONES)
    elif rng.random() < 0.5:
        p.cliente = rng.choice(CLIENTES)
    p.t_tomar = t + timedelta(minutes=rng.uniform(1, 5))
    p.t_lista = p.t_tomar + timedelta(minutes=rng.uniform(6, 16))
    p.t_entrega = p.t_lista + timedelta(minutes=rng.uniform(1, 4) if tipo != "domicilio" else rng.uniform(15, 30))
    p.t_cobro = p.t_entrega + timedelta(minutes=rng.uniform(10, 40) if tipo == "local" else rng.uniform(0, 3))
    medio = elegir(rng, MEDIOS)
    p.pagos = [(medio, 1)] if rng.random() > 0.08 else [(medio, 0.5), ("efectivo" if medio != "efectivo" else "nequi", 0.5)]
    if rng.random() < 0.012:
        p.destino = "anulada"
    elif len(items) > 1 and rng.random() < 0.01:
        p.anular_item = items[-1][0]
    return p


# ===========================================================================
# Borrar y crear
# ===========================================================================
def borrar_empresa(db, tenant_id) -> None:
    """Borra TODO lo de una empresa de demostración (y nada más)."""
    db.execute(update(m_ordenes.OrdenItem).where(m_ordenes.OrdenItem.tenant_id == tenant_id).values(venta_id=None))
    for tabla in reversed(Base.metadata.sorted_tables):
        if "tenant_id" in tabla.c and tabla.name != "tenants":
            db.execute(tabla.delete().where(tabla.c.tenant_id == tenant_id))
    db.execute(Tenant.__table__.delete().where(Tenant.id == tenant_id))
    db.commit()


def tenant_de(db, correo) -> Tenant | None:
    u = db.query(Usuario).filter(Usuario.email == correo).first()
    return db.get(Tenant, u.tenant_id) if u else None


def al_dia(db, tenant: Tenant, hoy: date) -> bool:
    return db.query(m_ordenes.Orden.id).filter(m_ordenes.Orden.tenant_id == tenant.id, m_ordenes.Orden.jornada == hoy).first() is not None


def logo_png(texto: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (512, 512), (24, 24, 27))
    d = ImageDraw.Draw(img)
    d.ellipse([70, 70, 442, 442], outline=(255, 255, 255), width=14)
    try:
        fuente = ImageFont.truetype("arialbd.ttf", 150)
    except OSError:
        fuente = ImageFont.load_default()
    caja_t = d.textbbox((0, 0), texto, font=fuente)
    d.text(((512 - (caja_t[2] - caja_t[0])) / 2 - caja_t[0], (512 - (caja_t[3] - caja_t[1])) / 2 - caja_t[1]), texto, font=fuente, fill=(255, 255, 255))
    salida = io.BytesIO()
    img.save(salida, format="PNG")
    return salida.getvalue()


def crear_usuarios(db, tenant, admin, lista) -> dict:
    roles = {r.nombre: r for r in db.query(Rol).filter(Rol.tenant_id == tenant.id)}
    usuarios = {"admin": admin}
    for clave, correo, clave_acceso, nombre, rol in lista:
        if clave == "admin":
            continue
        r_seg.crear_usuario(s_seg.UsuarioCreate(nombre_completo=nombre, email=correo, password=clave_acceso, rol_id=roles[rol].id), db=db, actor=admin)
        usuarios[clave] = db.query(Usuario).filter(Usuario.email == correo).one()
    return usuarios


def configurar(db, tenant, zonas_mesas, impresoras=True):
    config = s_ajustes.ConfiguracionRestaurante(
        alerta_cocina_minutos=15, jornada=s_ajustes.Jornada(inicio="05:00", fin="22:00"),
        impresoras=[s_ajustes.Impresora(nombre="Cocina", uso="comanda", ancho_mm=80), s_ajustes.Impresora(nombre="Caja", uso="factura", ancho_mm=80)] if impresoras else [],
    )
    r_ajustes.editar_configuracion(config, db=db, tenant_id=tenant.id)
    mesas = {}
    for i, (zona, nombres) in enumerate(zonas_mesas.items()):
        z = r_ajustes.crear_zona(s_ajustes.ZonaCreate(nombre=zona, orden=i), db=db, tenant_id=tenant.id)
        for n in nombres:
            m = r_ajustes.crear_mesa(s_ajustes.MesaCreate(nombre=n, zona_id=z["id"] if isinstance(z, dict) else z.id, puestos=4), db=db, tenant_id=tenant.id)
            mesas[n] = m["id"] if isinstance(m, dict) else m.id
    return mesas


def _id(x):
    return x["id"] if isinstance(x, dict) else x.id


# ===========================================================================
# Donde Tavo
# ===========================================================================
def sembrar_donde_tavo(db, hoy: date, ahora: datetime, dias: int, rng, escala: float = 1.0) -> dict:
    inicio = hoy - timedelta(days=dias + 1)
    t_inicio = utc(inicio, 5, 30)
    clave_admin = USUARIOS[0]
    tenant, admin = alta.crear_empresa(db, EMPRESA["nombre"], clave_admin[1], clave_admin[2], nombre_admin=clave_admin[3])
    r_ajustes.editar_negocio(s_ajustes.NegocioUpdate(nombre_empresa=EMPRESA["nombre"], nit=EMPRESA["nit"], direccion=EMPRESA["direccion"],
                             ciudad=EMPRESA["ciudad"], telefono=EMPRESA["telefono"], correo=EMPRESA["correo"]), db=db, tenant_id=tenant.id)
    r_ajustes.subir_logo(archivo=(logo_png("DT"), "image/png"), db=db, tenant_id=tenant.id)
    usuarios = crear_usuarios(db, tenant, admin, USUARIOS)
    mesas = configurar(db, tenant, {"Salón": [f"S{i}" for i in range(1, 9)], "Terraza": [f"T{i}" for i in range(1, 5)]})

    cats = {}
    for nombre, orden in CATEGORIAS:
        cats[nombre] = _id(r_catalogo.crear_categoria(s_cat.CategoriaCreate(nombre=nombre, orden=orden), db=db, tenant_id=tenant.id))
    ins = {}
    for clave, (nombre, unidad, grupo, costo, minimo, _) in INSUMOS.items():
        ins[clave] = _id(r_inv.crear_insumo(s_inv.InsumoCreate(nombre=nombre, unidad=unidad, grupo=grupo, minimo=Decimal(str(minimo)), costo_unitario=Decimal(str(costo))), db=db, usuario=admin))
    provs = {}
    for clave, datos in PROVEEDORES.items():
        surtidos = [ins[k] for k, v in INSUMOS.items() if v[5] == clave] + ([ins["tomate"]] if clave == "andina" else [])
        provs[clave] = _id(r_compras.crear_proveedor(s_compras.ProveedorCreate(**datos, insumo_ids=surtidos), db=db, tenant_id=tenant.id))
    platos = {}
    for nombre, (cat, precio, desc, cocina_, receta, mods) in PLATOS.items():
        payload = s_cat.ProductoCreate(
            nombre=nombre, precio=Decimal(precio), descripcion=desc, categoria_id=cats[cat], va_a_cocina=cocina_,
            receta=[s_cat.RecetaItemIn(insumo_id=ins[i], cantidad=Decimal(str(c)), unidad=u, merma_porcentaje=Decimal(m)) for i, c, u, m in receta],
            modificadores=[s_cat.ModificadorIn(tipo=t, nombre=n, precio=Decimal(p), insumo_id=ins[i] if i else None,
                                               cantidad=Decimal(str(c)) if c else None, unidad=u) for t, n, p, i, c, u in mods],
        )
        platos[nombre] = _id(r_catalogo.crear_producto(payload, db=db, usuario=admin))
    parciales = semana_de(hoy, SEMANAS_ATRAS_PARCIALES)
    for nombre, precio, comps, dias_sem, desde, hasta in COMBOS:
        desde = parciales[-1] if desde == "parciales" else desde
        hasta = parciales[0] if hasta == "parciales" else hasta
        payload = s_cat.ProductoCreate(
            tipo="combo", nombre=nombre, precio=Decimal(precio), categoria_id=cats["Almuerzos" if "almuerzo" in nombre else "Desayunos" if "desayuno" in nombre else "Rápidas"],
            descripcion="Promoción para estudiantes", dias_semana=dias_sem, vigente_desde=hoy - timedelta(days=desde),
            vigente_hasta=hoy - timedelta(days=hasta) if hasta is not None else None,
            componentes=[s_cat.ComboItemIn(producto_id=platos[p], cantidad=c) for p, c in comps],
        )
        platos[nombre] = _id(r_catalogo.crear_producto(payload, db=db, usuario=admin))
    db.query(Producto).filter(Producto.tenant_id == tenant.id).update({"created_at": t_inicio, "updated_at": t_inicio})
    db.query(Insumo).filter(Insumo.tenant_id == tenant.id).update({"created_at": t_inicio, "updated_at": t_inicio})
    db.commit()

    # ---------- Plan de órdenes y consumo previsto ----------
    ahora_local = ahora + COLOMBIA
    planes = planear_ordenes(rng, hoy, ahora_local, dias)
    if escala < 1:
        planes = [p for p in planes if rng.random() < escala or p.t.date() >= hoy - timedelta(days=1)]
    marcar_estados_de_hoy(rng, planes, hoy, ahora)
    productos = {p.id: p for p in db.query(Producto).options(*opciones_carga_producto()).filter(Producto.tenant_id == tenant.id)}
    por_nombre = {p.nombre: p for p in productos.values()}
    consumo_previsto = defaultdict(list)  # insumo_id → [(t, cantidad)]
    for p in planes:
        lineas = []
        for nombre, cant, mods, _ in p.items:
            prod = por_nombre[nombre]
            lineas.append(recetas.LineaVendida(prod, cant, [m for m in prod.modificadores if m.nombre in mods]))
        for insumo_id, c in recetas.consumo(lineas).items():
            consumo_previsto[insumo_id].append((p.t, Decimal(c)))
    mermas = planear_mermas(rng, hoy, dias, ins)
    for t, clave, cantidad, unidad, *_ in mermas:
        consumo_previsto[ins[clave]].append((t, Decimal(str(cantidad)) / (1000 if unidad in ("g", "ml") and INSUMOS[clave][1] in ("kg", "L") else 1)))

    # ---------- Eventos en orden cronológico ----------
    eventos = []  # (t, prioridad, tipo, datos)
    for clave in PROVEEDORES:
        dia = inicio
        while dia <= hoy:
            t = utc(dia, 5, 45)
            if t <= ahora:
                eventos.append((t, 0, "compra", clave))
            dia += timedelta(days=CADENCIA[clave])
    anulada_compra = utc(hoy - timedelta(days=50), 6, 5)
    eventos.append((anulada_compra, 0, "compra_duplicada", "andina"))
    dias_con_ordenes = sorted({(p.t + COLOMBIA).date() for p in planes})
    cajero_de = lambda d: "caja" if d.weekday() in (0, 2, 4, 5) else "admin"  # noqa: E731
    con_diferencia = [d for d in dias_con_ordenes if d < hoy and cajero_de(d) == "caja" and (hoy - d).days <= 25][-3:]
    diferencias = dict(zip(con_diferencia, (Decimal("-2000"), Decimal("-5000"), Decimal("-3500"))))
    for d in dias_con_ordenes:
        eventos.append((utc(d, 5, 50), 1, "abrir", d))
        if d < hoy:
            eventos.append((utc(d, 21, 15), 9, "cerrar", (d, diferencias.get(d))))
    for p in planes:
        eventos.append((p.t, 2, "orden", p))
        if p.destino == "anulada":
            eventos.append((p.t + timedelta(minutes=3), 3, "anular", p))
            continue
        if p.destino == "entrante":
            continue
        eventos.append((p.t_tomar, 3, "tomar", p))
        if p.anular_item:
            eventos.append((p.t_tomar + timedelta(seconds=30), 3, "anular_item", p))
        if p.destino == "en_preparacion":
            continue
        eventos.append((p.t_lista, 4, "finalizar", p))
        if p.destino == "lista":
            continue
        eventos.append((p.t_entrega, 5, "entregar", p))
        if p.destino == "entregada":
            continue
        eventos.append((p.t_cobro, 6, "cobrar", p))
    for t, clave, cantidad, unidad, motivo, detalle in mermas:
        eventos.append((t, 7, "merma", (clave, cantidad, unidad, motivo, detalle)))
    eventos.append((utc(hoy - timedelta(days=20), 20, 40), 8, "conteo", None))
    eventos.append((utc(hoy - timedelta(days=DIAS_INACTIVO), 21, 30), 8, "desactivar", PLATO_INACTIVO))
    for t, payload, de_caja in planear_gastos(hoy, dias):
        eventos.append((t, 7, "gasto", (payload, de_caja)))
    eventos.sort(key=lambda e: (e[0], e[1]))

    proximas = {clave: sorted(e[0] for e in eventos if e[2] == "compra" and e[3] == clave) for clave in PROVEEDORES}
    ultima_andina = proximas["andina"][-1]
    compras_de = {k: proximas[v[5]] for k, v in INSUMOS.items()}
    compras_de["tomate"] = [x for x in proximas["fruver"] if x < ultima_andina] + [ultima_andina]
    cuenta = defaultdict(int)
    for t, _, tipo, datos in eventos:
        if t > ahora:
            continue
        try:
            ejecutar(db, tenant, usuarios, mesas, platos, por_nombre, ins, provs, consumo_previsto, compras_de, hoy, ahora, t, tipo, datos, rng)
            cuenta[tipo] += 1
        except AppError as error:
            db.rollback()
            cuenta[f"{tipo} rechazada"] += 1
            if tipo not in ("orden",):
                print(f"   · {tipo} del {t + COLOMBIA:%d/%m %H:%M} no se pudo: {error.detail}")
    # Hoy: lo poco que quedó de mora se dañó, y el jugo de mora se marca
    # agotado (su insumo se acabó).
    mora = db.get(Insumo, ins["mora"])
    db.refresh(mora)
    if mora.existencia > 0:
        cuando = min(ahora - timedelta(minutes=30), utc(hoy, 7, 0)) if ahora > utc(hoy, 6, 0) else ahora - timedelta(minutes=1)
        inventario.registrar_merma(db, usuarios["cocina"], ins["mora"], s_inv.MermaCreate(cantidad=mora.existencia, unidad="kg", motivo="vencido",
                                   detalle="Se dañó la que quedaba"), ahora=cuando)
    ordenes.marcar_agotado(db, admin, platos[PLATO_AGOTADO])
    return {"tenant": tenant, "usuarios": usuarios, "cuenta": dict(cuenta), "ordenes_planeadas": len(planes)}


def marcar_estados_de_hoy(rng, planes, hoy, ahora):
    """Las últimas órdenes de hoy quedan en cada estado: la cocina, el
    tablero y la caja se ven vivos (y las mesas, ocupadas o por cobrar)."""
    de_hoy = [p for p in planes if (p.t + COLOMBIA).date() == hoy]
    if not de_hoy:
        return
    finales = [("entrante", "local", "S1"), ("entrante", "local", "S3"), ("entrante", "llevar", None),
               ("en_preparacion", "local", "S2"), ("en_preparacion", "domicilio", None),
               ("lista", "local", "T1"), ("lista", "llevar", None),
               ("entregada", "local", "S4"), ("entregada", "local", "S5")]
    # Al menos MIN_COBRADAS_HOY órdenes de hoy quedan cobradas (el dashboard
    # de "Hoy" nunca en cero); si temprano hay pocas, se dejan vivas las de
    # más prioridad (una por estado primero).
    cupo = max(0, min(len(finales), len(de_hoy) - MIN_COBRADAS_HOY))
    prioridad = [0, 3, 5, 7, 4, 2, 6, 8, 1]
    finales = [finales[i] for i in sorted(prioridad[:cupo])]
    recientes = de_hoy[len(de_hoy) - cupo:] if cupo else []
    for i, (p, (estado, tipo, mesa)) in enumerate(zip(recientes, finales)):
        p.destino = estado
        p.tipo, p.mesa = tipo, mesa
        p.t = ahora - timedelta(minutes=2 + 3 * (len(finales) - i) + (18 if estado == "entrante" and mesa == "S1" else 0))
        p.t_tomar = p.t + timedelta(minutes=1)
        p.t_lista = p.t_tomar + timedelta(minutes=1)
        p.t_entrega = p.t_lista + timedelta(minutes=1)
        if tipo == "local":
            p.toma = p.toma if p.toma.startswith("mesero") else "mesero"
            p.cliente = p.telefono = p.direccion = None
        elif tipo == "domicilio":
            p.origen, p.cliente, p.telefono, p.direccion = "whatsapp", "Camila Vargas", "3112223344", "Residencias, torre B apto 12"
        else:
            p.origen, p.toma = "local", "caja"
        p.anular_item = None
    for p in de_hoy[: len(de_hoy) - cupo]:
        # Las mesas S1–S5 y T1 quedan con UNA orden viva: las de antes, en otras.
        if p.mesa in {"S1", "S2", "S3", "S4", "S5", "T1"}:
            p.mesa = rng.choice(["S6", "S7", "S8", "T2", "T3", "T4"])
    anulables = [p for p in de_hoy[: len(de_hoy) - cupo] if p.destino == "cobrada"]
    if anulables and not any(p.destino == "anulada" for p in de_hoy):
        anulables[len(anulables) // 2].destino = "anulada"


def planear_mermas(rng, hoy, dias, ins):
    """Mermas normales (pocas, repartidas) y lechuga anormal en las últimas 2 semanas."""
    mermas = []
    for atras in range(dias, 0, -1):
        dia = hoy - timedelta(days=atras)
        if dia.weekday() == 6:
            continue
        if atras % 3 == 0:
            # Repartidas por turno (no al azar): ninguna se amontona en las
            # últimas dos semanas, que son la historia de la lechuga.
            clave, cantidad, unidad = [("tomate", rng.choice([300, 400, 500]), "g"), ("pan", rng.randint(2, 4), "unidad"),
                                       ("leche", 1, "L"), ("papa", 1, "kg"), ("platano", rng.randint(2, 3), "unidad")][atras // 3 % 5]
            mermas.append((utc(dia, 20, 30), clave, cantidad, unidad, rng.choice(["vencido", "danado"]), None))
        if atras <= 14 and dia.weekday() < 5:
            mermas.append((utc(dia, 20, 35), "lechuga", rng.choice([1, 2, 2]), "unidad", "danado", "Llegó marchita del proveedor"))
        elif atras > 14 and atras % 13 == 0:
            mermas.append((utc(dia, 20, 35), "lechuga", 1, "unidad", "vencido", None))
    mermas.append((utc(hoy - timedelta(days=9), 13, 10), "aceite", 500, "ml", "derramado", None))
    return mermas


def planear_gastos(hoy, dias):
    """Arriendo, servicios, nómina, gas y aseo de los meses del periodo."""
    salida = []
    inicio = hoy - timedelta(days=dias)
    dia = inicio
    while dia < hoy:
        d = dia.day
        def gasto(cat, desc, valor, medio="transferencia", de_caja=False, hora=10):  # noqa: E306
            salida.append((utc(dia, hora, 15), s_gastos.GastoIn(fecha=dia, categoria=cat, descripcion=desc, valor=Decimal(valor), medio_pago=medio, de_caja=de_caja), de_caja))
        if d == 1:
            gasto("arriendo", f"Arriendo del local, {dia:%m/%Y}", 1800000)
        if d == 5:
            gasto("servicios", "Internet y teléfono", 95000)
        if d == 8:
            gasto("servicios", "Energía", 420000)
        if d == 12:
            gasto("servicios", "Acueducto", 140000)
        if d in (15, 28):
            gasto("nomina", f"Nómina {'primera' if d == 15 else 'segunda'} quincena", 1600000)
        if dia.weekday() == 1:
            gasto("gas", "Pipeta de gas 100 lb", 98000, "efectivo", True)
        if d in (3, 18):
            gasto("aseo", "Jabón, desengrasante y bolsas", 86000, "efectivo", True)
        dia += timedelta(days=1)
    return salida


def ejecutar(db, tenant, usuarios, mesas, platos, por_nombre, ins, provs, consumo, compras_de, hoy, ahora, t, tipo, datos, rng):
    admin = usuarios["admin"]
    if tipo in ("compra", "compra_duplicada"):
        clave = datos
        lineas = []
        for k, (nombre, unidad, _, costo, minimo, prov) in INSUMOS.items():
            surte = prov == clave or (k == "tomate" and clave == "andina")
            if not surte or (tipo == "compra" and t not in compras_de[k]):
                continue
            insumo = db.get(Insumo, ins[k])
            db.refresh(insumo)
            siguiente = next((x for x in compras_de[k] if x > t), None)
            fin = siguiente or (ahora + timedelta(days=1))
            necesita = sum((c for tt, c in consumo[ins[k]] if t <= tt < fin), Decimal(0))
            diario = sum((c for tt, c in consumo[ins[k]] if t - timedelta(days=14) <= tt < t), Decimal(0)) / 14 or necesita / 7
            ultimo = siguiente is None
            if ultimo:
                objetivo = Decimal(0) if k in SIN_EXISTENCIA else (diario * Decimal(str(DIAS_OBJETIVO[k])) if k in DIAS_OBJETIVO else Decimal(minimo) * Decimal("1.6"))
                cantidad = necesita + objetivo - Decimal(insumo.existencia)
            else:
                cantidad = necesita * Decimal("1.25") + diario * Decimal("1.5") - Decimal(insumo.existencia)
            if cantidad <= 0:
                continue
            decimales = Decimal("1") if unidad in ("unidad", "g", "ml") else Decimal("0.001") if k in SIN_EXISTENCIA or ultimo else Decimal("0.5")
            cantidad = cantidad.quantize(decimales, rounding=ROUND_UP)
            precio = Decimal(PRECIO_RES_ALZA if k == "res" and t >= utc(hoy - timedelta(days=DIAS_ALZA), 0) else TOMATE_ANDINA if k == "tomate" and clave == "andina" else costo)
            precio = (precio * Decimal(str(rng.uniform(0.97, 1.03)))).quantize(Decimal("0.01") if unidad != "g" else Decimal("0.0001"))
            if k == "cafe":  # el café se compra por kilo
                lineas.append(s_compras.CompraItemCreate(insumo_id=ins[k], cantidad=(cantidad / 1000).quantize(Decimal("0.001"), rounding=ROUND_UP), unidad="kg", precio_unitario=(precio * 1000).quantize(Decimal("0.01"))))
            else:
                lineas.append(s_compras.CompraItemCreate(insumo_id=ins[k], cantidad=cantidad, unidad=unidad, precio_unitario=precio))
        if tipo == "compra_duplicada":
            lineas = [s_compras.CompraItemCreate(insumo_id=ins["arroz"], cantidad=Decimal("25"), unidad="kg", precio_unitario=Decimal("4200"))]
        if not lineas:
            return
        compra = compras.crear_compra(db, tenant.id, s_compras.CompraCreate(proveedor_id=provs[clave], fecha=t, confirmar=True, items=lineas,
                                      notas="Compra registrada dos veces por error" if tipo == "compra_duplicada" else None), admin.nombre_completo)
        if tipo == "compra_duplicada":
            compras.anular_compra(db, tenant.id, compra.id, admin.nombre_completo, ahora=t + timedelta(minutes=20))
    elif tipo == "abrir":
        d = datos
        # Turnos repartidos; HOY abre Carla, para que la cuenta de caja lo vea.
        quien = usuarios["caja" if d == hoy or d.weekday() in (0, 2, 4, 5) else "admin"]
        caja.abrir(db, quien, Decimal("100000"), ahora=t)
    elif tipo == "cerrar":
        d, diferencia = datos
        quien = usuarios["caja" if d.weekday() in (0, 2, 4, 5) else "admin"]
        abierta = caja.caja_abierta(db, tenant.id)
        if abierta is None:
            return
        esperado = caja.cuadre(db, abierta)["esperado"]
        contado = dict(esperado)
        motivo = None
        if diferencia:
            contado["efectivo"] = esperado["efectivo"] + diferencia
            motivo = "Faltante en el efectivo al cierre: no se encontró la causa"
        caja.cerrar(db, quien, s_caja.CerrarCaja(contado=contado, motivo_diferencia=motivo), ahora=t)
    elif tipo == "orden":
        p = datos
        quien = usuarios[p.toma]
        items = [s_ord.ItemPedido(producto_id=platos[n], cantidad=c, nota=nota,
                                  modificador_ids=[m.id for m in por_nombre[n].modificadores if m.nombre in mods]) for n, c, mods, nota in p.items]
        orden = ordenes.crear_orden(db, quien, s_ord.OrdenCreate(
            tipo=p.tipo, origen=p.origen, mesa_id=mesas.get(p.mesa) if p.tipo == "local" else None, cliente_nombre=p.cliente,
            cliente_telefono=p.telefono, cliente_direccion=p.direccion, items=items), ahora=t)
        p.id = orden.id
    elif tipo in ("anular", "anular_item", "tomar", "finalizar", "entregar", "cobrar"):
        p = datos
        if p.id is None:  # la orden no se pudo crear
            return
        orden = db.get(m_ordenes.Orden, p.id)
        db.refresh(orden)
        cocinero = usuarios["cocina" if (t + COLOMBIA).day % 2 else "cocina2"]
        if tipo == "anular":
            ordenes.anular_orden(db, usuarios["caja"], p.id, rng.choice(MOTIVOS_ANULACION), ahora=t)
        elif tipo == "anular_item":
            item = next(i for i in orden.items if i.nombre == p.anular_item and not i.anulado)
            ordenes.anular_item(db, usuarios[p.toma], p.id, item.id, "El cliente ya no lo quiso", ahora=t)
        elif tipo == "tomar":
            for c in orden.comandas:
                if c.estado == "entrante":
                    cocina.mover(db, cocinero, c.id, "entrante", "en_preparacion", "tomar", ahora=t)
        elif tipo == "finalizar":
            for c in orden.comandas:
                if c.estado == "en_preparacion":
                    cocina.mover(db, cocinero, c.id, "en_preparacion", "lista", "finalizar", ahora=t)
        elif tipo == "entregar":
            ordenes.entregar(db, usuarios[p.toma] if p.tipo == "local" else usuarios["caja"], p.id, ahora=t)
        elif tipo == "cobrar":
            config = caja._config(db, tenant.id)
            pendiente = sum((Decimal(i.precio_unitario) * i.cantidad for i in caja.pendientes(orden)), Decimal(0))
            total = caja.desglose(pendiente, config)["total"]
            propina = (total * Decimal("0.10")).quantize(Decimal("100")) if p.propina else Decimal(0)
            a_pagar = total + propina
            pagos = []
            restante = a_pagar
            for i, (medio, fraccion) in enumerate(p.pagos):
                monto = restante if i == len(p.pagos) - 1 else (a_pagar * Decimal(str(fraccion))).quantize(Decimal("100"))
                restante -= monto
                recibido = None
                if medio == "efectivo":
                    recibido = max(monto, ((monto / 10000).to_integral_value(rounding=ROUND_UP) * 10000))
                pagos.append(s_caja.PagoIn(medio=medio, monto=monto, recibido=recibido))
            hoy_dia = (t + COLOMBIA).date()
            quien = usuarios["caja" if hoy_dia.weekday() in (0, 2, 4, 5) else "admin"]
            caja.cobrar(db, quien, s_caja.CobroCreate(orden_id=p.id, propina=propina, pagos=pagos), ahora=t)
    elif tipo == "merma":
        clave, cantidad, unidad, motivo, detalle = datos
        inventario.registrar_merma(db, usuarios["cocina"], ins[clave], s_inv.MermaCreate(cantidad=Decimal(str(cantidad)), unidad=unidad, motivo=motivo, detalle=detalle), ahora=t)
    elif tipo == "conteo":
        ajustes = {"arroz": Decimal("-0.35"), "aceite": Decimal("-0.25"), "papa": Decimal("0.6"), "azucar": Decimal("-0.1"), "frijol": Decimal("0"), "huevo": Decimal("-3")}
        lineas = []
        for k, dif in ajustes.items():
            insumo = db.get(Insumo, ins[k])
            db.refresh(insumo)
            lineas.append(s_inv.ConteoLinea(insumo_id=ins[k], contado=max(Decimal(0), Decimal(insumo.existencia) + dif)))
        inventario.registrar_conteo(db, admin, s_inv.ConteoCreate(motivo="Conteo de cierre de mes", lineas=lineas), ahora=t)
    elif tipo == "desactivar":
        r_catalogo.cambiar_estado_producto(platos[datos], s_cat.CambioEstado(activo=False), db=db, usuario=admin)
    elif tipo == "gasto":
        payload, de_caja = datos
        if de_caja and caja.caja_abierta(db, tenant.id) is None:
            payload = payload.model_copy(update={"de_caja": False})
        gastos.registrar(db, usuarios["caja"] if de_caja else admin, payload, ahora=t)


# ===========================================================================
# Café Central (pequeño)
# ===========================================================================
def sembrar_cafe_central(db, hoy: date, ahora: datetime, rng) -> dict:
    tenant, admin = alta.crear_empresa(db, "Café Central", "admin@cafecentral.demo", "Central2026*Admin", nombre_admin="Elena Prieto")
    r_ajustes.editar_negocio(s_ajustes.NegocioUpdate(nombre_empresa="Café Central", nit=nit("901987654"), direccion="Carrera 5 # 12-30",
                             ciudad="Medellín", telefono="6044443322", correo="hola@cafecentral.demo"), db=db, tenant_id=tenant.id)
    mesas = configurar(db, tenant, {"Barra": ["B1", "B2", "B3", "B4"]}, impresoras=False)
    cat = _id(r_catalogo.crear_categoria(s_cat.CategoriaCreate(nombre="Cafetería", orden=1), db=db, tenant_id=tenant.id))
    ins = {
        "cafe": _id(r_inv.crear_insumo(s_inv.InsumoCreate(nombre="Café de origen", unidad="g", minimo=Decimal(800), costo_unitario=Decimal("60")), db=db, usuario=admin)),
        "leche": _id(r_inv.crear_insumo(s_inv.InsumoCreate(nombre="Leche entera", unidad="L", minimo=Decimal(6), costo_unitario=Decimal("4500")), db=db, usuario=admin)),
        "croissant": _id(r_inv.crear_insumo(s_inv.InsumoCreate(nombre="Croissant", unidad="unidad", minimo=Decimal(12), costo_unitario=Decimal("2100")), db=db, usuario=admin)),
    }
    prov = _id(r_compras.crear_proveedor(s_compras.ProveedorCreate(tipo_persona="juridica", nit=nit("900111222"), razon_social="Tostadores del Oriente SAS",
               representante_nombre="Iván Mora", insumo_ids=list(ins.values())), db=db, tenant_id=tenant.id))
    platos = {}
    for nombre, precio, receta in (("Espresso", 4500, [("cafe", 9, "g")]), ("Capuchino", 7500, [("cafe", 9, "g"), ("leche", 160, "ml")]),
                                   ("Croissant de mantequilla", 6000, [("croissant", 1, "unidad")])):
        platos[nombre] = _id(r_catalogo.crear_producto(s_cat.ProductoCreate(nombre=nombre, precio=Decimal(precio), categoria_id=cat,
                             receta=[s_cat.RecetaItemIn(insumo_id=ins[i], cantidad=Decimal(c), unidad=u) for i, c, u in receta]), db=db, usuario=admin))
    inicio = hoy - timedelta(days=7)
    compras.crear_compra(db, tenant.id, s_compras.CompraCreate(proveedor_id=prov, fecha=utc(inicio, 6, 0), confirmar=True, items=[
        s_compras.CompraItemCreate(insumo_id=ins["cafe"], cantidad=Decimal("5"), unidad="kg", precio_unitario=Decimal("60000")),
        s_compras.CompraItemCreate(insumo_id=ins["leche"], cantidad=Decimal("40"), unidad="L", precio_unitario=Decimal("4500")),
        s_compras.CompraItemCreate(insumo_id=ins["croissant"], cantidad=Decimal("150"), unidad="unidad", precio_unitario=Decimal("2100")),
    ]), admin.nombre_completo)
    n = 0
    for atras in range(7, -1, -1):
        dia = hoy - timedelta(days=atras)
        apertura = utc(dia, 6, 30)
        if apertura > ahora:
            break
        caja.abrir(db, admin, Decimal("50000"), ahora=apertura)
        for k in range(rng.randint(6, 10) if atras else 3):
            t = utc(dia, 7 + k, rng.randint(0, 50))
            if t > ahora - timedelta(minutes=5):
                break
            nombre = rng.choice(list(platos))
            orden = ordenes.crear_orden(db, admin, s_ord.OrdenCreate(tipo="local", mesa_id=mesas[rng.choice(list(mesas))], items=[s_ord.ItemPedido(producto_id=platos[nombre])]), ahora=t)
            for c in orden.comandas:
                if c.estado == "entrante":
                    cocina.mover(db, admin, c.id, "entrante", "en_preparacion", "tomar", ahora=t + timedelta(minutes=1))
                    cocina.mover(db, admin, c.id, "en_preparacion", "lista", "finalizar", ahora=t + timedelta(minutes=4))
            ordenes.entregar(db, admin, orden.id, ahora=t + timedelta(minutes=5))
            orden = db.get(m_ordenes.Orden, orden.id)
            caja.cobrar(db, admin, s_caja.CobroCreate(orden_id=orden.id, pagos=[s_caja.PagoIn(medio="efectivo", monto=orden.total)]), ahora=t + timedelta(minutes=12))
            n += 1
        if atras:
            abierta = caja.caja_abierta(db, tenant.id)
            caja.cerrar(db, admin, s_caja.CerrarCaja(contado=caja.cuadre(db, abierta)["esperado"]), ahora=utc(dia, 19, 0))
    return {"tenant": tenant, "ordenes": n}


# ===========================================================================
# Punto de entrada
# ===========================================================================
def cargar_demo(db, ahora: datetime | None = None, reset: bool = False, dias: int = 90, escala: float = 1.0) -> dict:
    """Crea (o recrea) las dos empresas de demostración. La usan main() y
    tests/test_seed_demo.py, para que la prueba corra EXACTAMENTE lo mismo."""
    if settings.ENV == "production":
        raise ConflictError("Los datos de demostración solo se cargan en desarrollo: ENV es production.")
    ahora = ahora or ahora_utc()
    hoy = (ahora + COLOMBIA).date()
    rng = random.Random(f"donde-tavo-{hoy}")
    resultado = {}
    for clave, correo, sembrar in (("donde_tavo", USUARIOS[0][1], lambda: sembrar_donde_tavo(db, hoy, ahora, dias, rng, escala)),
                                   ("cafe_central", "admin@cafecentral.demo", lambda: sembrar_cafe_central(db, hoy, ahora, rng))):
        existente = tenant_de(db, correo)
        if existente is not None and not reset and al_dia(db, existente, hoy):
            resultado[clave] = {"tenant": existente, "nombre": existente.nombre_empresa, "al_dia": True}
            continue
        if existente is not None:
            borrar_empresa(db, existente.id)
        resultado[clave] = sembrar()
        resultado[clave]["nombre"] = resultado[clave]["tenant"].nombre_empresa
    return resultado


def main():
    parser = argparse.ArgumentParser(description="Carga los datos de demostración de Donde Tavo y Café Central (solo en desarrollo)")
    parser.add_argument("--reset", action="store_true", help="Borra y recrea las dos empresas de demostración aunque estén al día")
    parser.add_argument("--dias", type=int, default=90, help="Días de historia (por defecto 90)")
    args = parser.parse_args()
    if settings.ENV == "production":
        salir("Los datos de demostración solo se cargan en desarrollo: ENV es production. No se tocó nada.")
    db = SessionLocal()
    inicio = reloj.monotonic()
    try:
        r = cargar_demo(db, reset=args.reset, dias=args.dias)
    finally:
        db.close()
    for clave, datos in r.items():
        nombre = datos["nombre"]
        if datos.get("al_dia"):
            print(f"✔ {nombre}: ya estaba al día (tiene órdenes de hoy). Usa --reset para recrearla.")
        elif clave == "donde_tavo":
            c = datos["cuenta"]
            print(f"✔ {nombre}: {c.get('orden', 0)} órdenes, {c.get('cobrar', 0)} cobros, {c.get('compra', 0) + c.get('compra_duplicada', 0)} compras, "
                  f"{c.get('merma', 0)} mermas, {c.get('gasto', 0)} gastos, {c.get('cerrar', 0)} cierres de caja.")
            rechazadas = {k: v for k, v in c.items() if k.endswith("rechazada")}
            if rechazadas:
                print(f"   (no se pudieron: {rechazadas})")
        else:
            print(f"✔ {nombre}: {datos['ordenes']} órdenes en la última semana.")
    print(f"   Listo en {reloj.monotonic() - inicio:.0f} s.")
    print("\nCuentas:")
    for _, correo, clave_acceso, nombre, rol in USUARIOS:
        print(f"   {rol:<14} {correo:<28} {clave_acceso}   ({nombre})")
    print(f"   {'Administrador':<14} {'admin@cafecentral.demo':<28} Central2026*Admin   (Café Central)")


if __name__ == "__main__":
    main()
