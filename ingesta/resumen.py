"""Muestra resultados.json de forma legible.

    python -m ingesta.resumen          # tabla en la terminal
    python -m ingesta.resumen --html   # además genera ingesta/resultados.html
"""
import argparse
import html
import json
import os
import sys

from ingesta import config

ANSI = {"verde": "\033[42;30m", "naranja": "\033[43;30m", "rojo": "\033[41;37m"}
HEX = {"verde": "#2e9e4f", "naranja": "#f08c00", "rojo": "#d6292b", None: "#888"}


def cargar():
    if not config.SALIDA_JSON.exists():
        sys.exit(f"No existe {config.SALIDA_JSON}. Ejecute primero: python -m ingesta.ingesta --una-vez")
    return json.loads(config.SALIDA_JSON.read_text(encoding="utf-8"))


def tabla(datos, color=True):
    filas = sorted(datos["estaciones"].values(), key=lambda e: -(e.get("ica") or -1))
    out = [f"Generado: {datos['generado_en']}   Fuente: {datos['fuente']}"]
    if "datos_demo" in str(datos["fuente"]):
        out.append("*** DATOS DE DEMOSTRACIÓN (sintéticos), no son mediciones reales ***")
    if datos.get("aviso"):
        out.append(f"*** {datos['aviso']} ***")
    out.append("")
    out.append(f"{'ESTACIÓN':28}{'ICA':>5}  {'NIVEL':9}{'PM2.5':>7}{'PM10':>7}  {'DOMINANTE':10}ÚLTIMA MEDICIÓN")
    for e in filas:
        if e["estado"] == "ok":
            nivel = e["nivel"].upper().ljust(9)
            if color and sys.stdout.isatty():
                nivel = f"{ANSI[e['nivel']]} {nivel[:-1]}\033[0m"
            aviso = "  (!) desactualizado" if e["desactualizado"] else ""
            out.append(f"{e['estacion'][:27]:28}{e['ica']:>5}  {nivel}{str(e['pm25_24h']):>7}"
                       f"{str(e['pm10_24h']):>7}  {e['contaminante_dominante']:10}{e['ultima_medicion']}{aviso}")
        else:
            out.append(f"{e['estacion'][:27]:28}{'-':>5}  {'SIN ICA':9}  (datos insuficientes: "
                       f"PM2.5={e['datos_pm25']} PM10={e['datos_pm10']} datos, mínimo {config.MIN_DATOS_24H})")
    return "\n".join(out)


def pagina_html(datos):
    tarjetas = []
    for e in sorted(datos["estaciones"].values(), key=lambda e: -(e.get("ica") or -1)):
        c = HEX[e.get("nivel")]
        ica = e.get("ica", "—")
        nota = "(!) dato desactualizado" if e["desactualizado"] else f"Última medición: {e['ultima_medicion']}"
        tarjetas.append(
            f'<div class="t" style="border-left:10px solid {c}"><h2>{html.escape(e["estacion"])}</h2>'
            f'<div class="n" style="color:{c}">{ica}</div><b>{html.escape(e.get("nivel", "sin datos").upper())}</b>'
            f'<p>PM2.5 {e["pm25_24h"]} · PM10 {e["pm10_24h"]} µg/m³ (24 h)</p><small>{nota}</small></div>')
    return ("<!doctype html><meta charset='utf-8'><title>MobiAire</title><style>"
            "body{font-family:system-ui;margin:24px;background:#f5f5f5}.g{display:grid;gap:14px;"
            "grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}.t{background:#fff;padding:14px;"
            "border-radius:8px}.n{font-size:48px;font-weight:700}h2{margin:0;font-size:16px}</style>"
            f"<h1>MobiAire — Calidad del aire</h1><p>Sincronizado: {datos['generado_en']}</p>"
            f"<p style='color:#b00'><b>{html.escape(datos.get('aviso', ''))}</b></p>"
            f"<div class='g'>{''.join(tarjetas)}</div>")


def main():
    os.system("")                                   # activa colores ANSI en la consola de Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--demo", action="store_true", help="muestra el resultado de la demo")
    args = ap.parse_args()
    if args.demo:
        config.SALIDA_JSON = config.SALIDA_DEMO
    datos = cargar()
    print(tabla(datos))
    if args.html:
        destino = config.SALIDA_JSON.with_suffix(".html")
        destino.write_text(pagina_html(datos), encoding="utf-8")
        print(f"\nPágina generada: {destino}")


if __name__ == "__main__":
    main()
