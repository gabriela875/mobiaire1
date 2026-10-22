import json
from datetime import datetime

import pytest
import requests

from ingesta import almacen, config, demo
from ingesta.calculo import calcular_estaciones, slug
from ingesta.cliente_api import ErrorFuente, obtener_registros
from ingesta.ingesta import ejecutar_ciclo
from ingesta.normalizador import FormatoInvalido, normalizar_contaminante, normalizar_registro

AHORA = datetime(2026, 10, 21, 12, 0, 0)


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SALIDA_JSON", tmp_path / "resultados.json")
    monkeypatch.setattr(config, "FUENTE_LOCAL", "")
    monkeypatch.setattr(config, "FECHA_REFERENCIA", "")
    monkeypatch.setattr(config, "ESTACIONES", [])
    monkeypatch.setattr(config, "FIREBASE_CREDENCIALES", "")
    return tmp_path


class RespuestaFalsa:
    def __init__(self, status=200, cuerpo=None):
        self.status_code, self._c, self.text = status, cuerpo, str(cuerpo)

    def json(self):
        if self._c is None:
            raise ValueError("no es JSON")
        return self._c


class SesionFalsa:
    def __init__(self, *respuestas):
        self.respuestas, self.llamadas = list(respuestas), 0

    def get(self, *a, **k):
        self.llamadas += 1
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


# ---------- normalizador ----------
@pytest.mark.parametrize("texto,esperado", [
    ("PM2.5", "PM25"), ("PM2,5", "PM25"), ("pm25", "PM25"), ("PM10", "PM10"),
    ("Material particulado menor a 2.5 micras", "PM25"),
    ("Material particulado menor a 10 micras", "PM10"),
    ("O3", None), ("Temperatura", None),
])
def test_normalizar_contaminante(texto, esperado):
    assert normalizar_contaminante(texto) == esperado


def test_registro_valido_y_otro_contaminante():
    base = demo.generar_registros(AHORA, horas=1)
    pm25, pm10, o3 = base[0], base[1], base[2]
    assert normalizar_registro(pm25).contaminante == "PM25"
    assert normalizar_registro(pm10).contaminante == "PM10"
    assert normalizar_registro(o3) is None


def test_formato_roto_lanza_error_controlado():
    with pytest.raises(FormatoInvalido):
        normalizar_registro({"otra_cosa": 1})
    r = demo.generar_registros(AHORA, horas=1)[0]
    r["med_concentracion_estandar"] = "N/D"
    with pytest.raises(FormatoInvalido):
        normalizar_registro(r)


# ---------- cálculo ----------
def test_calculo_demo_da_verde_naranja_rojo():
    ms = [normalizar_registro(r) for r in demo.generar_registros(AHORA)]
    est = calcular_estaciones([m for m in ms if m], AHORA)
    assert est["ciudad_bolivar"]["nivel"] == "verde"
    assert est["tunal"]["nivel"] == "naranja"
    assert est["estacion_demo_roja"]["nivel"] == "rojo"
    assert est["tunal"]["contaminante_dominante"] in ("PM25", "PM10")
    assert est["tunal"]["desactualizado"] is False


def test_pocos_datos_no_inventa_ica():
    ms = [normalizar_registro(r) for r in demo.generar_registros(AHORA, horas=5)]
    est = calcular_estaciones([m for m in ms if m], AHORA)
    assert est["tunal"]["estado"] == "datos_insuficientes" and "ica" not in est["tunal"]


def test_marca_desactualizado():
    ms = [normalizar_registro(r) for r in demo.generar_registros(datetime(2026, 10, 20, 0, 0))]
    est = calcular_estaciones([m for m in ms if m], AHORA)
    assert est["tunal"]["desactualizado"] is True


def test_slug():
    assert slug("Ciudad Bolívar") == "ciudad_bolivar"


# ---------- cliente: reintentos ----------
def test_reintenta_y_se_recupera(monkeypatch):
    esperas = []
    ses = SesionFalsa(requests.ConnectionError("sin red"), RespuestaFalsa(503),
                      RespuestaFalsa(200, [{"a": 1}]))
    datos = obtener_registros(AHORA, sesion=ses, dormir=esperas.append)
    assert datos == [{"a": 1}] and ses.llamadas == 3
    assert esperas == [config.ESPERA_BASE_S, config.ESPERA_BASE_S * 2]   # espera creciente


def test_agota_reintentos():
    ses = SesionFalsa(*[RespuestaFalsa(500)] * 3)
    with pytest.raises(ErrorFuente):
        obtener_registros(AHORA, sesion=ses, dormir=lambda s: None)
    assert ses.llamadas == config.REINTENTOS


def test_error_404_no_reintenta():
    ses = SesionFalsa(RespuestaFalsa(404, {"message": "no existe"}))
    with pytest.raises(ErrorFuente):
        obtener_registros(AHORA, sesion=ses, dormir=lambda s: None)
    assert ses.llamadas == 1


