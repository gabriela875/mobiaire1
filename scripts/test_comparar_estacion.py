import pytest

from scripts.comparar_estacion import distancia_km, estaciones_de


def test_distancia_cero_y_un_grado():
    assert distancia_km(4.5, -74.1, 4.5, -74.1) == 0
    assert distancia_km(0, 0, 1, 0) == pytest.approx(111.2, abs=0.2)


def test_parsea_busqueda_y_feed_y_error():
    busqueda = {"status": "ok", "data": [
        {"uid": 1, "station": {"name": "A", "geo": [4.5, -74.1]}},
        {"uid": 2, "station": {"name": "sin geo"}}]}
    assert estaciones_de(busqueda) == [("A", 1, 4.5, -74.1)]
    feed = {"status": "ok", "data": {"idx": 7, "city": {"name": "B", "geo": [4.6, -74.2]}}}
    assert estaciones_de(feed) == [("B", 7, 4.6, -74.2)]
    with pytest.raises(ValueError):
        estaciones_de({"status": "error", "data": "Invalid key"})
