"""Pruebas de la conversión sub-índice WAQI (US-EPA) -> ICA del proyecto."""
import pytest

from motor_ica.conversion_waqi import ica_desde_waqi, subindice_a_concentracion


def test_subindice_a_concentracion_limites_pm25():
    # AQI 50 -> tope del primer tramo EPA (9.0 µg/m³)
    assert subindice_a_concentracion("PM25", 50) == pytest.approx(9.0, abs=0.01)
    # AQI 0 -> 0
    assert subindice_a_concentracion("PM25", 0) == pytest.approx(0.0, abs=0.01)


def test_subindice_invalido_devuelve_none():
    assert subindice_a_concentracion("PM25", None) is None
    assert subindice_a_concentracion("PM25", -5) is None
    assert subindice_a_concentracion("PM25", 999) is None
    assert subindice_a_concentracion("PM25", "n/d") is None


def test_contaminante_no_soportado():
    with pytest.raises(ValueError):
        subindice_a_concentracion("O3", 50)


def test_ica_desde_waqi_marca_estimado_y_nivel():
    r = ica_desde_waqi(aqi_pm25=52, aqi_pm10=50)
    assert r is not None
    assert r["estimado"] is True
    assert r["nivel"] in ("verde", "naranja", "rojo")
    # concentración derivada expuesta (para transparencia)
    assert r["pm25_estimado_ugm3"] is not None
    assert "WAQI" in r["origen"]


def test_ica_desde_waqi_sin_datos_es_none():
    assert ica_desde_waqi(aqi_pm25=None, aqi_pm10=None) is None


def test_no_mezcla_escala_valor_waqi_no_es_el_ica():
    # Un sub-índice WAQI alto de PM2.5 (ej 160) NO debe copiarse como ICA tal cual:
    # se convierte a concentración (>55 µg/m³) y da un ICA del proyecto propio.
    r = ica_desde_waqi(aqi_pm25=160)
    assert r is not None
    assert r["ica"] != 160  # no es una copia del sub-índice
