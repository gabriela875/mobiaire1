"""Consulta a la API de datos abiertos con reintentos y espera creciente."""
import json
import logging
import time
from datetime import datetime, timedelta

import requests

from ingesta import config

log = logging.getLogger("mobiaire.ingesta")


class ErrorFuente(Exception):
    """La fuente no respondió bien tras agotar los reintentos."""


def _filtro_estaciones():
    """Condición SoQL para pedir solo las estaciones de ESTACIONES (vacío = todas)."""
    if not config.ESTACIONES:
        return ""
    col = config.CAMPOS["estacion"][0]
    conds = [f"upper({col}) like '%{e.upper().replace(chr(39), '')}%'" for e in config.ESTACIONES]
    return "(" + " OR ".join(conds) + ")"


def _get(sesion, params, headers, dormir):
    """GET con reintentos (3 por defecto) y espera creciente 2s, 4s, 8s..."""
    ultimo_error = None
    for intento in range(1, config.REINTENTOS + 1):
        try:
            resp = sesion.get(config.API_URL, params=params, headers=headers,
                              timeout=config.TIMEOUT_S)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code} (temporal)")
            if resp.status_code >= 400:     # error nuestro (URL, consulta): no tiene caso reintentar
                raise ErrorFuente(f"HTTP {resp.status_code}: {resp.text[:200]}")
            datos = resp.json()
            if not isinstance(datos, list):
                raise ErrorFuente(f"se esperaba una lista y llegó {type(datos).__name__}: {str(datos)[:200]}")
            return datos
        except ErrorFuente:
            raise
        except (requests.RequestException, ValueError) as e:
            ultimo_error = e
            espera = config.ESPERA_BASE_S * 2 ** (intento - 1)
            log.warning("Intento %d/%d falló (%s).%s", intento, config.REINTENTOS, e,
                        f" Reintento en {espera:.0f}s" if intento < config.REINTENTOS else "")
            if intento < config.REINTENTOS:
                dormir(espera)
    raise ErrorFuente(f"fuente no disponible tras {config.REINTENTOS} intentos: {ultimo_error}")


def _fecha_base(ahora, sesion, headers, dormir):
    """Fecha desde la que se cuentan los DIAS_ATRAS (ver FECHA_REFERENCIA en config)."""
    ref = config.FECHA_REFERENCIA.strip()
    if not ref:
        return ahora
    if ref.lower() != "auto":
        return datetime.fromisoformat(ref)
    params = {"$select": f"max({config.CAMPO_FECHA_SOQL}) as ultima"}
    filtro = _filtro_estaciones()
    if filtro:
        params["$where"] = filtro
    filas = _get(sesion, params, headers, dormir)
    if filas and filas[0].get("ultima"):
        base = datetime.fromisoformat(filas[0]["ultima"][:19])
        if (ahora - base).days > 7:
            log.warning("La fuente NO es en tiempo real: su dato más reciente es %s. "
                        "Se calcula con esa fecha como referencia (datos históricos).", base)
        return base
    return ahora


def obtener_registros(ahora=None, sesion=None, dormir=time.sleep):
    """Lista de registros crudos (dict). Lanza ErrorFuente si falla.

    `sesion` y `dormir` son inyectables para poder probar sin red.
    """
    if config.FUENTE_LOCAL:
        with open(config.FUENTE_LOCAL, encoding="utf-8") as f:
            return json.load(f)

    ahora = ahora or datetime.now()
    sesion = sesion or requests.Session()
    headers = {"Accept": "application/json"}
    if config.API_APP_TOKEN:
        headers["X-App-Token"] = config.API_APP_TOKEN

    base = _fecha_base(ahora, sesion, headers, dormir)
    desde = (base - timedelta(days=config.DIAS_ATRAS)).strftime("%Y-%m-%dT%H:%M:%S")
    condiciones = [f"{config.CAMPO_FECHA_SOQL} >= '{desde}'"]
    if _filtro_estaciones():
        condiciones.append(_filtro_estaciones())
    if config.FILTRO_VARIABLE_SOQL:
        condiciones.append(f"({config.FILTRO_VARIABLE_SOQL})")
    if config.FILTRO_SOQL:
        condiciones.append(f"({config.FILTRO_SOQL})")
    params = {
        "$where": " AND ".join(condiciones),
        "$order": f"{config.CAMPO_FECHA_SOQL} DESC, {config.CAMPOS['estacion'][0]}",
        "$limit": config.LIMITE_REGISTROS,
    }
    # Paginación: sigue pidiendo páginas mientras vengan completas (nada se corta en silencio)
    registros = []
    for pagina in range(config.MAX_PAGINAS):
        params["$offset"] = pagina * config.LIMITE_REGISTROS
        datos = _get(sesion, params, headers, dormir)
        registros.extend(datos)
        if len(datos) < config.LIMITE_REGISTROS:
            break
    else:
        log.warning("Se alcanzó MAX_PAGINAS=%d: puede haber datos sin leer. Use ESTACIONES o "
                    "reduzca DIAS_ATRAS.", config.MAX_PAGINAS)
    return registros
