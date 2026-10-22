# MobiAire — Sprint 1: ingesta y motor ICA

Calcula el ICA (PM2.5 y PM10, Res. 2254/2017) por estación y lo clasifica en
verde / naranja / rojo.

```
motor_ica/   ica.py (cálculo y semáforo) + test_ica.py
ingesta/     config.py · cliente_api.py · normalizador.py · calculo.py
             almacen.py · ingesta.py (ciclo) · explorar_api.py · demo.py
app/ docs/
```

## Puesta en marcha
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest                       # 54 pruebas deben pasar
python -m ingesta.ingesta --demo       # prueba completa SIN internet (datos sintéticos)
```

## Conectar la API real
```bash
python -m ingesta.explorar_api         # 1) revisa columnas, contaminantes y fecha más reciente
python -m ingesta.ingesta --una-vez    # 2) un ciclo real -> ingesta/resultados.json
python -m ingesta.ingesta              # 3) cada 15 minutos
```
Si `explorar_api` muestra `None` en algún campo, agregue el nombre real en `CAMPOS`
(`ingesta/config.py`). Variables opcionales en `.env.example`.

## Ver y validar resultados
```bash
python -m ingesta.resumen --html         # (con --demo muestra la demo) tabla en terminal + ingesta/resultados.html (abrir en el navegador)
python -m ingesta.validar "ciudad bolivar"   # cálculo paso a paso de una estación (tarea S1.3.2)
```
Configuración sin tocar código: copie `.env.example` a `.env` y edite (se carga solo).

## Firestore (opcional)
`pip install firebase-admin`, y defina `FIREBASE_CREDENCIALES` con la ruta de la clave
**fuera del repo**. Escribe un documento por estación en la colección `estaciones`.

## Importante: la fuente es histórica
El dataset `g4t8-zkc3` termina el 2024-12-31. Con `FECHA_REFERENCIA=auto` (defecto) la ingesta
calcula con esa fecha como referencia, marca `datos_historicos: true` y cada estación sale
`desactualizado`. Para un piloto en tiempo real hace falta otra fuente (ver docs/decisiones_tecnicas.md).
La demo escribe en `resultados_demo.json` y nunca mezcla con los datos reales.
