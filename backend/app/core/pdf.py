"""
Generación de PDF para documentos de negocio (compras, ventas, órdenes).

Un solo generador: cabecera con el restaurante (tenant), bloque de datos del
documento, tabla de ítems con filas alternadas, totales y pie. Devuelve los
bytes del PDF listos para responder con `application/pdf`.

Cada ítem es {descripcion, detalle, cantidad, precio_unitario, subtotal}:
`detalle` es lo que va en la segunda columna (la unidad de compra de un
insumo, los modificadores de un plato…) y su título es `columna_detalle`.
"""
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.branding import EMPRESA_PROVEEDORA, NOMBRE_PRODUCTO

# Paleta MONOCROMÁTICA del producto (2026-10-12, la misma de
# frontend/src/index.css en claro): el PDF es papel blanco. Antes usaba la
# paleta Espresso/Marfil, ya retirada.
TINTA = colors.HexColor("#18181B")  # texto principal, títulos, encabezado de tabla
SECUNDARIO = colors.HexColor("#6B6B76")  # texto secundario
BORDE = colors.HexColor("#E4E4E9")  # bordes y separadores
SUTIL = colors.HexColor("#F1F1F4")  # fila de totales
RELLENO = colors.HexColor("#F7F7F9")  # superficies y texto sobre tinta


def formatear_moneda(valor) -> str:
    numero = Decimal(str(valor or 0)).quantize(Decimal("1"))
    entero = f"{int(numero):,}".replace(",", ".")
    return f"$ {entero}"


def formatear_cantidad(valor) -> str:
    """1 → "1"; 1.500 → "1,5"; 0.25 → "0,25"."""
    numero = Decimal(str(valor or 0)).normalize()
    return f"{numero:f}".replace(".", ",")


def formatear_fecha(valor: datetime | None) -> str:
    if not valor:
        return "—"
    return valor.strftime("%d/%m/%Y %H:%M")


def generar_documento_pdf(
    *,
    titulo: str,
    codigo: str,
    empresa: str,
    estado: str,
    fecha: datetime | None,
    datos: list[tuple[str, str]],
    items: list[dict],
    total,
    notas: str | None = None,
    pie: str | None = None,
    columna_descripcion: str = "Producto",
    columna_detalle: str = "Detalle",
    totales_extra: list[tuple[str, str]] | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{titulo} {codigo}",
        author=empresa,
    )

    estilos = getSampleStyleSheet()
    st_empresa = ParagraphStyle("empresa", parent=estilos["Title"], fontSize=18, leading=22, alignment=0,
                                textColor=TINTA, spaceAfter=0)
    st_sub = ParagraphStyle("sub", parent=estilos["Normal"], fontSize=9, textColor=SECUNDARIO)
    st_titulo = ParagraphStyle("titulo", parent=estilos["Normal"], fontSize=13, leading=16, textColor=TINTA,
                               fontName="Helvetica-Bold", alignment=TA_RIGHT)
    st_codigo = ParagraphStyle("codigo", parent=estilos["Normal"], fontSize=10, textColor=TINTA,
                               alignment=TA_RIGHT, fontName="Helvetica-Bold")
    st_meta_k = ParagraphStyle("metak", parent=estilos["Normal"], fontSize=8, textColor=SECUNDARIO)
    st_meta_v = ParagraphStyle("metav", parent=estilos["Normal"], fontSize=10, textColor=TINTA)
    st_celda = ParagraphStyle("celda", parent=estilos["Normal"], fontSize=9, leading=12)
    st_celda_der = ParagraphStyle("celdader", parent=st_celda, alignment=TA_RIGHT)
    st_total_k = ParagraphStyle("totalk", parent=estilos["Normal"], fontSize=10, alignment=TA_RIGHT,
                                textColor=SECUNDARIO)
    st_total_v = ParagraphStyle("totalv", parent=estilos["Normal"], fontSize=14, alignment=TA_RIGHT,
                                textColor=TINTA, fontName="Helvetica-Bold")
    st_notas = ParagraphStyle("notas", parent=estilos["Normal"], fontSize=9, textColor=TINTA, leading=12)
    st_pie = ParagraphStyle("pie", parent=estilos["Normal"], fontSize=8, textColor=SECUNDARIO)

    contenido = []

    # ---------- Cabecera ----------
    cabecera = Table(
        [
            [
                Paragraph(empresa, st_empresa),
                Paragraph(titulo.upper(), st_titulo),
            ],
            [
                Paragraph(f"{NOMBRE_PRODUCTO} · {EMPRESA_PROVEEDORA}", st_sub),
                Paragraph(codigo, st_codigo),
            ],
        ],
        colWidths=["62%", "38%"],
    )
    cabecera.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, TINTA),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
    ]))
    contenido += [cabecera, Spacer(1, 8 * mm)]

    # ---------- Datos del documento ----------
    meta = [("Fecha", formatear_fecha(fecha)), ("Estado", estado.replace("_", " ").capitalize())] + list(datos)
    filas_meta = []
    for i in range(0, len(meta), 3):
        grupo = meta[i:i + 3]
        filas_meta.append([Paragraph(k, st_meta_k) for k, _ in grupo] + [""] * (3 - len(grupo)))
        filas_meta.append([Paragraph(v or "—", st_meta_v) for _, v in grupo] + [""] * (3 - len(grupo)))
    tabla_meta = Table(filas_meta, colWidths=["34%", "33%", "33%"])
    tabla_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RELLENO),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    contenido += [tabla_meta, Spacer(1, 7 * mm)]

    # ---------- Ítems ----------
    encabezado = ["#", columna_descripcion, columna_detalle, "Cant.", "Precio unit.", "Subtotal"]
    filas = [encabezado]
    for i, it in enumerate(items, start=1):
        filas.append([
            str(i),
            Paragraph(it.get("descripcion") or "—", st_celda),
            Paragraph(it.get("detalle") or "—", st_celda),
            Paragraph(formatear_cantidad(it.get("cantidad", 0)), st_celda_der),
            Paragraph(formatear_moneda(it.get("precio_unitario", 0)), st_celda_der),
            Paragraph(formatear_moneda(it.get("subtotal", 0)), st_celda_der),
        ])
    tabla = Table(filas, colWidths=[8 * mm, None, 34 * mm, 18 * mm, 28 * mm, 30 * mm], repeatRows=1)
    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("TEXTCOLOR", (0, 0), (-1, 0), RELLENO),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])
    for fila in range(1, len(filas)):
        if fila % 2 == 0:
            estilo.add("BACKGROUND", (0, fila), (-1, fila), RELLENO)
    tabla.setStyle(estilo)
    contenido += [tabla, Spacer(1, 5 * mm)]

    # ---------- Totales ----------
    totales = Table(
        [[Paragraph("Ítems", st_total_k), Paragraph(str(len(items)), st_meta_v)]]
        + [[Paragraph(k, st_total_k), Paragraph(v, st_meta_v)] for k, v in (totales_extra or [])]
        + [[Paragraph("TOTAL", st_total_k), Paragraph(formatear_moneda(total), st_total_v)]],
        colWidths=[30 * mm, 40 * mm],
        hAlign="RIGHT",
    )
    totales.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, TINTA),
        ("BACKGROUND", (0, -1), (-1, -1), SUTIL),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    contenido.append(totales)

    if notas:
        contenido += [Spacer(1, 6 * mm), Paragraph("<b>Notas</b>", st_meta_k), Paragraph(notas, st_notas)]

    contenido += [
        Spacer(1, 10 * mm),
        Paragraph(pie or f"Documento generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} · {empresa}", st_pie),
    ]

    doc.build(contenido)
    return buffer.getvalue()


