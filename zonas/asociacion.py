"""Asocia cada UPZ de Ciudad Bolívar a la estación WAQI más cercana (haversine).

Reglas (proyecto.md): NO se inventan coordenadas. Las coordenadas (centroides)
de las UPZ solo pueden venir de una fuente oficial. Este módulo las lee de
datos/upz_coords.json, que genera scripts/generar_zonas.py a partir de un
GeoJSON oficial (datos/upz.geojson). Si ese archivo no existe, la asociación
queda "pendiente" y no se afirma ninguna cercanía.

La asociación es una TABLA ESTÁTICA: se calcula con las coordenadas conocidas de
estaciones (no requiere red). El módulo es puro y testeable con coords sintéticas.
"""
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ZONAS_JSON = RAIZ / "web" / "zonas.json"
UPZ_COORDS = RAIZ / "datos" / "upz_coords.json"   # lo genera scripts/generar_zonas.py


def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia en km entre dos puntos (lat, lon en grados)."""
    r = math.radians
    dlat = r(lat2 - lat1)
    dlon = r(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def estacion_mas_cercana(lat, lon, estaciones):
    """Devuelve (estacion, distancia_km) más cercana, o (None, None) si no hay.

    `estaciones`: lista de dicts con al menos lat y lon (float).
    """
    mejor, dmin = None, None
    for e in estaciones:
        if e.get("lat") is None or e.get("lon") is None:
            continue
        d = haversine_km(lat, lon, e["lat"], e["lon"])
        if dmin is None or d < dmin:
            mejor, dmin = e, d
    if mejor is None:
        return None, None
    return mejor, round(dmin, 2)


def cargar_zonas():
    """UPZ desde web/zonas.json (lista de dicts)."""
    datos = json.loads(ZONAS_JSON.read_text(encoding="utf-8"))
    return datos.get("zonas", [])


def cargar_coords_upz():
    """Centroides oficiales de las UPZ si existen; si no, dict vacío.

    Formato de datos/upz_coords.json: {"id_upz": {"lat": .., "lon": ..}, ...}
    """
    if not UPZ_COORDS.exists():
        return {}
    try:
        return json.loads(UPZ_COORDS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def asociar(estaciones, coords_upz=None):
    """Asocia cada UPZ a la estación más cercana.

    `estaciones`: lista de dicts {uid/id, nombre, lat, lon}.
    `coords_upz`: dict {id_upz: {lat, lon}}; si None, se lee de disco.

    Devuelve dict con estado global y la lista de zonas. Si no hay coordenadas
    oficiales de una UPZ, esa zona queda estado="pendiente" (no se inventa).
    """
    if coords_upz is None:
        coords_upz = cargar_coords_upz()
    zonas = cargar_zonas()
    resultado = []
    for z in zonas:
        c = coords_upz.get(z["id"])
        if not c or c.get("lat") is None or c.get("lon") is None:
            resultado.append({
                "id": z["id"], "nombre": z["nombre"],
                "estado": "pendiente",
                "motivo": "Sin coordenadas oficiales de la UPZ (ver scripts/generar_zonas.py).",
                "estacion": None, "distancia_km": None,
            })
            continue
        est, dist = estacion_mas_cercana(c["lat"], c["lon"], estaciones)
        if est is None:
            resultado.append({
                "id": z["id"], "nombre": z["nombre"],
                "estado": "sin_estacion",
                "motivo": "No hay estaciones con coordenadas disponibles para comparar.",
                "estacion": None, "distancia_km": None,
            })
            continue
        resultado.append({
            "id": z["id"], "nombre": z["nombre"],
            "estado": "ok",
            "estacion": {"uid": est.get("uid") or est.get("id"),
                         "nombre": est.get("nombre"),
                         "lat": est["lat"], "lon": est["lon"]},
            "distancia_km": dist,
        })
    hay_coords = bool(coords_upz)
    return {
        "localidad": "Ciudad Bolívar",
        "metodo": "haversine (centroide UPZ -> estación WAQI más cercana)",
        "fuente_coords_upz": "datos/upz_coords.json (oficial)" if hay_coords else "pendiente",
        "estado_global": "ok" if hay_coords else "pendiente",
        "zonas": resultado,
    }
