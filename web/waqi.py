"""Cliente de WAQI (World Air Quality Index) para MobiAire Materno.

SOLO LECTURA. El token vive en .env (variable WAQI_TOKEN) y NUNCA se expone al
frontend ni se devuelve en las respuestas. Este módulo:
  - Llama a la API de WAQI con el token del backend.
  - Cachea en disco (~10 min) para no golpear la API en cada carga ni gastar
    cuota.
  - Normaliza los datos (estación, uid, coords, AQI de WAQI, PM2.5/PM10, hora)
    SIN convertir el índice: el AQI de WAQI es escala US-EPA, NO es el ICA del
    proyecto. Se entrega como "indice de origen", claramente identificado.

IMPORTANTE: no toca el motor ICA, ni resultados.json, ni la ingesta histórica.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

# Reutiliza el cargador de .env del proyecto (sin dependencias nuevas).
sys.path.insert(0, str(RAIZ))
import os
from ingesta import config  # noqa: E402  (ejecuta _cargar_env() al importar)

BASE = "https://api.waqi.info"
CACHE = RAIZ / "ingesta" / "cache_waqi.json"   # junto a los demás datos; ignorado por git
CACHE_SEGUNDOS = int(os.getenv("WAQI_CACHE_S", "600"))   # 10 min por defecto
# Recuadro aproximado de Bogotá (lat_sur, lon_oeste, lat_norte, lon_este)
BBOX_BOGOTA = os.getenv("WAQI_BBOX", "4.45,-74.25,4.84,-73.99")
TIMEOUT = 20


class ErrorWAQI(Exception):
    """Fallo al consultar WAQI (sin red, token inválido, respuesta inesperada)."""


def hay_token():
    return bool(os.getenv("WAQI_TOKEN", "").strip())


def _token():
    t = os.getenv("WAQI_TOKEN", "").strip()
    if not t:
        raise ErrorWAQI("No hay WAQI_TOKEN en .env. Añádelo para usar datos recientes.")
    return t


def _pedir(ruta, params):
    """GET a WAQI. Nunca registra ni devuelve el token."""
    p = dict(params)
    p["token"] = _token()
    url = BASE + ruta + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": "MobiAire/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            cuerpo = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        # Enmascara el token si apareciera en el mensaje
        msg = str(e).replace(_token(), "***")
        raise ErrorWAQI(f"No se pudo consultar WAQI: {msg}")
    if cuerpo.get("status") != "ok":
        detalle = json.dumps(cuerpo.get("data"), ensure_ascii=False)
        raise ErrorWAQI(f"WAQI respondió error: {detalle}")
    return cuerpo.get("data")


# ---------------------------------------------------------------------------
# Caché en disco
# ---------------------------------------------------------------------------
def _leer_cache(clave):
    if not CACHE.exists():
        return None
    try:
        todo = json.loads(CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    item = todo.get(clave)
    if not item:
        return None
    if time.time() - item.get("ts", 0) > CACHE_SEGUNDOS:
        return None
    return item.get("valor")


def _guardar_cache(clave, valor):
    todo = {}
    if CACHE.exists():
        try:
            todo = json.loads(CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            todo = {}
    todo[clave] = {"ts": time.time(), "valor": valor}
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(todo, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE)


# ---------------------------------------------------------------------------
# Normalización (sin convertir escalas)
# ---------------------------------------------------------------------------
def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _estacion_de_feed(d):
    """Convierte la respuesta /feed/@uid en un dict normalizado del proyecto."""
    ciudad = d.get("city", {}) or {}
    iaqi = d.get("iaqi", {}) or {}
    geo = ciudad.get("geo") or [None, None]
    attrs = [a.get("name", "") for a in (d.get("attributions") or [])]
    return {
        "uid": d.get("idx"),
        "nombre": ciudad.get("name"),
        "lat": _num(geo[0]) if len(geo) > 0 else None,
        "lon": _num(geo[1]) if len(geo) > 1 else None,
        # AQI de WAQI (escala US-EPA). NO es el ICA del proyecto.
        "aqi_waqi": d.get("aqi"),
        "dominante": d.get("dominentpol"),
        "pm25": _num((iaqi.get("pm25") or {}).get("v")),
        "pm10": _num((iaqi.get("pm10") or {}).get("v")),
        "o3": _num((iaqi.get("o3") or {}).get("v")),
        "no2": _num((iaqi.get("no2") or {}).get("v")),
        "so2": _num((iaqi.get("so2") or {}).get("v")),
        "co": _num((iaqi.get("co") or {}).get("v")),
        "contaminantes": sorted(iaqi.keys()),
        # Hora de medición en zona local de la estación (viene en -05:00 en el feed)
        "medido_en": (d.get("time", {}) or {}).get("s"),
        "medido_iso": (d.get("time", {}) or {}).get("iso"),
        "fuente": "WAQI",
        "atribucion": attrs,
        "escala_indice": "US-EPA (WAQI) — no es el ICA del proyecto",
    }


def _reciente(iso, max_horas=6):
    """True si la medición es de las últimas `max_horas` (descarta estaciones muertas)."""
    if not iso:
        return False
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return False
    ahora = datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (ahora - t).total_seconds() <= max_horas * 3600


# ---------------------------------------------------------------------------
# API pública del módulo
# ---------------------------------------------------------------------------
def estaciones_bogota(forzar=False):
    """Lista de estaciones de Bogotá (con dato reciente). Usa /map/bounds.

    Devuelve dict: {generado_en, consultado_en, fuente, estaciones:[...]}.
    Cacheado ~10 min. Lanza ErrorWAQI si falla y no hay caché.
    """
    clave = "bogota_bounds"
    if not forzar:
        c = _leer_cache(clave)
        if c is not None:
            c = dict(c)
            c["desde_cache"] = True
            return c

    data = _pedir("/map/bounds/", {"latlng": BBOX_BOGOTA})
    estaciones = []
    for f in data or []:
        st = f.get("station", {}) or {}
        iso = st.get("time")
        estaciones.append({
            "uid": f.get("uid"),
            "nombre": st.get("name"),
            "lat": _num(f.get("lat")),
            "lon": _num(f.get("lon")),
            "aqi_waqi": f.get("aqi"),
            "medido_iso": iso,
            "reciente": _reciente(iso),
            "fuente": "WAQI",
            "escala_indice": "US-EPA (WAQI) — no es el ICA del proyecto",
        })
    # Orden: recientes primero, luego por nombre
    estaciones.sort(key=lambda e: (not e["reciente"], str(e["nombre"])))
    resultado = {
        "fuente": "WAQI / AQICN",
        "atribucion": ["World Air Quality Index Project", "OAB - Observatorio Ambiental de Bogotá"],
        "escala_indice": "US-EPA (WAQI) — no es el ICA del proyecto MobiAire",
        "bbox": BBOX_BOGOTA,
        "consultado_en": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "estaciones": estaciones,
    }
    _guardar_cache(clave, resultado)
    resultado["desde_cache"] = False
    return resultado


def estacion(uid, forzar=False):
    """Detalle de una estación por uid (ej. 6235). Usa /feed/@uid. Cacheado."""
    clave = f"feed_{uid}"
    if not forzar:
        c = _leer_cache(clave)
        if c is not None:
            c = dict(c)
            c["desde_cache"] = True
            return c
    data = _pedir(f"/feed/@{uid}/", {})
    est = _estacion_de_feed(data)
    resultado = {
        "fuente": "WAQI / AQICN",
        "escala_indice": "US-EPA (WAQI) — no es el ICA del proyecto MobiAire",
        "consultado_en": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "estacion": est,
    }
    _guardar_cache(clave, resultado)
    resultado["desde_cache"] = False
    return resultado
