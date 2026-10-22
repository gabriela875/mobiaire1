"""De mediciones sueltas a un estado de calidad del aire por estación."""
import re
import unicodedata
from collections import defaultdict
from datetime import timedelta

from ingesta import config
from motor_ica.ica import calcular_ica


def slug(texto):
    """'Ciudad Bolívar' -> 'ciudad_bolivar' (id estable para la estación)."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def sin_tildes(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def coincide_estacion(nombre):
    """True si no hay filtro ESTACIONES o el nombre contiene alguno (sin tildes)."""
    if not config.ESTACIONES:
        return True
    n = sin_tildes(nombre)
    return any(sin_tildes(e) in n for e in config.ESTACIONES)


def promedio_24h(mediciones):
    """Promedio de 24 h de una serie (un contaminante, una estación).

    - Si el dato ya es un promedio de 24 h (duración >= 1440 min) se usa tal cual.
    - Si son datos horarios se promedian las últimas 24 h y se exige un
      mínimo de datos (MIN_DATOS_24H) para que el promedio sea representativo.
    Devuelve (promedio | None, n_datos, fecha_ultimo_dato).
    """
    por_fin = {}
    for m in mediciones:                       # quita duplicados por fecha
        por_fin[m.fin] = m
    serie = sorted(por_fin.values(), key=lambda m: m.fin)
    ultimo = serie[-1]

    if ultimo.duracion_min and ultimo.duracion_min >= 1440:
        return ultimo.valor, 1, ultimo.fin

    desde = ultimo.fin - timedelta(hours=24)
    ventana = [m for m in serie if m.fin > desde]
    if len(ventana) < config.MIN_DATOS_24H:
        return None, len(ventana), ultimo.fin
    return sum(m.valor for m in ventana) / len(ventana), len(ventana), ultimo.fin


def calcular_estaciones(mediciones, ahora):
    """Devuelve {id_estacion: estado} listo para guardar."""
    grupos = defaultdict(lambda: defaultdict(list))
    meta = {}
    for m in mediciones:
        if not coincide_estacion(m.estacion):
            continue
        sid = slug(m.estacion)
        grupos[sid][m.contaminante].append(m)
        meta[sid] = m

    resultado = {}
    for sid, por_contaminante in grupos.items():
        m0 = meta[sid]
        prom, n, ultimas = {}, {}, []
        for cont, serie in por_contaminante.items():
            prom[cont], n[cont], ultimo = promedio_24h(serie)
            ultimas.append(ultimo)
        ultima_medicion = max(ultimas)

        ica = calcular_ica(pm25=prom.get("PM25"), pm10=prom.get("PM10"))
        antiguedad_h = (ahora - ultima_medicion).total_seconds() / 3600
        estado = {
            "estacion": m0.estacion,
            "autoridad": m0.autoridad,
            "municipio": m0.municipio,
            "departamento": m0.departamento,
            "latitud": m0.latitud,
            "longitud": m0.longitud,
            "estado": "ok" if ica else "datos_insuficientes",
            "pm25_24h": round(prom["PM25"], 1) if prom.get("PM25") is not None else None,
            "pm10_24h": round(prom["PM10"], 1) if prom.get("PM10") is not None else None,
            "datos_pm25": n.get("PM25", 0),
            "datos_pm10": n.get("PM10", 0),
            "ultima_medicion": ultima_medicion.isoformat(),
            "desactualizado": antiguedad_h > config.MAX_ANTIGUEDAD_H,
            "sincronizado_en": ahora.isoformat(timespec="seconds"),
        }
        if ica:
            estado.update(ica)
        resultado[sid] = estado
    return resultado
