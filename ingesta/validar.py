"""Muestra, paso a paso, cómo se calculó el ICA de UNA estación.

Sirve para la tarea S1.3.2 (verificar con datos reales): comparen este cálculo
a mano con el ICA que publica la autoridad ambiental para esa estación.

    python -m ingesta.validar "ciudad bolivar"
    python -m ingesta.validar "ciudad bolivar" --demo
"""
import argparse
from datetime import datetime, timedelta

from ingesta import config
from ingesta.calculo import promedio_24h, sin_tildes
from ingesta.cliente_api import obtener_registros
from ingesta.normalizador import FormatoInvalido, normalizar_registro
from motor_ica.ica import TRAMOS, calcular_ica, calcular_ica_contaminante


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("estacion", help="texto contenido en el nombre de la estación")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        from ingesta import demo
        config.FUENTE_LOCAL = str(demo.generar())
        config.FECHA_REFERENCIA = ""

    ahora = datetime.now()
    if not config.FUENTE_LOCAL and not config.ESTACIONES:
        config.ESTACIONES = [args.estacion.lower()]   # pide solo esa estación a la API
    meds = []
    for r in obtener_registros(ahora=ahora):
        try:
            m = normalizar_registro(r)
        except FormatoInvalido:
            continue
        if m and sin_tildes(args.estacion) in sin_tildes(m.estacion):
            meds.append(m)
    if not meds:
        raise SystemExit(f"Sin datos PM2.5/PM10 para '{args.estacion}'. Revise el nombre con explorar_api.")

    print(f"Estación: {meds[0].estacion}  ({meds[0].autoridad})\n")
    prom = {}
    for cont in ("PM25", "PM10"):
        serie = [m for m in meds if m.contaminante == cont]
        if not serie:
            continue
        valor, n, ultimo = promedio_24h(serie)
        ventana = sorted((m for m in serie if m.fin > ultimo - timedelta(hours=24)), key=lambda m: m.fin)
        print(f"{cont}: {n} datos en las 24 h hasta {ultimo}")
        print("   valores:", ", ".join(f"{m.valor:g}" for m in ventana[-24:]))
        if valor is None:
            print(f"   -> insuficiente (mínimo {config.MIN_DATOS_24H})\n")
            continue
        ica = calcular_ica_contaminante(cont, valor)
        tramo = next(t for t in TRAMOS[cont] if t[2] <= int(valor + 0.5) <= t[3])
        print(f"   promedio 24 h = {valor:.2f} µg/m³ -> redondeo {int(valor + 0.5)}")
        print(f"   tramo ICA {tramo[0]}-{tramo[1]} / conc {tramo[2]}-{tramo[3]}  =>  ICA {cont} = {ica}\n")
        prom[cont] = valor
    r = calcular_ica(pm25=prom.get("PM25"), pm10=prom.get("PM10"))
    if r:
        print(f"RESULTADO: ICA {r['ica']} = {r['nivel'].upper()} "
              f"(categoría oficial: {r['categoria']}, dominante {r['contaminante_dominante']})")


if __name__ == "__main__":
    main()
