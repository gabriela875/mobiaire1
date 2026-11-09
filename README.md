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

## Interfaz web (Sprint 1 y 2)

Aplicación web visual y responsive (semáforo de calidad del aire) construida solo
con la **biblioteca estándar de Python** (`http.server`) + HTML + CSS + JavaScript.
No requiere Flask/FastAPI ni dependencias adicionales. El servidor **solo lee** los
resultados ya generados por el motor (`ingesta/resultados.json`): abrir o actualizar
la página **nunca** ejecuta la ingesta ni recalcula el ICA.

```bash
python -m web.server                 # abre en http://127.0.0.1:8000
python -m web.server --port 8080     # otro puerto
python -m web.server --demo-refrescar # regenera ingesta/resultados_demo.json (sin internet)
```

Pantallas: **Semáforo** (estación destacada con ICA, PM2.5/PM10, fechas y avisos),
**Estaciones** (lista y detalle) y **Zonas** (selector de las 8 UPZ de Ciudad Bolívar
con su descripción; la asociación zona↔estación queda **pendiente** hasta tener datos
geográficos verificables — no se inventan cercanías ni coordenadas).

Identidad visual propia (sin librerías ni imágenes externas): estética ambiental y de
salud con verdes naturales, fondo marfil y acento coral; logotipo SVG embebido. Los
estados se comunican con **color + icono + texto** (nunca solo color) y la interfaz es
responsive (en móvil prioriza ICA, mediciones y fecha de actualización).

El **modo demostración** (interruptor en la interfaz) usa `ingesta/resultados_demo.json`,
se rotula siempre como «DEMO — DATOS SIMULADOS» y nunca mezcla ni pisa los datos reales.
Los datos reales son **históricos** (dataset hasta dic-2024) y la interfaz lo advierte
de forma visible; no se presentan como la calidad del aire actual.

## Asociación zona ↔ estación (Sprint 2)

Cada UPZ de Ciudad Bolívar se asocia a la **estación de WAQI más cercana** con una
**regla única**: distancia haversine entre el **centroide de la UPZ** y las estaciones,
sin excepciones manuales por zona (`zonas/asociacion.py`).

- **Centroides de las UPZ:** salen de la capa oficial de UPZ de Datos Abiertos Bogotá
  (`datos/upz.geojson`); `scripts/generar_zonas.py` calcula el centroide ponderado por
  área y escribe `datos/upz_coords.json`. No se inventan coordenadas: si una UPZ no tiene
  centroide oficial, su asociación queda `pendiente`.
- **Estaciones candidatas:** las de Bogotá que WAQI reporta con dato reciente, más la
  estación de Ciudad Bolívar (`A522148`); sus coordenadas provienen de la respuesta de
  WAQI, no están escritas en el código.
- **Resultado:** la distancia se muestra como «X km al centro de la zona» y el semáforo de
  la zona usa el **ICA estimado (derivado de WAQI)**, nunca el índice WAQI tal cual.

### Límites
- Es una aproximación: la estación más cercana al centroide **no equivale** a la calidad
  del aire de toda la UPZ, que es heterogénea.
- La red de WAQI/OAB **no tiene una estación dentro de cada UPZ**; varias zonas comparten
  la misma estación cercana (p. ej. Mochuelo → Tunal ≈ 4,25 km; Jerusalén → Carvajal ≈ 3,83 km).
- El ICA de la zona es **estimado y horario** (derivado del sub-índice WAQI US-EPA), no el
  promedio de 24 h de la Resolución 2254. Si la estación no tiene dato reciente (< 6 h), la
  zona se muestra en gris «Sin dato reciente», sin número.
