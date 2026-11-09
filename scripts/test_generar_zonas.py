from scripts.generar_zonas import calcular, centroide


def cuadro(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def test_centroide_cuadrado():
    lat, lon = centroide({"type": "Polygon", "coordinates": [cuadro(-74.2, 4.5, -74.0, 4.7)]})
    assert abs(lat - 4.6) < 1e-9 and abs(lon + 74.1) < 1e-9


def test_centroide_no_depende_de_la_densidad_de_vertices():
    denso = [[-74.2, 4.5], [-74.0, 4.5], [-74.0, 4.7]] + [[-74.0 - i * 0.0001, 4.7] for i in range(1, 2000, 100)] + [[-74.2, 4.7], [-74.2, 4.5]]
    lat, lon = centroide({"type": "Polygon", "coordinates": [denso]})
    assert abs(lat - 4.6) < 1e-3 and abs(lon + 74.1) < 1e-3


def test_centroide_resta_huecos():
    geo = {"type": "Polygon", "coordinates": [cuadro(0, 0, 4, 4), cuadro(2, 0, 4, 4)]}
    lat, lon = centroide(geo)
    assert abs(lon - 1.0) < 1e-9


def test_alias_codigo_y_repetidos():
    def f(nombre, cod, caja, loc="CUALQUIERA"):
        return {"properties": {"UPlNombre": nombre, "UPlCodigo": cod, "LocNombre": loc},
                "geometry": {"type": "MultiPolygon", "coordinates": [[cuadro(*caja)]]}}
    gj = {"features": [
        f("JERUSALEM", "UPZ70", (-74.2, 4.5, -74.0, 4.7), loc="BOSA"),   # LocNombre no se usa
        f("JERUSALEM", "UPZ70", (-74.2, 4.5, -74.0, 4.7)),                # copia idéntica
        f("EL MOCHUELO", "UPZ63", (-74.2, 4.4, -74.1, 4.5)),
        f("LUCERO", "UPZ99", (-73.0, 5.0, -72.9, 5.1)),                   # nombre igual, otra UPZ
    ]}
    zonas = [{"id": "jerusalen", "nombre": "Jerusalén"}, {"id": "mochuelo", "nombre": "Mochuelo"},
             {"id": "lucero", "nombre": "Lucero"}]
    coords, faltan, avisos = calcular(gj, zonas)
    assert set(coords) == {"jerusalen", "mochuelo"} and faltan == ["Lucero"] and avisos == []
    assert abs(coords["jerusalen"]["lat"] - 4.6) < 1e-6


def test_avisa_si_repetidas_difieren():
    def f(caja):
        return {"properties": {"UPlNombre": "LUCERO", "UPlCodigo": "UPZ67"},
                "geometry": {"type": "Polygon", "coordinates": [cuadro(*caja)]}}
    gj = {"features": [f((-74.2, 4.5, -74.0, 4.7)), f((-74.1, 4.4, -73.9, 4.6))]}
    coords, faltan, avisos = calcular(gj, [{"id": "lucero", "nombre": "Lucero"}])
    assert len(avisos) == 1 and abs(coords["lucero"]["lat"] - 4.6) < 1e-6
