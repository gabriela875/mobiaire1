"""Pruebas de la PWA (Sprint 3): el servidor sirve manifest, SW e iconos.

No requieren red externa: arrancan el servidor en memoria y piden los recursos.
No tocan el motor ICA, la ingesta ni las APIs.
"""
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from web import server as srv


def _servidor():
    # Puerto efímero (0) para que las pruebas no colisionen entre sí.
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.2)
    return httpd


def _get(httpd, ruta):
    puerto = httpd.server_address[1]
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (puerto, ruta), timeout=5) as r:
            return r.status, r.read(), r.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None


def test_sirve_recursos_pwa():
    httpd = _servidor()
    try:
        # manifest
        c, cuerpo, tipo = _get(httpd, "/manifest.webmanifest")
        assert c == 200 and "manifest" in tipo
        man = json.loads(cuerpo.decode("utf-8"))
        assert man["name"] == "MobiAire Materno"
        assert man["display"] == "standalone"
        assert man["start_url"].startswith("/")
        assert any(i["sizes"] == "512x512" for i in man["icons"])
        assert any(i.get("purpose") == "maskable" for i in man["icons"])

        # service worker (en la raíz, para scope global)
        c, cuerpo, tipo = _get(httpd, "/service-worker.js")
        assert c == 200 and "javascript" in tipo
        txt = cuerpo.decode("utf-8")
        assert "/api/" in txt            # trata la API aparte
        assert "caches" in txt           # usa Cache API

        # iconos
        for ruta, firma in [("/iconos/icono-192.png", b"\x89PNG"),
                            ("/iconos/icono-512.png", b"\x89PNG"),
                            ("/iconos/icono.svg", b"<svg")]:
            c, cuerpo, tipo = _get(httpd, ruta)
            assert c == 200, ruta
            assert cuerpo[:4] == firma or cuerpo.lstrip()[:4] == firma, ruta

        # La raíz sirve el DISEÑO NUEVO (rediseño móvil) y enlaza el manifest + JS.
        c, cuerpo, tipo = _get(httpd, "/")
        html = cuerpo.decode("utf-8")
        assert c == 200 and "text/html" in tipo
        assert 'rel="manifest"' in html            # es instalable
        assert "/app-movil.js" in html              # carga el JS del rediseño móvil
        assert "MobiAire" in html and "Cuida tu embarazo" in html

        # El JS del rediseño usa los MISMOS endpoints (no se cambiaron).
        c, cuerpo, tipo = _get(httpd, "/app-movil.js")
        assert c == 200 and "javascript" in tipo
        js = cuerpo.decode("utf-8")
        assert "/api/waqi/estaciones?semaforo=1" in js
        assert "/api/zona/" in js
        # privacidad: sin USO real de almacenamiento (la palabra en un comentario no cuenta)
        assert "localStorage." not in js and "localStorage[" not in js
        assert "sessionStorage." not in js and "sessionStorage[" not in js

        # Textos editables del PO se sirven.
        c, cuerpo, _ = _get(httpd, "/recomendaciones.json")
        assert c == 200
        reco = json.loads(cuerpo.decode("utf-8"))
        assert "niveles" in reco and "guia" in reco
    finally:
        httpd.shutdown()


def test_api_sigue_igual_y_env_protegido():
    httpd = _servidor()
    try:
        # La API no se altera: estación histórica sigue dando ICA 67
        c, cuerpo, _ = _get(httpd, "/api/estacion/ciudad_bolivar")
        assert c == 200
        est = json.loads(cuerpo.decode("utf-8"))["estacion"]
        assert est["ica"] == 67
        # Seguridad intacta
        assert _get(httpd, "/.env")[0] == 404
    finally:
        httpd.shutdown()
