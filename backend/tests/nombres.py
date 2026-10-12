"""Nombres de prueba que cumplen la regla de nombres de ítem (solo letras):
desde el 2026-09-27 "Producto 1" ya no es un nombre válido, así que las
pruebas que crean N registros usan `letras(i)` → "AAA", "AAB", ... (ancho
fijo, así conservan el orden alfabético de los índices)."""


def letras(i: int, ancho: int = 3) -> str:
    salida = ""
    for _ in range(ancho):
        i, resto = divmod(i, 26)
        salida = chr(ord("A") + resto) + salida
    return salida.capitalize()
