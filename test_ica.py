import pytest
from motor_ica.ica import (calcular_ica, calcular_ica_contaminante,
                           categoria_oficial, clasificar)


@pytest.mark.parametrize("ica,nivel", [
    (0, "verde"), (100, "verde"), (101, "naranja"),
    (150, "naranja"), (151, "rojo"), (500, "rojo"),
])
def test_clasificar_limites(ica, nivel):
    assert clasificar(ica) == nivel


def test_clasificar_fuera_de_rango():
    with pytest.raises(ValueError):
        clasificar(501)


@pytest.mark.parametrize("contaminante,conc,ica", [
    ("PM25", 12, 50), ("PM25", 13, 51), ("PM25", 37, 100),
    ("PM25", 38, 101), ("PM25", 55, 150), ("PM25", 56, 151),
    ("PM10", 54, 50), ("PM10", 55, 51), ("PM10", 154, 100),
    ("PM10", 155, 101), ("PM10", 254, 150), ("PM10", 255, 151),
])
def test_valores_limite_de_la_tabla(contaminante, conc, ica):
    assert calcular_ica_contaminante(contaminante, conc) == ica


def test_interpolacion_intermedia():
    # PM2.5 = 25 en tramo 13-37 (ICA 51-100): 49/24*12+51 = 75.5 -> 76
    assert calcular_ica_contaminante("PM25", 25) == 76


def test_decimales_se_redondean_sin_huecos():
    assert calcular_ica_contaminante("PM25", 12.4) == 50
    assert calcular_ica_contaminante("PM25", 12.5) == 51


def test_tope_500():
    assert calcular_ica_contaminante("PM10", 9999) == 500


def test_toma_el_mayor_y_dominante():
    r = calcular_ica(pm25=40, pm10=60)
    assert r["contaminante_dominante"] == "PM25"
    assert r["nivel"] == "naranja" and r["completo"] is True


def test_un_solo_contaminante():
    r = calcular_ica(pm10=300)
    assert r["nivel"] == "rojo" and r["completo"] is False


def test_sin_datos():
    assert calcular_ica() is None


def test_entradas_invalidas():
    with pytest.raises(ValueError):
        calcular_ica_contaminante("PM25", -1)
    with pytest.raises(ValueError):
        calcular_ica_contaminante("O3", 10)


def test_categoria_oficial():
    assert categoria_oficial(75) == "amarillo"
    assert categoria_oficial(350) == "marron"
