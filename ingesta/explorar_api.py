"""Revisa la API real y dice si CAMPOS (config.py) está bien. Ejecutar UNA vez.

    python -m ingesta.explorar_api

Muestra: columnas reales, cuál detecta para cada campo, qué contaminantes
hay, la fecha de dato más reciente y las estaciones de Bogotá/Soacha.
"""
import json
import sys

import requests

from ingesta import config
from ingesta.normalizador import _buscar, normalizar_contaminante


def consultar(params):
    h = {"X-App-Token": config.API_APP_TOKEN} if config.API_APP_TOKEN else {}
    r = requests.get(config.API_URL, params=params, headers=h, timeout=config.TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def main():
    print(f"API: {config.API_URL}\n")
    try:
        muestra = consultar({"$limit": 3, "$order": f"{config.CAMPO_FECHA_SOQL} DESC"})
    except Exception as e:
        sys.exit(f"No se pudo consultar la API: {e}")
    if not muestra:
        sys.exit("La API respondió vacío.")

    print("1) Registro de ejemplo (pegue esto en el chat/documento del equipo):")
    print(json.dumps(muestra[0], ensure_ascii=False, indent=2))

    print("\n2) Campos detectados (None = revisar CAMPOS en config.py):")
    from ingesta.config import SUBCADENAS_VARIABLE
    for campo in config.CAMPOS:
        sub = SUBCADENAS_VARIABLE if campo == "variable" else ()
        print(f"   {campo:13s} -> {_buscar(muestra[0], campo, sub)!r}")

    print("\n3) Fecha de dato más reciente en el dataset:")
    print("  ", muestra[0].get(config.CAMPO_FECHA_SOQL))

    var_col = next((c for c in config.CAMPOS["variable"] if c in muestra[0]), None) or \
        next((k for k in muestra[0] if any(x in k.lower() for x in SUBCADENAS_VARIABLE)), None)
    if var_col:
        print(f"\n4) Valores de la columna '{var_col}' (cómo los interpreta MobiAire):")
        for fila in consultar({"$select": f"{var_col}, count(*) as n", "$group": var_col,
                               "$order": "n DESC", "$limit": 60}):
            v = fila.get(var_col)
            print(f"   {str(v):30s} {fila.get('n'):>10} registros -> {normalizar_contaminante(v) or 'se ignora'}")
        print("   (Solo PM25 y PM10 entran al ICA. Si el PM está con otro código, avísenos.)")
        pm = consultar({"$where": f"upper({var_col}) like 'PM%'", "$limit": 1,
                        "$order": f"{config.CAMPO_FECHA_SOQL} DESC"})
        if pm:
            print("\n   Último registro de material particulado:")
            print(json.dumps(pm[0], ensure_ascii=False, indent=2))
    else:
        print("\n4) No se encontró columna de contaminante: revise el registro del punto 1.")

    print("\n5) Estaciones de Bogotá y Soacha (últimos datos):")
    est_col = config.CAMPOS["estacion"][0]
    filtro = "upper(municipio) like '%BOGOT%' OR upper(municipio) like '%SOACHA%'"
    try:
        for fila in consultar({"$select": f"{est_col}, max({config.CAMPO_FECHA_SOQL}) as ultima",
                               "$where": filtro, "$group": est_col, "$order": "ultima DESC"}):
            print(f"   {fila.get(est_col)!s:40s} {fila.get('ultima')}")
    except Exception as e:
        print(f"   (consulta no disponible: {e}). Pruebe FILTRO_SOQL con otro campo.")


if __name__ == "__main__":
    main()
