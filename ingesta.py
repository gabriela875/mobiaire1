"""Ciclo de ingesta: API -> normalizar -> ICA por estación -> guardar.

Uso (desde la raíz del repo):
    python -m ingesta.ingesta --una-vez     # un ciclo y termina
    python -m ingesta.ingesta               # cada 15 minutos (Ctrl+C para parar)
    python -m ingesta.ingesta --demo        # con datos sintéticos, sin internet
"""
import argparse
import logging
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from ingesta import almacen, config
from ingesta.calculo import calcular_estaciones
from ingesta.cliente_api import ErrorFuente, obtener_registros
from ingesta.normalizador import FormatoInvalido, normalizar_registro

log = logging.getLogger("mobiaire.ingesta")


def configurar_logs():
    """Logs técnicos a consola y archivo rotativo. Sin datos personales."""
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in (logging.StreamHandler(),
              RotatingFileHandler(config.LOG_ARCHIVO, maxBytes=1_000_000, backupCount=3,
                                  encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)


def ejecutar_ciclo(ahora=None, **kwargs):
    """Un ciclo completo. Nunca lanza excepciones: devuelve True si salió bien."""
    ahora = ahora or datetime.now()
    inicio = time.time()
    try:
        crudos = obtener_registros(ahora=ahora, **kwargs)
    except ErrorFuente as e:
        log.error("Ciclo fallido: %s. Se conserva el último resultado válido.", e)
        return False

    mediciones, invalidos, motivos = [], 0, {}
    for reg in crudos:
        try:
            m = normalizar_registro(reg)
        except FormatoInvalido as e:
            invalidos += 1
            motivos[str(e)] = motivos.get(str(e), 0) + 1
            continue
        if m is not None:
            mediciones.append(m)

    if invalidos:
        log.warning("%d de %d registros con formato inesperado: %s",
                    invalidos, len(crudos), motivos)
    if crudos and not mediciones and invalidos == len(crudos):
        claves = sorted(crudos[0].keys()) if isinstance(crudos[0], dict) else "?"
        log.error("POSIBLE CAMBIO DE FORMATO: ningún registro válido. Campos recibidos: %s. "
                  "Revise CAMPOS en config.py. Se conserva el último resultado.", claves)
        return False
    if not mediciones:
        log.warning("La API respondió %d registros pero ninguno de PM2.5/PM10 en la ventana "
                    "pedida (DIAS_ATRAS=%d, FECHA_REFERENCIA=%r). Ejecute explorar_api para ver "
                    "la fecha más reciente y los códigos msfl_code.",
                    len(crudos), config.DIAS_ATRAS, config.FECHA_REFERENCIA)
        return False

    estaciones = calcular_estaciones(mediciones, ahora)
    if not estaciones:
        log.warning("Hay mediciones pero ninguna estación pasa el filtro ESTACIONES=%s", config.ESTACIONES)
        return False

    mas_reciente = max(m.fin for m in mediciones)
    historicos = (ahora - mas_reciente).days > 7
    resultado = {
        "generado_en": ahora.isoformat(timespec="seconds"),
        "datos_historicos": historicos,
        "aviso": (f"Fuente no en tiempo real: dato más reciente {mas_reciente.isoformat()}"
                  if historicos else ""),
        "fuente": config.FUENTE_LOCAL or config.API_URL,
        "estaciones": estaciones,
    }
    almacen.guardar_json(resultado)
    try:
        almacen.guardar_firestore(resultado)
    except Exception as e:           # Firestore caído no debe tumbar la ingesta
        log.error("No se pudo escribir en Firestore: %s", e)

    ok = sum(1 for e in estaciones.values() if e["estado"] == "ok")
    log.info("Ciclo OK en %.1fs: %d registros, %d estaciones (%d con ICA)",
             time.time() - inicio, len(crudos), len(estaciones), ok)
    for sid, e in estaciones.items():
        log.info("  %-28s %s", sid, f"ICA {e['ica']} {e['nivel']}" if e["estado"] == "ok"
                 else e["estado"])
    return True


def main():
    ap = argparse.ArgumentParser(description="Ingesta de calidad del aire MobiAire")
    ap.add_argument("--una-vez", action="store_true", help="ejecuta un ciclo y termina")
    ap.add_argument("--demo", action="store_true", help="usa datos sintéticos (sin internet)")
    args = ap.parse_args()

    configurar_logs()
    if args.demo:
        from ingesta import demo
        config.FUENTE_LOCAL = str(demo.generar())
        config.SALIDA_JSON = config.SALIDA_DEMO
        log.info("Modo DEMO: datos sintéticos en %s", config.FUENTE_LOCAL)

    if args.una_vez or args.demo:
        raise SystemExit(0 if ejecutar_ciclo() else 1)

    log.info("Ingesta iniciada: cada %d min. Ctrl+C para detener.", config.INTERVALO_MIN)
    try:
        while True:
            ejecutar_ciclo()
            time.sleep(config.INTERVALO_MIN * 60)
    except KeyboardInterrupt:
        log.info("Ingesta detenida.")


if __name__ == "__main__":
    main()
