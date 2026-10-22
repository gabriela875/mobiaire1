"""Motor ICA de MobiAire (PM2.5 y PM10, Resolución 2254 de 2017).

Fórmula (interpolación lineal por tramos):
    ICA = (I_hi - I_lo) / (BP_hi - BP_lo) * (C - BP_lo) + I_lo

Se calcula el ICA de cada contaminante, se toma el mayor y se clasifica
en el semáforo de 3 niveles del proyecto:
    verde   = ICA 0-100   (oficial: verde + amarillo)
    naranja = ICA 101-150 (oficial: naranja)
    rojo    = ICA 151-500 (oficial: rojo + púrpura + marrón)

Las concentraciones son promedios de 24 horas en µg/m3.
"""

# (ICA_min, ICA_max, conc_min, conc_max)
# Naranja y rojo: confirmados contra informes que citan la Res. 2254/2017
# (PM10 155-254 / 255-354; PM2.5 38-55 / 56-150).
# VERIFICAR contra la tabla oficial: verde/amarillo y púrpura/marrón.
# Esos dos últimos tramos no cambian el semáforo (todo >=151 es rojo).
TRAMOS = {
    "PM25": [
        (0, 50, 0, 12),
        (51, 100, 13, 37),
        (101, 150, 38, 55),
        (151, 200, 56, 150),
        (201, 300, 151, 250),
        (301, 500, 251, 500),
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

CATEGORIAS_OFICIALES = [
    (50, "verde"), (100, "amarillo"), (150, "naranja"),
    (200, "rojo"), (300, "purpura"), (500, "marron"),
]


def _redondear(concentracion):
    """Redondea a entero (los tramos oficiales no tienen decimales).

    Decisión del equipo: evita huecos entre tramos (ej. 12.4 µg/m3).
    """
    return int(concentracion + 0.5)


def calcular_ica_contaminante(contaminante, concentracion):
    """ICA (entero 0-500) de un contaminante ('PM25' o 'PM10')."""
    if contaminante not in TRAMOS:
        raise ValueError(f"Contaminante no soportado: {contaminante}")
    if concentracion is None or concentracion < 0:
        raise ValueError(f"Concentración inválida: {concentracion}")

    c = _redondear(concentracion)
    tramos = TRAMOS[contaminante]
    if c > tramos[-1][3]:           # por encima de la tabla: tope 500
        return 500
    for i_lo, i_hi, bp_lo, bp_hi in tramos:
        if bp_lo <= c <= bp_hi:
            return round((i_hi - i_lo) / (bp_hi - bp_lo) * (c - bp_lo) + i_lo)
    raise ValueError(f"Sin tramo para {contaminante}={concentracion}")


def clasificar(ica):
    """Semáforo de 3 niveles a partir del ICA numérico."""
    if ica < 0 or ica > 500:
        raise ValueError(f"ICA fuera de rango: {ica}")
    if ica <= 100:
        return "verde"
    if ica <= 150:
        return "naranja"
    return "rojo"


def categoria_oficial(ica):
    """Una de las 6 categorías oficiales de la Res. 2254."""
    for tope, nombre in CATEGORIAS_OFICIALES:
        if ica <= tope:
            return nombre
    return "marron"


def calcular_ica(pm25=None, pm10=None):
    """ICA final de una estación a partir de PM2.5 y/o PM10 (24 h, µg/m3).

    Devuelve None si no hay ningún dato. Si falta uno de los dos
    contaminantes calcula con el otro y marca completo=False.
    """
    icas = {}
    if pm25 is not None:
        icas["PM25"] = calcular_ica_contaminante("PM25", pm25)
    if pm10 is not None:
        icas["PM10"] = calcular_ica_contaminante("PM10", pm10)
    if not icas:
        return None

    dominante = max(icas, key=icas.get)
    ica = icas[dominante]
    return {
        "ica": ica,
        "nivel": clasificar(ica),
        "categoria": categoria_oficial(ica),
        "contaminante_dominante": dominante,
        "ica_pm25": icas.get("PM25"),
        "ica_pm10": icas.get("PM10"),
        "completo": len(icas) == 2,
    }
