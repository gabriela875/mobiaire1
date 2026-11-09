"""Conversión del sub-índice AQI de WAQI (escala US-EPA) a nuestro ICA (Res. 2254).

WAQI entrega el AQI ya calculado por contaminante (sub-índice US-EPA, 0-500), NO
la concentración. Para alimentar nuestro motor (que trabaja en µg/m³) hacemos:

    sub-índice AQI (EPA)  --interpolación inversa-->  concentración µg/m³
    concentración µg/m³   --motor_ica.ica (Res 2254)-->  ICA del proyecto

Es una APROXIMACIÓN y así se documenta (ver .kiro/steering/proyecto.md):
  - depende de la versión de la tabla EPA que use WAQI;
  - es un valor horario, no el promedio de 24 h que pide la norma.
Por eso el resultado se rotula "ICA estimado (derivado de WAQI)" y NUNCA se
presenta como el ICA oficial ni se mezcla con el índice WAQI original.

No modifica motor_ica/ica.py: lo reutiliza.
"""
from motor_ica import ica as _ica

# Breakpoints oficiales de la US-EPA (40 CFR Part 58, actualización PM2.5 2024).
# (AQI_lo, AQI_hi, C_lo, C_hi). Concentraciones en µg/m³, promedio 24 h.
# PM2.5 con los cortes vigentes desde 2024 (9.0/35.4/...); PM10 estándar EPA.
EPA = {
    "PM25": [
        (0, 50, 0.0, 9.0),
        (51, 100, 9.1, 35.4),
        (101, 150, 35.5, 55.4),
        (151, 200, 55.5, 125.4),
        (201, 300, 125.5, 225.4),
        (301, 500, 225.5, 500.4),
    ],
    "PM10": [
        (0, 50, 0, 54),
        (51, 100, 55, 154),
        (101, 150, 155, 254),
        (151, 200, 255, 354),
        (201, 300, 355, 424),
        (301, 500, 425, 604),
    ],
}


def subindice_a_concentracion(contaminante, aqi):
    """Interpolación inversa EPA: sub-índice AQI -> concentración µg/m³.

    Devuelve None si el sub-índice no es un número válido en 0-500.
    """
    if contaminante not in EPA:
        raise ValueError(f"Contaminante no soportado: {contaminante}")
    if aqi is None:
        return None
    try:
        aqi = float(aqi)
    except (TypeError, ValueError):
        return None
    if aqi < 0 or aqi > 500:
        return None
    for i_lo, i_hi, c_lo, c_hi in EPA[contaminante]:
        if i_lo <= aqi <= i_hi:
            # inversa de la fórmula AQI lineal por tramos
            return (aqi - i_lo) / (i_hi - i_lo) * (c_hi - c_lo) + c_lo
    return None


def ica_desde_waqi(aqi_pm25=None, aqi_pm10=None):
    """ICA del proyecto (Res. 2254) a partir de los sub-índices WAQI.

    Recibe los sub-índices AQI (US-EPA) de PM2.5 y/o PM10 que entrega WAQI.
    Devuelve el mismo formato que motor_ica.ica.calcular_ica, más:
      - estimado=True y nota (es aproximación horaria derivada de WAQI).
    Devuelve None si no hay ningún sub-índice utilizable.
    """
    pm25 = subindice_a_concentracion("PM25", aqi_pm25)
    pm10 = subindice_a_concentracion("PM10", aqi_pm10)
    r = _ica.calcular_ica(pm25=pm25, pm10=pm10)
    if r is None:
        return None
    r = dict(r)
    r["estimado"] = True
    r["origen"] = "WAQI (sub-índice US-EPA) -> concentración -> ICA Res. 2254"
    r["nota"] = ("ICA estimado (derivado de WAQI): aproximación horaria, no el "
                 "promedio de 24 h de la norma.")
    # Concentraciones derivadas (redondeadas) para mostrar de dónde sale
    r["pm25_estimado_ugm3"] = round(pm25, 1) if pm25 is not None else None
    r["pm10_estimado_ugm3"] = round(pm10, 1) if pm10 is not None else None
    return r
