"""Guarda el resultado: siempre en resultados.json, y en Firestore si hay clave."""
import json
import logging
import os

from ingesta import config

log = logging.getLogger("mobiaire.ingesta")


def guardar_json(resultado, ruta=None):
    """Escritura atómica: si algo falla a mitad, no queda un archivo corrupto."""
    ruta = ruta or config.SALIDA_JSON
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def guardar_firestore(resultado):
    """Sube un documento por estación a la colección `estaciones`.

    Solo se ejecuta si FIREBASE_CREDENCIALES apunta a la clave de servicio.
    (Requiere: pip install firebase-admin)
    """
    if not config.FIREBASE_CREDENCIALES:
        return False
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(config.FIREBASE_CREDENCIALES))
    db = firestore.client()
    lote = db.batch()
    for sid, estado in resultado["estaciones"].items():
        lote.set(db.collection(config.FIRESTORE_COLECCION).document(sid), estado)
    lote.commit()
    log.info("Firestore: %d estaciones actualizadas", len(resultado["estaciones"]))
    return True
