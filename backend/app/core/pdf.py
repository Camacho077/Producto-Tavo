"""
Generación de PDF para documentos de negocio (compras, ventas, pedidos).

Un solo generador para los tres documentos: cabecera con la empresa del
tenant, bloque de datos del documento, tabla de ítems con filas alternadas,
totales y pie. Devuelve los bytes del PDF listos para responder con
`application/pdf`.
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

# Paleta del producto (ver frontend/src/index.css). El PDF es papel blanco,
# así que usa el esquema CLARO completo: blanco + crema, sin ningún otro color.
MARRON = colors.HexColor("#3B2A18")  # texto principal, títulos, encabezado de tabla
TIERRA = colors.HexColor("#8A6B44")  # texto secundario
ARENA = colors.HexColor("#D9C5A0")  # bordes y separadores
CREMA_HONDO = colors.HexColor("#F2E7D3")  # fila de totales
CREMA = colors.HexColor("#FBF6EC")  # superficies y texto sobre marrón


def formatear_moneda(valor) -> str:
    numero = Decimal(str(valor or 0)).quantize(Decimal("1"))
    entero = f"{int(numero):,}".replace(",", ".")
    return f"$ {entero}"


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
                                textColor=MARRON, spaceAfter=0)
    st_sub = ParagraphStyle("sub", parent=estilos["Normal"], fontSize=9, textColor=TIERRA)
    st_titulo = ParagraphStyle("titulo", parent=estilos["Normal"], fontSize=13, leading=16, textColor=MARRON,
                               fontName="Helvetica-Bold", alignment=TA_RIGHT)
    st_codigo = ParagraphStyle("codigo", parent=estilos["Normal"], fontSize=10, textColor=MARRON,
                               alignment=TA_RIGHT, fontName="Helvetica-Bold")
    st_meta_k = ParagraphStyle("metak", parent=estilos["Normal"], fontSize=8, textColor=TIERRA)
    st_meta_v = ParagraphStyle("metav", parent=estilos["Normal"], fontSize=10, textColor=MARRON)
    st_celda = ParagraphStyle("celda", parent=estilos["Normal"], fontSize=9, leading=12)
    st_celda_der = ParagraphStyle("celdader", parent=st_celda, alignment=TA_RIGHT)
    st_total_k = ParagraphStyle("totalk", parent=estilos["Normal"], fontSize=10, alignment=TA_RIGHT,
                                textColor=TIERRA)
    st_total_v = ParagraphStyle("totalv", parent=estilos["Normal"], fontSize=14, alignment=TA_RIGHT,
                                textColor=MARRON, fontName="Helvetica-Bold")
    st_notas = ParagraphStyle("notas", parent=estilos["Normal"], fontSize=9, textColor=MARRON, leading=12)
    st_pie = ParagraphStyle("pie", parent=estilos["Normal"], fontSize=8, textColor=TIERRA)

    contenido = []

    # ---------- Cabecera ----------
    cabecera = Table(
        [
            [
                Paragraph(empresa, st_empresa),
                Paragraph(titulo.upper(), st_titulo),
            ],
            [
                Paragraph("Sistema de gestión · JS Company", st_sub),
                Paragraph(codigo, st_codigo),
            ],
        ],
        colWidths=["62%", "38%"],
    )
    cabecera.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, MARRON),
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
        ("BACKGROUND", (0, 0), (-1, -1), CREMA),
        ("BOX", (0, 0), (-1, -1), 0.5, ARENA),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    contenido += [tabla_meta, Spacer(1, 7 * mm)]

    # ---------- Ítems ----------
    encabezado = ["#", "Producto", "SKU", "Cant.", "Precio unit.", "Subtotal"]
    filas = [encabezado]
    for i, it in enumerate(items, start=1):
        filas.append([
            str(i),
            Paragraph(it.get("producto_nombre") or "—", st_celda),
            Paragraph(it.get("producto_sku") or "—", st_celda),
            Paragraph(str(it.get("cantidad", 0)), st_celda_der),
            Paragraph(formatear_moneda(it.get("precio_unitario", 0)), st_celda_der),
            Paragraph(formatear_moneda(it.get("subtotal", 0)), st_celda_der),
        ])
    tabla = Table(filas, colWidths=[8 * mm, None, 28 * mm, 16 * mm, 30 * mm, 32 * mm], repeatRows=1)
    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MARRON),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREMA),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, ARENA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])
    for fila in range(1, len(filas)):
        if fila % 2 == 0:
            estilo.add("BACKGROUND", (0, fila), (-1, fila), CREMA)
    tabla.setStyle(estilo)
    contenido += [tabla, Spacer(1, 5 * mm)]

    # ---------- Totales ----------
    cantidad_total = sum(int(it.get("cantidad", 0)) for it in items)
    totales = Table(
        [
            [Paragraph("Ítems", st_total_k), Paragraph(str(len(items)), st_meta_v)],
            [Paragraph("Unidades", st_total_k), Paragraph(str(cantidad_total), st_meta_v)],
            [Paragraph("TOTAL", st_total_k), Paragraph(formatear_moneda(total), st_total_v)],
        ],
        colWidths=[30 * mm, 40 * mm],
        hAlign="RIGHT",
    )
    totales.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, MARRON),
        ("BACKGROUND", (0, -1), (-1, -1), CREMA_HONDO),
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
