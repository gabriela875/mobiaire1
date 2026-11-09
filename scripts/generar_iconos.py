"""Genera los PNG de icono de la PWA SIN dependencias (solo stdlib: zlib, struct).

Dibuja una versión rasterizada simple del logo de MobiAire (fondo verde, círculo
crema, silueta y vientre coral) en los tamaños que piden Android/Chrome:
  web/iconos/icono-192.png  y  web/iconos/icono-512.png
(y una variante "maskable" con el mismo arte, que ya ocupa todo el lienzo).

Uso:  python -m scripts.generar_iconos
El SVG (web/iconos/icono.svg) sigue siendo la fuente vectorial.
"""
import struct
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "web" / "iconos"

VERDE = (47, 107, 79)
CREMA = (231, 241, 234)
VERDE_MEDIO = (61, 131, 98)
CORAL = (232, 146, 124)


def _circulo(px, py, cx, cy, r):
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def _dibujar(n):
    """Devuelve filas RGB (lista de bytearray) de n x n con el logo."""
    c = n / 512.0  # escala respecto al viewBox 512
    filas = []
    for y in range(n):
        fila = bytearray()
        for x in range(n):
            col = VERDE  # fondo (maskable: cubre todo)
            # círculo crema central
            if _circulo(x, y, 256 * c, 256 * c, 150 * c):
                col = CREMA
                # silueta (cuerpo) aproximada: elipse del torso
                if _circulo(x, y, 272 * c, 300 * c, 95 * c):
                    col = VERDE_MEDIO
                # cabeza
                if _circulo(x, y, 300 * c, 175 * c, 34 * c):
                    col = VERDE
                # vientre coral
                if _circulo(x, y, 208 * c, 320 * c, 52 * c):
                    col = CORAL
            fila += bytes(col)
        filas.append(fila)
    return filas


def _png(n, ruta):
    filas = _dibujar(n)
    cruda = bytearray()
    for fila in filas:
        cruda.append(0)         # filtro 'none' por scanline
        cruda += fila
    comprimido = zlib.compress(bytes(cruda), 9)

    def chunk(tipo, datos):
        c = struct.pack(">I", len(datos)) + tipo + datos
        return c + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

    firma = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0)  # 8 bits, color tipo 2 (RGB)
    datos = firma + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comprimido) + chunk(b"IEND", b"")
    ruta.write_bytes(datos)
    return len(datos)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for n in (192, 512):
        tam = _png(n, DEST / f"icono-{n}.png")
        print(f"Escrito web/iconos/icono-{n}.png ({n}x{n}, {tam} bytes)")


if __name__ == "__main__":
    main()
