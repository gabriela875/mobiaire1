"""Datos SINTÉTICOS con el mismo formato que la API (solo para demo y pruebas)."""
import json
from datetime import datetime, timedelta

from ingesta import config

# (estación, PM2.5 base, PM10 base): una verde, una naranja, una roja
ESTACIONES_DEMO = [
    ("Ciudad Bolívar", 8, 35, 4.5780, -74.1544),
    ("Tunal", 45, 120, 4.5762, -74.1306),
    ("Estacion Demo Roja", 80, 300, 4.60, -74.10),
]


def generar_registros(ahora=None, horas=30):
    ahora = (ahora or datetime.now()).replace(minute=0, second=0, microsecond=0)
    registros = []
    for nombre, pm25, pm10, lat, lon in ESTACIONES_DEMO:
        for h in range(horas):
            ini = ahora - timedelta(hours=h + 1)
            base = {
                "nombre_fgda": "SECRETARIA DISTRITAL DE AMBIENTE (DEMO)",
                "nombre_est": nombre,
                "departamento": "BOGOTÁ",
                "municipio": "BOGOTÁ, D.C.",
                "latitud": str(lat), "longitud": str(lon),
                "med_fecha_inicio": ini.strftime("%Y-%m-%dT%H:%M:%S.000"),
                "med_fecha_final": (ini + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000"),
                "duraci_n": "60", "sigla_unidad": "µg/m3",
            }
            wiggle = (h % 5) - 2
            registros.append({**base, "msfl_code": "PM2.5", "med_concentracion_estandar": str(pm25 + wiggle)})
            registros.append({**base, "msfl_code": "PM10", "med_concentracion_estandar": str(pm10 + 2 * wiggle)})
            registros.append({**base, "msfl_code": "RGlobal", "med_concentracion_estandar": "40"})  # se ignora
    return registros


def generar(ruta=None):
    ruta = ruta or config.RAIZ / "ingesta" / "datos_demo.json"
    ruta.write_text(json.dumps(generar_registros(), ensure_ascii=False), encoding="utf-8")
    return ruta
