"""Configuración de la ingesta. Todo se puede cambiar con variables de entorno."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env():
    """Lee RAIZ/.env (CLAVE=valor) sin pisar variables ya definidas. Sin dependencias."""
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.split(" #")[0].strip().strip('"').strip("'"))


_cargar_env()

# --- Fuente de datos --------------------------------------------------------
# Dataset "Calidad del Aire en Colombia" (IDEAM / SISAIRE) en datos.gov.co
API_URL = os.getenv("API_URL", "https://www.datos.gov.co/resource/g4t8-zkc3.json")
API_APP_TOKEN = os.getenv("API_APP_TOKEN", "")   # opcional (Socrata): más cuota
FUENTE_LOCAL = os.getenv("FUENTE_LOCAL", "")     # ruta a un JSON (demo/pruebas)
CAMPO_FECHA_SOQL = "med_fecha_inicio"            # campo usado para filtrar/ordenar
FILTRO_SOQL = os.getenv("FILTRO_SOQL", "")       # ej: departamento='BOGOTÁ'
DIAS_ATRAS = int(os.getenv("DIAS_ATRAS", "3"))   # cuánto histórico pedir
# Fecha desde la cual se cuenta DIAS_ATRAS:
#   "auto" (defecto) = el dato más reciente que tenga la fuente (sirve si la fuente es
#   histórica, como este dataset, que termina en dic-2024). Vacío = la fecha de hoy.
#   O una fecha fija, ej: 2024-12-31T23:00:00
FECHA_REFERENCIA = os.getenv("FECHA_REFERENCIA", "auto")
LIMITE_REGISTROS = int(os.getenv("LIMITE_REGISTROS", "50000"))   # por página
MAX_PAGINAS = int(os.getenv("MAX_PAGINAS", "10"))
# Solo material particulado (códigos confirmados con explorar_api). Vacío = sin filtro.
FILTRO_VARIABLE_SOQL = os.getenv("FILTRO_VARIABLE_SOQL", "msfl_code in('PM2.5','PM10')")

# Si no está vacío, solo se procesan estaciones cuyo nombre contenga alguno
# de estos textos (ej: "ciudad bolivar,tunal"). Vacío = todas.
ESTACIONES = [e.strip().lower() for e in os.getenv("ESTACIONES", "").split(",") if e.strip()]

# --- Ejecución --------------------------------------------------------------
INTERVALO_MIN = int(os.getenv("INTERVALO_MIN", "15"))
REINTENTOS = int(os.getenv("REINTENTOS", "3"))
ESPERA_BASE_S = float(os.getenv("ESPERA_BASE_S", "2"))   # 2s, 4s, 8s...
TIMEOUT_S = 30

# --- Reglas del cálculo -----------------------------------------------------
MIN_DATOS_24H = int(os.getenv("MIN_DATOS_24H", "18"))    # 75% de 24 datos horarios
MAX_ANTIGUEDAD_H = int(os.getenv("MAX_ANTIGUEDAD_H", "6"))  # más viejo = "desactualizado"

# --- Salidas ----------------------------------------------------------------
SALIDA_JSON = Path(os.getenv("SALIDA_JSON", RAIZ / "ingesta" / "resultados.json"))
SALIDA_DEMO = RAIZ / "ingesta" / "resultados_demo.json"   # la demo nunca pisa los datos reales
LOG_ARCHIVO = Path(os.getenv("LOG_ARCHIVO", RAIZ / "ingesta" / "ingesta.log"))
FIREBASE_CREDENCIALES = os.getenv("FIREBASE_CREDENCIALES", "")  # ruta al JSON de la clave
FIRESTORE_COLECCION = os.getenv("FIRESTORE_COLECCION", "estaciones")

# --- Nombres de campos de la API -------------------------------------------
# Lista de candidatos por campo: se usa el primero que exista en la respuesta.
# Si la API cambia un nombre, agréguelo aquí. NO se toca el resto del código.
# Los 8 primeros nombres están confirmados en el diccionario de datos del dataset;
# el de la variable/contaminante se detecta por candidatos (ver explorar_api.py).
CAMPOS = {
    "estacion":   ["nombre_est", "nombreestacion", "estacion"],
    "autoridad":  ["nombre_fgda", "autoridad_ambiental"],
    "valor":      ["med_concentracion_estandar", "concentracion", "valor"],
    "inicio":     ["med_fecha_inicio", "fecha_inicio", "fecha"],
    "fin":        ["med_fecha_final", "fecha_final"],
    "duracion":   ["duraci_n", "duracion"],
    "unidad":     ["sigla_unidad", "nombre_unidad"],
    "latitud":    ["latitud"],
    "longitud":   ["longitud"],
    "municipio":  ["municipio", "nombre_municipio", "ciudad"],
    "departamento": ["departamento"],
    # En este dataset el contaminante/variable viene en msfl_code (ej. "RGlobal" = radiación)
    "variable":   ["msfl_code", "variable", "nombre_variable", "sigla_variable", "contaminante", "parametro"],
}
# Si ningún candidato exacto existe, se busca una columna cuyo nombre CONTENGA esto:
SUBCADENAS_VARIABLE = ("msfl", "variable", "contamin", "param")