# ---------- ciclo completo ----------
def test_ciclo_completo_escribe_json(aislar):
    ses = SesionFalsa(RespuestaFalsa(200, demo.generar_registros(AHORA)))
    assert ejecutar_ciclo(AHORA, sesion=ses, dormir=lambda s: None) is True
    datos = json.loads(config.SALIDA_JSON.read_text(encoding="utf-8"))
    assert set(datos["estaciones"]) == {"ciudad_bolivar", "tunal", "estacion_demo_roja"}


def test_cambio_de_formato_no_se_cae_ni_pisa_el_resultado(aislar):
    almacen.guardar_json({"estaciones": {"previo": 1}})
    roto = [{"columna_nueva": "x", "otro": 2}] * 10
    ses = SesionFalsa(RespuestaFalsa(200, roto))
    assert ejecutar_ciclo(AHORA, sesion=ses, dormir=lambda s: None) is False
    assert json.loads(config.SALIDA_JSON.read_text())["estaciones"] == {"previo": 1}


def test_fuente_caida_no_se_cae(aislar):
    ses = SesionFalsa(*[requests.Timeout("lento")] * 3)
    assert ejecutar_ciclo(AHORA, sesion=ses, dormir=lambda s: None) is False


def test_filtro_por_estacion(monkeypatch):
    monkeypatch.setattr(config, "ESTACIONES", ["ciudad bol"])
    ms = [normalizar_registro(r) for r in demo.generar_registros(AHORA)]
    est = calcular_estaciones([m for m in ms if m], AHORA)
    assert list(est) == ["ciudad_bolivar"]


# ---------- resumen y .env ----------
def test_resumen_tabla_y_html(aislar):
    from ingesta import resumen
    ses = SesionFalsa(RespuestaFalsa(200, demo.generar_registros(AHORA)))
    ejecutar_ciclo(AHORA, sesion=ses, dormir=lambda s: None)
    datos = resumen.cargar()
    t = resumen.tabla(datos, color=False)
    assert "ROJO" in t and "NARANJA" in t and "VERDE" in t
    assert "Tunal" in resumen.pagina_html(datos)


def test_carga_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    (tmp_path / ".env").write_text("PRUEBA_X=hola # comentario\n# nada\n", encoding="utf-8")
    monkeypatch.delenv("PRUEBA_X", raising=False)
    config._cargar_env()
    import os
    assert os.environ["PRUEBA_X"] == "hola"


# ---------- fuente histórica ----------
def test_referencia_auto_usa_el_dato_mas_reciente(monkeypatch):
    monkeypatch.setattr(config, "FECHA_REFERENCIA", "auto")
    visto = []

    class Ses(SesionFalsa):
        def get(self, url, params=None, **k):
            visto.append(params)
            return super().get(url, params=params, **k)
    ses = Ses(RespuestaFalsa(200, [{"ultima": "2024-12-31T23:00:00.000"}]),
              RespuestaFalsa(200, [{"x": 1}]))
    obtener_registros(AHORA, sesion=ses, dormir=lambda s: None)
    assert "max(" in visto[0]["$select"]
    assert "2024-12-28T23:00:00" in visto[1]["$where"]        # 3 días antes de la referencia


def test_ciclo_marca_datos_historicos(aislar):
    viejos = demo.generar_registros(datetime(2024, 12, 31, 23))
    ses = SesionFalsa(RespuestaFalsa(200, viejos))
    assert ejecutar_ciclo(AHORA, sesion=ses, dormir=lambda s: None) is True
    datos = json.loads(config.SALIDA_JSON.read_text(encoding="utf-8"))
    assert datos["datos_historicos"] is True and "no en tiempo real" in datos["aviso"]
    assert datos["estaciones"]["tunal"]["desactualizado"] is True


def test_filtro_estaciones_en_la_consulta(monkeypatch):
    monkeypatch.setattr(config, "ESTACIONES", ["ciudad bolivar"])
    visto = []

    class Ses(SesionFalsa):
        def get(self, url, params=None, **k):
            visto.append(params)
            return super().get(url, params=params, **k)
    obtener_registros(AHORA, sesion=Ses(RespuestaFalsa(200, [])), dormir=lambda s: None)
    assert "CIUDAD BOLIVAR" in visto[0]["$where"]


def test_msfl_code_como_columna_de_contaminante():
    reg = {"nombre_est": "X", "msfl_code": "PM10", "med_concentracion_estandar": "20",
           "med_fecha_inicio": "2024-12-31T23:00:00.000"}
    assert normalizar_registro(reg).contaminante == "PM10"
    reg["msfl_code"] = "RGlobal"
    assert normalizar_registro(reg) is None


# ---------- paginación y filtro de contaminante ----------
def test_pagina_hasta_completar(monkeypatch):
    monkeypatch.setattr(config, "LIMITE_REGISTROS", 2)
    visto = []

    class Ses(SesionFalsa):
        def get(self, url, params=None, **k):
            visto.append(dict(params))
            return super().get(url, params=params, **k)
    ses = Ses(RespuestaFalsa(200, [{"a": 1}, {"a": 2}]), RespuestaFalsa(200, [{"a": 3}]))
    datos = obtener_registros(AHORA, sesion=ses, dormir=lambda s: None)
    assert len(datos) == 3
    assert [v["$offset"] for v in visto] == [0, 2]
    assert "msfl_code in('PM2.5','PM10')" in visto[0]["$where"]
