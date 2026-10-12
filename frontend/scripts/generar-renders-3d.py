"""Genera renders 3D abstractos (SVG) para las tarjetas de producto e inventario.

Formas con iluminación desde arriba-izquierda, brillo especular, sombra suave
de contacto y la paleta del producto (monocromática: grises del oscuro / grises del claro). Fondo
transparente: funcionan sobre el tema oscuro y el claro.
"""
from pathlib import Path

DESTINO = Path(r"C:\Users\camac\Desktop\Producto JS\frontend\src\assets\3d")
DESTINO.mkdir(parents=True, exist_ok=True)

# Solo tokens de la paleta (src/index.css). Los nombres de archivo "-pizarra"
# y "-arena" se conservan para no tocar los imports de Imagen3d.jsx.
# (luz, medio, sombra, fondo)
PIZARRA = ("#8A8A94", "#52525B", "#232327", "#0A0A0B")  # grises del oscuro (2026-10-01)
ARENA = ("#F7F7F9", "#D4D4DA", "#6B6B76", "#3F3F46")  # grises del claro (2026-10-01)

DEFS = """
  <defs>
    <filter id="sombra" x="-30%" y="-30%" width="160%" height="180%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="6"/>
      <feOffset dy="10" result="b"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <radialGradient id="contacto" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#0A0A0B" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#0A0A0B" stop-opacity="0"/>
    </radialGradient>
  </defs>
"""


def svg(nombre, cuerpo, defs_extra=""):
    contenido = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200" role="img" aria-label="{nombre}">
{DEFS}{defs_extra}
  <ellipse cx="100" cy="168" rx="58" ry="12" fill="url(#contacto)"/>
{cuerpo}
</svg>
"""
    (DESTINO / f"{nombre}.svg").write_text(contenido, encoding="utf-8")


def esfera(nombre, pal):
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <radialGradient id="g" cx="35%" cy="30%" r="75%">
    <stop offset="0%" stop-color="{luz}"/>
    <stop offset="45%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </radialGradient>
  <radialGradient id="brillo" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#F7F7F9" stop-opacity="0.9"/>
    <stop offset="100%" stop-color="#F7F7F9" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="rebote" cx="50%" cy="100%" r="60%">
    <stop offset="0%" stop-color="{luz}" stop-opacity="0.35"/>
    <stop offset="100%" stop-color="{luz}" stop-opacity="0"/>
  </radialGradient>"""
    cuerpo = f"""  <g filter="url(#sombra)">
    <circle cx="100" cy="100" r="64" fill="url(#g)"/>
    <circle cx="100" cy="100" r="64" fill="url(#rebote)"/>
    <ellipse cx="78" cy="72" rx="22" ry="14" fill="url(#brillo)" transform="rotate(-25 78 72)"/>
  </g>"""
    svg(nombre, cuerpo, defs)


def cubo(nombre, pal):
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <linearGradient id="cara-top" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#F7F7F9" stop-opacity="0.95"/>
    <stop offset="100%" stop-color="{luz}"/>
  </linearGradient>
  <linearGradient id="cara-izq" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{oscuro}"/>
  </linearGradient>
  <linearGradient id="cara-der" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{oscuro}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>"""
    # Cubo isométrico con aristas suavizadas
    cuerpo = """  <g filter="url(#sombra)" stroke-linejoin="round">
    <path d="M100 36 L156 68 L100 100 L44 68 Z" fill="url(#cara-top)"/>
    <path d="M44 68 L100 100 L100 164 L44 132 Z" fill="url(#cara-izq)"/>
    <path d="M156 68 L100 100 L100 164 L156 132 Z" fill="url(#cara-der)"/>
    <path d="M100 36 L156 68 L100 100 L44 68 Z" fill="none" stroke="#F7F7F9" stroke-opacity="0.35" stroke-width="1.5"/>
  </g>"""
    svg(nombre, cuerpo, defs)


def toro(nombre, pal):
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <linearGradient id="anillo" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{luz}"/>
    <stop offset="50%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>
  <radialGradient id="hueco" cx="50%" cy="40%" r="60%">
    <stop offset="0%" stop-color="{abismo}"/>
    <stop offset="100%" stop-color="{oscuro}"/>
  </radialGradient>"""
    cuerpo = """  <g filter="url(#sombra)">
    <ellipse cx="100" cy="100" rx="66" ry="50" fill="url(#anillo)"/>
    <ellipse cx="100" cy="104" rx="30" ry="21" fill="url(#hueco)"/>
    <path d="M42 96 Q100 60 158 96" fill="none" stroke="#F7F7F9" stroke-opacity="0.45" stroke-width="5" stroke-linecap="round"/>
  </g>"""
    svg(nombre, cuerpo, defs)


