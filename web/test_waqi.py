"""Pruebas de web/waqi.py que no requieren red: rutas, hora y unidades."""
import pytest

from web import waqi


def test_ruta_feed_acepta_formatos():
    assert waqi._ruta_feed("6235") == "/feed/@6235/"
    assert waqi._ruta_feed("@6235") == "/feed/@6235/"
    assert waqi._ruta_feed("A522148") == "/feed/A522148/"
    # idx negativo de /map/bounds (estación externa) -> se consulta como A{abs}
    assert waqi._ruta_feed("-522148") == "/feed/A522148/"
    assert waqi._ruta_feed(-522148) == "/feed/A522148/"


def test_ruta_feed_rechaza_invalidos():
    for mal in ("abc", "../x", "@@3", "A", "@", "-", "--5", "A12x"):
        with pytest.raises(waqi.ErrorWAQI):
            waqi._ruta_feed(mal)


def test_a_hora_bogota_convierte_offset():
    # +09:00 (como da map/bounds) -> -05:00 (Bogotá), mismo instante
    assert waqi.a_hora_bogota("2026-11-09T05:00:00+09:00") == "2026-11-08T15:00-05:00"


def test_texto_hora_bogota_legible():
    t = waqi.texto_hora_bogota("2026-11-08T16:00:00-05:00")
    assert "8 nov 2026" in t and "4:00 p. m." in t and "Bogotá" in t
    # medianoche y mediodía
    assert "12:00 a. m." in waqi.texto_hora_bogota("2026-11-08T00:00:00-05:00")
    assert "12:00 p. m." in waqi.texto_hora_bogota("2026-11-08T12:00:00-05:00")
    assert waqi.texto_hora_bogota(None) is None


def test_estacion_de_feed_unescape_y_unidades():
    d = {"idx": -522148, "aqi": 52, "dominentpol": "pm25",
         "city": {"name": "Ciudad Bol&iacute;var", "geo": ["4.57", "-74.16"]},
         "iaqi": {"pm25": {"v": 52}, "pm10": {"v": 50}},
         "time": {"iso": "2026-11-08T09:00:00-05:00"},
         "attributions": [{"name": "OAB - Bogot&aacute;"}]}
    e = waqi._estacion_de_feed(d)
    assert "&iacute;" not in e["nombre"] and e["nombre"] == "Ciudad Bolívar"
    assert "&aacute;" not in e["atribucion"][0]
    # los valores son sub-índices AQI, no µg/m³
    assert e["aqi_pm25"] == 52 and "pm25" not in e
    assert "NO µg/m³" in e["unidad_valores"]
