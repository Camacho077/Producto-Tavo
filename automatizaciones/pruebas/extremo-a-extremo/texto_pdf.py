"""Extrae el texto de un PDF generado por ReportLab SIN librerías externas:
descomprime cada stream FlateDecode con zlib y junta las cadenas de los
operadores de texto (Tj / TJ). Suficiente para verificar que el PDF trae los
datos correctos. Uso: python texto_pdf.py archivo.pdf"""
import base64
import re
import sys
import zlib

datos = open(sys.argv[1], "rb").read()
assert datos.startswith(b"%PDF"), "no es un PDF"
paginas = len(re.findall(rb"/Type\s*/Page[^s]", datos))
textos = []
for m in re.finditer(rb"stream\r?\n(.*?)\s*endstream", datos, re.S):
    crudo = m.group(1)
    contenido = crudo
    for intento in (
        lambda b: zlib.decompress(b),
        # ReportLab: /Filter [/ASCII85Decode /FlateDecode]
        lambda b: zlib.decompress(base64.a85decode(b.strip().removesuffix(b"~>").strip(), adobe=False)),
    ):
        try:
            contenido = intento(crudo)
            break
        except Exception:
            continue
    for cadena in re.findall(rb"\((.*?)(?<!\\)\)\s*Tj", contenido, re.S):
        textos.append(cadena)
    for arreglo in re.findall(rb"\[(.*?)\]\s*TJ", contenido, re.S):
        textos.append(b"".join(re.findall(rb"\((.*?)(?<!\\)\)", arreglo, re.S)))


def decodificar(b: bytes) -> str:
    b = re.sub(rb"\\([0-7]{3})", lambda x: bytes([int(x.group(1), 8)]), b)
    b = b.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
    return b.decode("latin-1")


print(f"PAGINAS={paginas}")
print("\n".join(decodificar(t) for t in textos))