def capsula(nombre, pal):
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <linearGradient id="cap" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{luz}"/>
    <stop offset="40%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>
  <linearGradient id="cap2" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#F7F7F9"/>
    <stop offset="40%" stop-color="#D4D4DA"/>
    <stop offset="100%" stop-color="#6B6B76"/>
  </linearGradient>"""
    cuerpo = """  <g filter="url(#sombra)" transform="rotate(-28 100 100)">
    <rect x="34" y="72" width="132" height="56" rx="28" fill="url(#cap)"/>
    <path d="M100 72 h38 a28 28 0 0 1 0 56 h-38 z" fill="url(#cap2)"/>
    <rect x="48" y="80" width="100" height="8" rx="4" fill="#F7F7F9" fill-opacity="0.45"/>
  </g>"""
    svg(nombre, cuerpo, defs)


def cono(nombre, pal):
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <linearGradient id="cono" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{luz}"/>
    <stop offset="45%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>
  <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{oscuro}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>"""
    cuerpo = """  <g filter="url(#sombra)">
    <ellipse cx="100" cy="146" rx="58" ry="18" fill="url(#base)"/>
    <path d="M100 30 L158 146 A58 18 0 0 1 42 146 Z" fill="url(#cono)"/>
    <path d="M100 30 L70 140" stroke="#F7F7F9" stroke-opacity="0.35" stroke-width="4" stroke-linecap="round"/>
  </g>"""
    svg(nombre, cuerpo, defs)


def caja(nombre, pal):
    """Paquete/caja de inventario con tapa abierta y cinta."""
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <linearGradient id="tapa" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#F7F7F9" stop-opacity="0.9"/>
    <stop offset="100%" stop-color="{luz}"/>
  </linearGradient>
  <linearGradient id="izq" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{oscuro}"/>
  </linearGradient>
  <linearGradient id="der" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{oscuro}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>"""
    cuerpo = f"""  <g filter="url(#sombra)" stroke-linejoin="round">
    <path d="M46 78 L100 106 L100 166 L46 138 Z" fill="url(#izq)"/>
    <path d="M154 78 L100 106 L100 166 L154 138 Z" fill="url(#der)"/>
    <path d="M100 50 L154 78 L100 106 L46 78 Z" fill="url(#tapa)"/>
    <path d="M46 78 L100 106 L154 78" fill="none" stroke="#F7F7F9" stroke-opacity="0.35" stroke-width="1.5"/>
    <path d="M100 106 L100 166" stroke="#F7F7F9" stroke-opacity="0.18" stroke-width="1.5"/>
    <path d="M73 92 L127 64" stroke="{ARENA[1]}" stroke-width="6" stroke-linecap="round" stroke-opacity="0.85"/>
  </g>"""
    svg(nombre, cuerpo, defs)


def moneda(nombre, pal):
    luz, medio, oscuro, abismo = pal
    defs = f"""
  <linearGradient id="canto" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{medio}"/>
    <stop offset="100%" stop-color="{abismo}"/>
  </linearGradient>
  <radialGradient id="caraM" cx="35%" cy="30%" r="80%">
    <stop offset="0%" stop-color="#F7F7F9"/>
    <stop offset="35%" stop-color="{luz}"/>
    <stop offset="100%" stop-color="{medio}"/>
  </radialGradient>"""
    cuerpo = f"""  <g filter="url(#sombra)">
    <ellipse cx="100" cy="112" rx="62" ry="40" fill="url(#canto)"/>
    <rect x="38" y="88" width="124" height="24" fill="url(#canto)"/>
    <ellipse cx="100" cy="88" rx="62" ry="40" fill="url(#caraM)"/>
    <ellipse cx="100" cy="88" rx="44" ry="27" fill="none" stroke="{oscuro}" stroke-opacity="0.35" stroke-width="3"/>
  </g>"""
    svg(nombre, cuerpo, defs)


# Solo la paleta del producto: ningún color fuera de sus doce tokens.
esfera("esfera-arena", ARENA)
esfera("esfera-pizarra", PIZARRA)
cubo("cubo-arena", ARENA)
cubo("cubo-pizarra", PIZARRA)
toro("toro-pizarra", PIZARRA)
capsula("capsula-arena", ARENA)
cono("cono-pizarra", PIZARRA)
caja("caja-arena", ARENA)
caja("caja-pizarra", PIZARRA)
moneda("moneda-arena", ARENA)

for viejo in DESTINO.glob("*-verde.svg"):
    viejo.unlink()

(DESTINO / "LICENSE.md").write_text(
    "# Renders 3D del producto\n\n"
    "Formas abstractas generadas para JS Company (script en el historial del proyecto),\n"
    "sin material de terceros. Se liberan bajo CC0 1.0: se pueden usar, modificar y\n"
    "redistribuir sin atribución. Son marcadores de posición hasta que existan fotos\n"
    "reales de producto.\n",
    encoding="utf-8",
)
print("generados:", sorted(p.name for p in DESTINO.iterdir()))
