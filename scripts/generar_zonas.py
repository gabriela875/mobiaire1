"""Genera datos/upz_coords.json (centroides de las UPZ) desde un GeoJSON oficial.

Lee datos/upz.geojson (capa de UPZ de Datos Abiertos Bogotá, WGS84), toma solo las 8 UPZ
de Ciudad Bolívar (por nombre y código), calcula el centroide de cada una (ponderado por área) y escribe
{"id_zona": {"lat": .., "lon": ..}}. Ese archivo lo usa zonas/asociacion.py.

Uso:  python -m scripts.generar_zonas
"""
import json
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GEOJSON = RAIZ / "datos" / "upz.geojson"
SALIDA = RAIZ / "datos" / "upz_coords.json"
ZONAS = RAIZ / "web" / "zonas.json"

# nombre en web/zonas.json -> nombre en el GeoJSON (ambos sin tildes ni mayúsculas)
ALIAS = {"jerusalen": "jerusalem", "mochuelo": "el mochuelo"}
# Código de cada UPZ en datos/upz.geojson (UPlCodigo). Se usa para no confundir nombres repetidos.
# No se filtra por LocNombre: en este archivo no coincide con la localidad real de las UPZ.
CODIGOS = {"el mochuelo": "UPZ63", "monte blanco": "UPZ64", "arborizadora": "UPZ65",
           "san francisco": "UPZ66", "lucero": "UPZ67", "el tesoro": "UPZ68",
           "ismael perdomo": "UPZ69", "jerusalem": "UPZ70"}
CLAVES_NOMBRE = ("UPlNombre", "UPZNOMBRE", "upznombre", "NOMBRE", "nombre", "upl_nombre")


def _norm(txt):
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def _anillo(pts):
    """(2*área con signo, suma_x, suma_y) de un anillo, fórmula del polígono."""
    a = sx = sy = 0.0
    for p, q in zip(pts, pts[1:] + pts[:1]):
        cruz = p[0] * q[1] - q[0] * p[1]
        a += cruz
        sx += (p[0] + q[0]) * cruz
        sy += (p[1] + q[1]) * cruz
    return a, sx, sy


def _poligono(anillos):
    """(área, área*x, área*y): anillo exterior menos los huecos."""
    A = X = Y = 0.0
    for i, pts in enumerate(anillos):
        a, sx, sy = _anillo(pts)
        if a == 0:
            continue
        area = abs(a / 2) * (1 if i == 0 else -1)
        A += area
        X += area * sx / (3 * a)
        Y += area * sy / (3 * a)
    return A, X, Y


def centroide(geometria):
    """(lat, lon) del centroide de un Polygon/MultiPolygon/Point, o None."""
    tipo, coords = geometria.get("type"), geometria.get("coordinates", [])
    if tipo == "Point":
        return coords[1], coords[0]
    if tipo == "Polygon":
        poligonos = [coords]
    elif tipo == "MultiPolygon":
        poligonos = coords
    else:
        return None
    A = X = Y = 0.0
    for anillos in poligonos:
        a, x, y = _poligono(anillos)
        A, X, Y = A + a, X + x, Y + y
    return (Y / A, X / A) if A else None


def calcular(gj, zonas):
    """Devuelve (coords, faltan, avisos) a partir del GeoJSON y la lista de zonas."""
    objetivo = {}
    for z in zonas:
        n = _norm(z["nombre"])
        objetivo[ALIAS.get(n, n)] = z["id"]

    coords, avisos = {}, []
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        nombre = next((props[k] for k in CLAVES_NOMBRE if props.get(k)), None)
        zid = objetivo.get(_norm(nombre)) if nombre else None
        esperado = CODIGOS.get(_norm(nombre)) if nombre else None
        if zid and esperado and props.get("UPlCodigo") not in (None, esperado):
            continue            # mismo nombre pero otra UPZ
        c = centroide(feat.get("geometry", {})) if zid else None
        if not c:
            continue
        if zid in coords:       # fila repetida: se conserva la primera y se avisa si difiere
            previo = coords[zid]
            if abs(previo["lat"] - c[0]) > 0.0005 or abs(previo["lon"] - c[1]) > 0.0005:
                avisos.append(f"{nombre}: filas repetidas con geometrías distintas (se usó la primera)")
            continue
        coords[zid] = {"lat": round(c[0], 6), "lon": round(c[1], 6),
                       "fuente": "centroide de datos/upz.geojson (oficial)"}
    faltan = [z["nombre"] for z in zonas if z["id"] not in coords]
    return coords, faltan, avisos


def main():
    if not GEOJSON.exists():
        print("No existe datos/upz.geojson. Descargue la capa de UPZ (Datos Abiertos Bogotá, GeoJSON)")
        print("y guárdela con ese nombre. Luego: python -m scripts.generar_zonas")
        sys.exit(1)
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    zonas = json.loads(ZONAS.read_text(encoding="utf-8")).get("zonas", [])
    coords, faltan, avisos = calcular(gj, zonas)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(coords, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito {SALIDA} con {len(coords)} UPZ.")
    for a in avisos:
        print("AVISO:", a)
    if faltan:
        print("UPZ sin emparejar (revise nombres en el GeoJSON):", ", ".join(faltan))
        sys.exit(1)


if __name__ == "__main__":
    main()
