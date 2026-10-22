"""Prueba de conexión con WAQI — INDEPENDIENTE y de SOLO LECTURA.

No toca el motor ICA, ni el servidor web, ni resultados.json. Solo sirve para
comprobar que el token funciona y ver qué estaciones/datos entrega WAQI en
Bogotá y Ciudad Bolívar.

Uso (desde la raíz del repo, en tu computador CON internet):
    python probar_waqi.py

El token se lee de .env (variable WAQI_TOKEN). NUNCA se imprime en pantalla.
Si algo falla, se explica el motivo sin exponer la clave.
"""
import json
import sys
import urllib.parse
import urllib.request

# Reutiliza el mismo cargador de .env del proyecto (sin dependencias).
sys.path.insert(0, ".")
try:
    from ingesta import config  # ejecuta _cargar_env() al importarse
except Exception as e:
    print("No se pudo cargar la configuración del proyecto:", e)
    sys.exit(1)

import os

TOKEN = os.getenv("WAQI_TOKEN", "").strip()
BASE = "https://api.waqi.info"


def _enmascarar(txt):
    """Oculta el token si por accidente apareciera en un mensaje de error."""
    if TOKEN and TOKEN in txt:
        return txt.replace(TOKEN, "***TOKEN-OCULTO***")
    return txt


def pedir(ruta, params):
    params = dict(params)
    params["token"] = TOKEN
    url = BASE + ruta + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "MobiAire-prueba/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def seccion(titulo):
    print("\n" + "=" * 64 + "\n" + titulo + "\n" + "=" * 64)


def main():
    if not TOKEN:
        print("No hay WAQI_TOKEN en .env.")
        print("Añade una línea  WAQI_TOKEN=tu_token  al archivo .env y vuelve a intentar.")
        sys.exit(1)
    print(f"Token detectado en .env (longitud {len(TOKEN)} caracteres). No se mostrará su valor.")

    # 1) Prueba básica: feed de la ciudad de Bogotá -----------------------
    seccion("1) Feed de ciudad: /feed/bogota/")
    try:
        d = pedir("/feed/bogota/", {})
    except Exception as e:
        print("ERROR de conexión:", _enmascarar(str(e)))
        print("Comprueba: internet activo, token válido y que no haya firewall/proxy.")
        sys.exit(1)

    estado = d.get("status")
    print("status:", estado)
    if estado != "ok":
        # WAQI devuelve status 'error' y data con el motivo (p.ej. token inválido)
        print("La API respondió con error:", _enmascarar(json.dumps(d.get("data"), ensure_ascii=False)))
        print("Si dice 'Invalid key', el token no es correcto o no está activado aún.")
        sys.exit(1)

    data = d.get("data", {})
    ciudad = data.get("city", {})
    iaqi = data.get("iaqi", {})
    print("  Estación/ciudad :", ciudad.get("name"))
    print("  AQI (WAQI, US-EPA):", data.get("aqi"), " (NO es el ICA del proyecto)")
    print("  Contaminante dominante:", data.get("dominentpol"))
    print("  Medido (time.s):", data.get("time", {}).get("s"), data.get("time", {}).get("tz", ""))
    print("  Coordenadas:", ciudad.get("geo"))
    print("  Contaminantes disponibles (iaqi):", ", ".join(sorted(iaqi.keys())) or "ninguno")
    print("  PM2.5:", iaqi.get("pm25", {}).get("v", "NO disponible"))
    print("  PM10 :", iaqi.get("pm10", {}).get("v", "NO disponible"))
    attr = data.get("attributions", [])
    print("  Atribuciones:", "; ".join(a.get("name", "") for a in attr) or "sin datos")

    # 2) Búsqueda de estaciones que contengan 'bogota' -------------------
    seccion("2) Estaciones encontradas: /search/?keyword=bogota")
    try:
        s = pedir("/search/", {"keyword": "bogota"})
        if s.get("status") == "ok":
            filas = s.get("data", [])
            print(f"  {len(filas)} estaciones devueltas. Primeras (nombre · AQI · medido · coord):")
            for f in filas[:25]:
                st = f.get("station", {})
                print(f"   - {st.get('name')} · AQI {f.get('aqi')} · {f.get('time', {}).get('stime', f.get('time', {}).get('vtime'))} · {st.get('geo')}")
        else:
            print("  search respondió:", _enmascarar(json.dumps(s.get("data"), ensure_ascii=False)))
    except Exception as e:
        print("  ERROR en search:", _enmascarar(str(e)))

    # 3) Búsqueda específica de Ciudad Bolívar ---------------------------
    seccion("3) Búsqueda de 'ciudad bolivar'")
    try:
        s = pedir("/search/", {"keyword": "ciudad bolivar"})
        filas = s.get("data", []) if s.get("status") == "ok" else []
        if filas:
            for f in filas[:15]:
                st = f.get("station", {})
                print(f"   - {st.get('name')} · AQI {f.get('aqi')} · {st.get('geo')}")
        else:
            print("  Sin resultados directos para 'ciudad bolivar'.")
    except Exception as e:
        print("  ERROR:", _enmascarar(str(e)))

    # 4) Estaciones dentro del recuadro de Bogotá (map/bounds) -----------
    seccion("4) Estaciones en el recuadro de Bogotá: /map/bounds/")
    # Recuadro aproximado de Bogotá (lat1,lng1,lat2,lng2)
    bbox = "4.45,-74.25,4.84,-73.99"
    try:
        m = pedir("/map/bounds/", {"latlng": bbox})
        if m.get("status") == "ok":
            filas = m.get("data", [])
            print(f"  {len(filas)} estaciones dentro del recuadro de Bogotá:")
            for f in filas:
                st = f.get("station", {})
                print(f"   - uid {f.get('uid')} · {st.get('name')} · AQI {f.get('aqi')} · ({f.get('lat')},{f.get('lon')}) · {st.get('time')}")
        else:
            print("  map/bounds respondió:", _enmascarar(json.dumps(m.get("data"), ensure_ascii=False)))
    except Exception as e:
        print("  ERROR en map/bounds:", _enmascarar(str(e)))

    seccion("RESUMEN")
    print("Si viste 'status: ok' en el punto 1, el token FUNCIONA.")
    print("Revisa en los puntos 2–4 qué estaciones de Bogotá/Ciudad Bolívar aparecen,")
    print("sus coordenadas, su AQI (escala WAQI, NO el ICA del proyecto) y la fecha de medición.")


if __name__ == "__main__":
    main()
