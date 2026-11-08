"""Distancia de cada zona (UPZ) a una estación de WAQI, para revisar la asociación zona-estación.

Uso:
    python -m scripts.comparar_estacion "Ciudad Bolivar"   # busca por nombre
    python -m scripts.comparar_estacion @1234              # por identificador (uid) de WAQI

Lee WAQI_TOKEN del .env (no lo imprime) y los centros de zona de datos/upz_coords.json.
"""
import json
import math
import os
import sys

import requests

from ingesta import config  # noqa: F401  (carga el .env)

ZONAS = config.RAIZ / "datos" / "upz_coords.json"
API = "https://api.waqi.info"


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia haversine en km."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def estaciones_de(respuesta):
    """Lista [(nombre, uid, lat, lon)] desde la respuesta de /search/ o /feed/@uid/."""
    if respuesta.get("status") != "ok":
        raise ValueError(f"WAQI respondió: {respuesta.get('data')}")
    datos = respuesta["data"]
    if isinstance(datos, dict):                       # /feed/@uid/
        ciudad = datos.get("city", {})
        geo = ciudad.get("geo") or []
        return [(ciudad.get("name", "?"), datos.get("idx"), geo[0], geo[1])] if len(geo) == 2 else []
    salida = []                                       # /search/
    for e in datos:
        geo = e.get("station", {}).get("geo") or []
        if len(geo) == 2:
            salida.append((e["station"].get("name", "?"), e.get("uid"), geo[0], geo[1]))
    return salida


def consultar(entrada, token):
    ruta = f"/feed/{entrada}/" if entrada.startswith("@") else "/search/"
    params = {"token": token} if entrada.startswith("@") else {"token": token, "keyword": entrada}
    r = requests.get(API + ruta, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python -m scripts.comparar_estacion "Ciudad Bolivar"  (o @uid)')
    token = os.environ.get("WAQI_TOKEN", "")
    if not token:
        sys.exit("Falta WAQI_TOKEN en el .env (en la carpeta raíz, sin comillas ni espacios).")
    if not ZONAS.exists():
        sys.exit("No existe datos/upz_coords.json. Ejecute: python -m scripts.generar_zonas")
    try:
        estaciones = estaciones_de(consultar(sys.argv[1], token))
    except (requests.RequestException, ValueError) as e:
        sys.exit(f"No se pudo consultar WAQI: {str(e).replace(token, '***')}")
    if not estaciones:
        sys.exit("WAQI no devolvió estaciones con coordenadas para esa búsqueda.")

    zonas = json.loads(ZONAS.read_text(encoding="utf-8"))
    for nombre, uid, lat, lon in estaciones:
        print(f"\nEstación: {nombre}  (uid {uid})  lat {lat}, lon {lon}")
        for zid, z in sorted(zonas.items(), key=lambda kv: distancia_km(kv[1]["lat"], kv[1]["lon"], lat, lon)):
            print(f"   {zid:16s} {distancia_km(z['lat'], z['lon'], lat, lon):5.2f} km")


if __name__ == "__main__":
    main()