def generar_reporte_pdf(*, titulo: str, empresa: str, subtitulo: str, resumen: list[tuple[str, str]], secciones: list[tuple[str, list[str], list[list[str]]]]) -> bytes:
    """Reporte de varias tablas (fase 8): cabecera, cuadro de cifras y una
    tabla por sección, con el mismo estilo monocromo de los documentos."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"{titulo} · {empresa}", author=empresa)
    estilos = getSampleStyleSheet()
    st_titulo = ParagraphStyle("t", parent=estilos["Title"], fontSize=16, leading=20, alignment=0, textColor=TINTA)
    st_sub = ParagraphStyle("s", parent=estilos["Normal"], fontSize=9, textColor=SECUNDARIO)
    st_seccion = ParagraphStyle("h", parent=estilos["Heading3"], fontSize=11, textColor=TINTA, spaceBefore=10, spaceAfter=4)
    st_celda = ParagraphStyle("c", parent=estilos["Normal"], fontSize=8, leading=10, textColor=TINTA)
    historia = [Paragraph(f"{empresa} · {titulo}", st_titulo), Paragraph(subtitulo, st_sub), Spacer(1, 6)]

    def tabla(encabezados, filas, anchos=None):
        datos = [[Paragraph(f"<b>{e}</b>", st_celda) for e in encabezados]] + [[Paragraph(str(c), st_celda) for c in f] for f in filas]
        t = Table(datos, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), RELLENO),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    historia.append(tabla(["Cifra", "Valor"], [[a, b] for a, b in resumen], anchos=[80 * mm, 60 * mm]))
    for nombre, encabezados, filas in secciones:
        historia.append(Paragraph(nombre, st_seccion))
        historia.append(tabla(encabezados, filas or [["Sin datos en el periodo"] + [""] * (len(encabezados) - 1)]))
    historia.append(Spacer(1, 8))
    historia.append(Paragraph(f"Generado con {NOMBRE_PRODUCTO} · {EMPRESA_PROVEEDORA}", st_sub))
    doc.build(historia)
    return buffer.getvalue()
