"""Servidor web de MobiAire Materno — SOLO LECTURA.

Sirve la interfaz (HTML/CSS/JS) y expone los resultados YA generados por el
motor de ingesta. NO ejecuta la ingesta ni recalcula el ICA: solo lee los
archivos JSON que el motor dejó en disco.

Usa únicamente la biblioteca estándar de Python (http.server). No requiere
instalar Flask, FastAPI, requests ni ninguna otra dependencia.

Uso:
    python -m web.server                 # http://localhost:8000
    python -m web.server --port 8080
    python -m web.server --demo-refrescar # regenera resultados_demo.json (sin red)

Endpoints (solo GET, solo lectura):
    GET /                      -> interfaz web (index.html)
    GET /api/estaciones        -> resultados reales (resultados.json)
    GET /api/estaciones?demo=1 -> resultados demo (resultados_demo.json)
    GET /api/estacion/<id>     -> una estación (admite ?demo=1)
    GET /api/zonas             -> zonas de Ciudad Bolívar (Sprint 2)
    GET /api/salud             -> estado del servidor y de los archivos de datos

Privacidad: nunca sirve .env, claves de Firebase ni archivos fuera de web/.
No guarda ninguna información de quien consulta.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent          # .../mobiaire1/web
RAIZ = AQUI.parent                               # .../mobiaire1
DIR_DATOS = RAIZ / "ingesta"
ARCHIVO_REAL = DIR_DATOS / "resultados.json"
ARCHIVO_DEMO = DIR_DATOS / "resultados_demo.json"
ARCHIVO_ZONAS = AQUI / "zonas.json"

# Solo estos archivos estáticos se pueden servir (lista blanca por seguridad).
ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/estilos.css": ("estilos.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    # Prototipo visual estático (DEMO). Autocontenido; solo para revisión de diseño.
    "/prototipo": ("prototipo/index.html", "text/html; charset=utf-8"),
    "/prototipo/": ("prototipo/index.html", "text/html; charset=utf-8"),
    "/prototipo/index.html": ("prototipo/index.html", "text/html; charset=utf-8"),
}


def _leer_json(ruta):
    """Lee un JSON de disco. Devuelve (datos, None) o (None, mensaje_error)."""
    if not ruta.exists():
        return None, f"No existe {ruta.name}. Ejecute la ingesta primero."
    try:
        return json.loads(ruta.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, OSError) as e:
        return None, f"No se pudo leer {ruta.name}: {e}"


class Handler(BaseHTTPRequestHandler):
    server_version = "MobiAire/1.0"

    # --- utilidades de respuesta ------------------------------------------
    def _json(self, cuerpo, codigo=200):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")   # siempre el dato más reciente del disco
        self.end_headers()
        self.wfile.write(datos)

    def _archivo(self, nombre, tipo):
        ruta = AQUI / nombre
        if not ruta.exists():
            return self._json({"error": f"Falta {nombre}"}, 404)
        datos = ruta.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _error(self, mensaje, codigo=404):
        self._json({"error": mensaje}, codigo)

    # --- ruteo ------------------------------------------------------------
    def do_GET(self):
        ruta = urlparse(self.path)
        camino = ruta.path
        params = parse_qs(ruta.query)
        es_demo = params.get("demo", ["0"])[0] in ("1", "true", "si", "sí")

        if camino in ESTATICOS:
            nombre, tipo = ESTATICOS[camino]
            return self._archivo(nombre, tipo)

        if camino == "/api/salud":
            return self._salud()

        if camino == "/api/estaciones":
            return self._estaciones(es_demo)

        if camino.startswith("/api/estacion/"):
            sid = camino[len("/api/estacion/"):].strip("/")
            return self._estacion(sid, es_demo)

        if camino == "/api/zonas":
            return self._zonas()

        # --- WAQI (datos recientes; token solo en el backend) ------------
        if camino == "/api/waqi/estaciones":
            con_semaforo = params.get("semaforo", ["0"])[0] in ("1", "true", "si", "sí")
            return self._waqi_estaciones(con_semaforo)

        if camino == "/api/waqi/ciudad-bolivar":
            return self._waqi_ciudad_bolivar()

        if camino.startswith("/api/waqi/estacion/"):
            uid = camino[len("/api/waqi/estacion/"):].strip("/")
            return self._waqi_estacion(uid)

        # --- Zonas (Sprint 2): asociación UPZ -> estación más cercana -----
        if camino == "/api/zonas/asociacion":
            return self._zonas_asociacion()

        if camino.startswith("/api/zona/"):
            zid = camino[len("/api/zona/"):].strip("/")
            return self._zona_semaforo(zid)

        return self._error("Ruta no encontrada", 404)

    # bloquear cualquier método que no sea GET (solo lectura)
    def do_POST(self): self._error("Solo lectura (GET)", 405)
    def do_PUT(self): self._error("Solo lectura (GET)", 405)
    def do_DELETE(self): self._error("Solo lectura (GET)", 405)

    # --- handlers de datos ------------------------------------------------
    def _cargar(self, es_demo):
        ruta = ARCHIVO_DEMO if es_demo else ARCHIVO_REAL
        datos, err = _leer_json(ruta)
        if err:
            return None, err
        # Marca de modo para que el frontend nunca confunda demo con real.
        datos = dict(datos)
        datos["modo"] = "demo" if es_demo else "real"
        datos["consultado_en"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        return datos, None

    def _estaciones(self, es_demo):
        datos, err = self._cargar(es_demo)
        if err:
            return self._error(err, 503)
        return self._json(datos)

    def _estacion(self, sid, es_demo):
        datos, err = self._cargar(es_demo)
        if err:
            return self._error(err, 503)
        est = datos.get("estaciones", {}).get(sid)
        if est is None:
            return self._error(f"Estación '{sid}' no encontrada", 404)
        return self._json({
            "modo": datos["modo"],
            "generado_en": datos.get("generado_en"),
            "datos_historicos": datos.get("datos_historicos", False),
            "aviso": datos.get("aviso", ""),
            "fuente": datos.get("fuente", ""),
            "consultado_en": datos["consultado_en"],
            "id": sid,
            "estacion": est,
        })

    def _zonas(self):
        datos, err = _leer_json(ARCHIVO_ZONAS)
        if err:
            return self._error(err, 503)
        return self._json(datos)

    # --- WAQI (proxy de solo lectura; el token NUNCA sale del backend) ----
    def _waqi_estaciones(self, con_semaforo=False):
        from web import waqi
        if not waqi.hay_token():
            return self._error("WAQI no configurado: falta WAQI_TOKEN en .env del backend.", 503)
        try:
            if con_semaforo:
                return self._json(waqi.estaciones_con_semaforo())
            return self._json(waqi.estaciones_bogota())
        except waqi.ErrorWAQI as e:
            return self._error(str(e), 502)

    def _waqi_estacion(self, uid):
        from web import waqi
        if not waqi.hay_token():
            return self._error("WAQI no configurado: falta WAQI_TOKEN en .env del backend.", 503)
        # WAQI: IDs internos (6235, @6235), externos (A522148) o idx negativo (-522148).
        if not re.fullmatch(r"@?\d+|A\d+|-\d+", uid):
            return self._error("uid de estación inválido.", 400)
        try:
            return self._json(waqi.estacion(uid))
        except waqi.ErrorWAQI as e:
            return self._error(str(e), 502)

    def _waqi_ciudad_bolivar(self):
        from web import waqi
        if not waqi.hay_token():
            return self._error("WAQI no configurado: falta WAQI_TOKEN en .env del backend.", 503)
        try:
            return self._json(waqi.ciudad_bolivar())
        except waqi.ErrorWAQI as e:
            return self._error(str(e), 502)

    # --- Zonas (Sprint 2) --------------------------------------------------
    @staticmethod
    def _estaciones_candidatas(waqi):
        """Estaciones recientes del bounds + Ciudad Bolívar (A522148), coords de WAQI."""
        from zonas import asociacion
        estaciones = [e for e in waqi.estaciones_bogota().get("estaciones", [])
                      if e.get("reciente")]
        # Agregar Ciudad Bolívar como candidata; sus coords salen de WAQI, no del código.
        try:
            cb = waqi.ciudad_bolivar().get("estacion")
        except waqi.ErrorWAQI:
            cb = None
        return asociacion.agregar_ciudad_bolivar(estaciones, cb)

    def _zonas_asociacion(self):
        """Tabla UPZ -> estación WAQI más cercana (haversine). Sin token -> pendiente."""
        from zonas import asociacion
        from web import waqi
        estaciones = []
        if waqi.hay_token():
            try:
                estaciones = self._estaciones_candidatas(waqi)
            except waqi.ErrorWAQI:
                estaciones = []
        return self._json(asociacion.asociar(estaciones))

    def _zona_semaforo(self, zid):
        """Semáforo de una zona: su estación asociada + ICA estimado (derivado WAQI)."""
        from zonas import asociacion
        from web import waqi
        if not waqi.hay_token():
            return self._error("WAQI no configurado: falta WAQI_TOKEN en .env del backend.", 503)
        try:
            estaciones = self._estaciones_candidatas(waqi)
        except waqi.ErrorWAQI as e:
            return self._error(str(e), 502)
        tabla = asociacion.asociar(estaciones)
        zona = next((z for z in tabla["zonas"] if z["id"] == zid), None)
        if zona is None:
            return self._error(f"Zona '{zid}' no encontrada", 404)
        if zona["estado"] != "ok" or not zona.get("estacion"):
            # Zona pendiente (sin coords oficiales) o sin estación: estado honesto
            return self._json({"zona": zona, "estado": zona["estado"],
                               "semaforo": None, "consultado_en": tabla.get("consultado_en")})
        uid = zona["estacion"]["uid"]
        try:
            det = waqi.estacion(uid)
        except waqi.ErrorWAQI:
            # Una estación que falla no debe tumbar la zona: estado honesto, no 502.
            return self._json({
                "zona": {"id": zona["id"], "nombre": zona["nombre"],
                         "distancia_km": zona["distancia_km"]},
                "estado": "sin_dato_reciente",
                "estacion": {"uid": uid, "nombre": zona["estacion"].get("nombre"),
                             "medido_bogota": None, "reciente": False},
                "semaforo": None, "indice_waqi": None,
                "consultado_en": tabla.get("consultado_en"),
            })
        est = det.get("estacion", {})
        return self._json({
            "zona": {"id": zona["id"], "nombre": zona["nombre"], "distancia_km": zona["distancia_km"]},
            "estado": "ok" if est.get("reciente") else "sin_dato_reciente",
            "estacion": {"uid": est.get("uid"), "nombre": est.get("nombre"),
                         "medido_bogota": est.get("medido_bogota"),
                         "medido_texto": est.get("medido_texto"),
                         "reciente": est.get("reciente")},
            # ICA estimado del proyecto (Res. 2254) derivado de WAQI; None si no reciente
            "semaforo": est.get("ica_estimado"),
            "indice_waqi": est.get("aqi_waqi"),
            "atribucion": det.get("atribucion", []),
            "consultado_en": det.get("consultado_en"),
        })

    def _salud(self):
        return self._json({
            "ok": True,
            "modo_red": "sin red (solo lectura de archivos)",
            "datos_reales": {
                "existe": ARCHIVO_REAL.exists(),
                "ruta": str(ARCHIVO_REAL.relative_to(RAIZ)),
            },
            "datos_demo": {
                "existe": ARCHIVO_DEMO.exists(),
                "ruta": str(ARCHIVO_DEMO.relative_to(RAIZ)),
            },
            "waqi": {
                # Solo informa SI hay token configurado; nunca su valor.
                "configurado": self._waqi_configurado(),
            },
            "consultado_en": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        })

    @staticmethod
    def _waqi_configurado():
        try:
            from web import waqi
            return waqi.hay_token()
        except Exception:
            return False

    # logs sobrios (sin datos personales)
    def log_message(self, formato, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), formato % args))


def regenerar_demo():
    """Regenera ingesta/resultados_demo.json con el motor existente (sin red).

    NO toca resultados.json. Reutiliza demo + normalizador + calculo + ica.
    """
    sys.path.insert(0, str(RAIZ))
    from ingesta import demo, almacen, config
    from ingesta.normalizador import normalizar_registro
    from ingesta.calculo import calcular_estaciones

    config.ESTACIONES = []   # la demo muestra los 3 niveles, sin el filtro del .env
    ahora = datetime.now()
    mediciones = [m for m in (normalizar_registro(r) for r in demo.generar_registros(ahora)) if m]
    estaciones = calcular_estaciones(mediciones, ahora)
    resultado = {
        "generado_en": ahora.isoformat(timespec="seconds"),
        "datos_historicos": False,
        "aviso": "DEMO - DATOS SIMULADOS (no son mediciones reales)",
        "fuente": "datos_demo (sintéticos)",
        "estaciones": estaciones,
    }
    almacen.guardar_json(resultado, config.SALIDA_DEMO)
    print(f"Demo regenerada en {config.SALIDA_DEMO} ({len(estaciones)} estaciones).")


def main():
    ap = argparse.ArgumentParser(description="Servidor web de MobiAire Materno (solo lectura)")
    ap.add_argument("--port", type=int, default=8000, help="puerto (defecto 8000)")
    ap.add_argument("--host", default="127.0.0.1", help="host (defecto 127.0.0.1)")
    ap.add_argument("--demo-refrescar", action="store_true",
                    help="regenera resultados_demo.json y termina")
    args = ap.parse_args()

    if args.demo_refrescar:
        regenerar_demo()
        return

    servidor = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"MobiAire Materno en http://{args.host}:{args.port}")
    print("Solo lectura. Ctrl+C para detener.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        servidor.server_close()


if __name__ == "__main__":
    main()
