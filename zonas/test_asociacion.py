"""Pruebas de la asociación UPZ -> estación WAQI más cercana (haversine).

Usa coordenadas SINTÉTICAS dentro del test (no reales), para no depender de red
ni de datos oficiales. Verifica: cercanía, zona pendiente sin coordenadas y que
la función no guarda ni la zona ni ninguna ubicación.
"""
from zonas import asociacion


# Estaciones sintéticas (coords de prueba, no reales)
ESTACIONES = [
    {"uid": "A1", "nombre": "Estación Norte", "lat": 4.70, "lon": -74.05},
    {"uid": "A2", "nombre": "Estación Sur", "lat": 4.52, "lon": -74.15},
]


def test_haversine_conocido():
    # ~1.11 km por 0.01° de latitud en el ecuador aproximado
    d = asociacion.haversine_km(4.60, -74.10, 4.61, -74.10)
    assert 1.0 < d < 1.25


def test_estacion_mas_cercana_elige_la_correcta():
    est, dist = asociacion.estacion_mas_cercana(4.53, -74.14, ESTACIONES)
    assert est["uid"] == "A2"            # el punto está al sur
    assert dist is not None and dist >= 0


def test_estacion_mas_cercana_sin_estaciones():
    est, dist = asociacion.estacion_mas_cercana(4.5, -74.1, [])
    assert est is None and dist is None


def test_asociar_zona_pendiente_sin_coords():
    # Sin coords oficiales de UPZ -> todas las zonas quedan "pendiente" (no inventa)
    r = asociacion.asociar(ESTACIONES, coords_upz={})
    assert r["estado_global"] == "pendiente"
    assert all(z["estado"] == "pendiente" for z in r["zonas"])
    assert all(z["estacion"] is None for z in r["zonas"])


def test_asociar_con_coords_sinteticas_calcula_cercania():
    # Coords sintéticas para dos UPZ reales del archivo zonas.json
    coords = {
        "lucero": {"lat": 4.53, "lon": -74.15},      # cerca de Estación Sur
        "ismael_perdomo": {"lat": 4.69, "lon": -74.06},  # cerca de Estación Norte
    }
    r = asociacion.asociar(ESTACIONES, coords_upz=coords)
    porid = {z["id"]: z for z in r["zonas"]}
    assert porid["lucero"]["estado"] == "ok"
    assert porid["lucero"]["estacion"]["uid"] == "A2"
    assert porid["ismael_perdomo"]["estacion"]["uid"] == "A1"
    # Las UPZ sin coords siguen pendientes
    assert porid["mochuelo"]["estado"] == "pendiente"


def test_asociar_no_persiste_estado():
    # Dos llamadas independientes no comparten estado (función pura).
    r1 = asociacion.asociar(ESTACIONES, coords_upz={"lucero": {"lat": 4.53, "lon": -74.15}})
    r2 = asociacion.asociar(ESTACIONES, coords_upz={})
    assert r1 is not r2
    assert any(z["estado"] == "ok" for z in r1["zonas"])
    assert all(z["estado"] == "pendiente" for z in r2["zonas"])
