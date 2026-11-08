"""Genera datos/upz_coords.json (centroides de las UPZ) desde un GeoJSON oficial.

NO inventa coordenadas: las obtiene de un archivo oficial que debes descargar.

QUÉ DESCARGAR
-------------
Capa oficial de UPZ de Bogotá (polígonos), desde una de estas fuentes:
  - Mapas Bogotá / IDECA (Infraestructura de Datos Espaciales): capa
    "Unidad de Planeamiento Zonal (UPZ)".  https://www.ideca.gov.co
  - Datos Abiertos Bogotá (datosabiertos.bogota.gov.co), buscar "UPZ".
  - Secretaría Distrital de Planeación (SDP).
Guarda el archivo como:  datos/upz.geojson   (formato GeoJSON, EPSG:4326 / WGS84).

USO
---
    python -m scripts.generar_zonas

Lee datos/upz.geojson, calcula el CENTROIDE de cada UPZ de Ciudad Bolívar
(emparejando por nombre con web/zonas.json) y escribe datos/upz_coords.json
con {"id_upz": {"lat": .., "lon": ..}}. Ese archivo lo usa zonas/asociacion.py.

Solo biblioteca estándar. No agrega dependencias.
"""
import json
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GEOJSON = RAIZ / "datos" / "upz.geojson"
SALIDA = RAIZ / "datos" / "upz_coords.json"
ZONAS = RAIZ / "web" / "zonas.json"


def _norm(txt):
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def _centroide(geometria):
    """Centroide aproximado (promedio de vértices) de un Polygon/MultiPolygon."""
    pts = []

    def recorrer(coords, prof):
        if prof == 0:
            # coords = [lon, lat]
            pts.append((coords[1], coords[0]))
            return
        for c in coords:
            recorrer(c, prof - 1)

    tipo = geometria.get("type")
    coords = geometria.get("coordinates", [])
    if tipo == "Polygon":
        recorrer(coords, 2)
    elif tipo == "MultiPolygon":
        recorrer(coords, 3)
    elif tipo == "Point":
        return coords[1], coords[0]
    if not pts:
        return None
    lat = sum(p[0] for p in pts) / len(pts)
    lon = sum(p[1] for p in pts) / len(pts)
    return lat, lon


def main():
    if not GEOJSON.exists():
        print("No existe datos/upz.geojson.")
        print("Descarga la capa oficial de UPZ (IDECA / Datos Abiertos Bogotá / SDP),")
        print("guárdala como datos/upz.geojson (GeoJSON, WGS84) y vuelve a ejecutar:")
        print("    python -m scripts.generar_zonas")
        sys.exit(1)

    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    zonas = json.loads(ZONAS.read_text(encoding="utf-8")).get("zonas", [])
    objetivo = {_norm(z["nombre"]): z["id"] for z in zonas}

    coords = {}
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        # El nombre de la UPZ puede venir en distintas claves según la fuente
        nombre = None
        for k in ("UPZNOMBRE", "upznombre", "NOMBRE", "nombre", "UPlNombre", "upl_nombre"):
            if props.get(k):
                nombre = props[k]
                break
        if not nombre:
            continue
        clave = _norm(nombre)
        zid = objetivo.get(clave)
        if not zid:
            continue
        c = _centroide(feat.get("geometry", {}))
        if c:
            coords[zid] = {"lat": round(c[0], 6), "lon": round(c[1], 6),
                           "fuente": "centroide de datos/upz.geojson (oficial)"}

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(coords, ensure_ascii=False, indent=2), encoding="utf-8")
    faltan = [z["nombre"] for z in zonas if z["id"] not in coords]
    print(f"Escrito {SALIDA} con {len(coords)} UPZ.")
    if faltan:
        print("UPZ sin emparejar (revisa nombres en el GeoJSON):", ", ".join(faltan))


if __name__ == "__main__":
    main()
