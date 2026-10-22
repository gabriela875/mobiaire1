"""Convierte un registro crudo de la API en una Medicion validada.

Si el formato cambia (falta una columna clave, valor no numérico, fecha rara)
lanza FormatoInvalido: la ingesta lo registra en el log y sigue, no se cae.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ingesta import config


class FormatoInvalido(Exception):
    pass


@dataclass
class Medicion:
    estacion: str
    autoridad: str
    contaminante: str            # "PM25" | "PM10"
    valor: float                 # µg/m3
    inicio: datetime
    fin: datetime
    duracion_min: Optional[int]
    latitud: Optional[float]
    longitud: Optional[float]
    municipio: str
    departamento: str


def _buscar(registro, campo, subcadenas=()):
    """Valor del primer candidato presente en el registro (o None)."""
    for nombre in config.CAMPOS[campo]:
        if nombre in registro and registro[nombre] not in (None, ""):
            return registro[nombre]
    for clave, valor in registro.items():
        if subcadenas and any(s in clave.lower() for s in subcadenas) and valor not in (None, ""):
            return valor
    return None


def _numero(texto):
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _fecha(texto):
    if not texto:
        return None
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "")[:19])
    except ValueError:
        return None


def normalizar_contaminante(texto):
    """Devuelve 'PM25', 'PM10' o None si no es material particulado."""
    t = re.sub(r"[^A-Z0-9.]", "", str(texto).upper().replace(",", "."))
    if "PM2.5" in t or "PM25" in t or ("2.5" in t and ("MATERIAL" in t or "PM" in t)):
        return "PM25"
    if "PM10" in t or ("10" in t and ("MATERIAL" in t or "PM" in t)):
        return "PM10"
    return None


def normalizar_registro(registro):
    """Medicion de PM2.5/PM10, o None si el registro es de otro contaminante."""
    if not isinstance(registro, dict):
        raise FormatoInvalido("el registro no es un objeto JSON")

    variable = _buscar(registro, "variable", config.SUBCADENAS_VARIABLE)
    if variable is None:
        raise FormatoInvalido("no se encontró la columna del contaminante/variable")
    contaminante = normalizar_contaminante(variable)
    if contaminante is None:
        return None                      # O3, NO2, temperatura, etc.: se ignora

    estacion = _buscar(registro, "estacion")
    valor = _numero(_buscar(registro, "valor"))
    inicio = _fecha(_buscar(registro, "inicio"))
    if estacion is None:
        raise FormatoInvalido("falta el nombre de la estación")
    if valor is None:
        raise FormatoInvalido("valor de concentración ausente o no numérico")
    if inicio is None:
        raise FormatoInvalido("fecha de medición ausente o inválida")
    if valor < 0:
        raise FormatoInvalido(f"concentración negativa: {valor}")

    duracion = _numero(_buscar(registro, "duracion"))
    return Medicion(
        estacion=str(estacion).strip(),
        autoridad=str(_buscar(registro, "autoridad") or "").strip(),
        contaminante=contaminante,
        valor=valor,
        inicio=inicio,
        fin=_fecha(_buscar(registro, "fin")) or inicio,
        duracion_min=int(duracion) if duracion is not None else None,
        latitud=_numero(_buscar(registro, "latitud")),
        longitud=_numero(_buscar(registro, "longitud")),
        municipio=str(_buscar(registro, "municipio") or "").strip(),
        departamento=str(_buscar(registro, "departamento") or "").strip(),
    )
