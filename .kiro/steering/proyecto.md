---
inclusion: always
---
# MobiAire Materno · contexto del proyecto

Semáforo informativo de calidad del aire (PM2.5 y PM10) para gestantes de Ciudad Bolívar, Bogotá. Trabajo académico de Análisis de Sistemas (Universidad Distrital). No es un diagnóstico médico.

## Fuente de datos y cálculo (decisión del equipo)
- Fuente principal en tiempo real: WAQI (datos del Observatorio Ambiental de Bogotá, ya convertidos a escala AQI de EE. UU.).
- El equipo convierte los sub-índices WAQI de PM2.5 y PM10 a concentraciones (interpolación inversa con los cortes de la EPA) y calcula con su motor el ICA de la Resolución 2254 de 2017. Resultado: "ICA estimado (derivado de WAQI)". Es una aproximación y se documenta: depende de la versión de la tabla EPA que use WAQI y es un dato horario, no el promedio de 24 h que pide la norma.
- El índice WAQI original nunca se muestra como si fuera el ICA; si se muestra, se rotula "Índice WAQI (escala US-EPA)".
- IDEAM/SISAIRE (dataset g4t8-zkc3) es HISTÓRICO (hasta 31/12/2024): sirve para validar el motor con datos reales y como referencia histórica. Se muestra aparte y rotulado, y nunca alimenta el semáforo ni las alertas.
- Un dato es reciente si tiene menos de 6 horas. Sin dato reciente no hay semáforo vigente, ni recomendación, ni alerta.

## Estado actual
- Sprints 0 y 1 hechos: ingesta IDEAM cada 15 min con reintentos, motor ICA (Res. 2254) en motor_ica/ y 55 pruebas pytest.
- Interfaz web de solo lectura (web/): semáforo, estaciones, zonas, mapa WAQI y modo demo. web/zonas.json lista las UPZ; la asociación zona-estación está PENDIENTE por falta de datos geográficos oficiales verificables.

## Niveles del semáforo
verde ICA 0-100 · naranja 101-150 · rojo 151-500 (agrupan las 6 categorías oficiales).

## Reglas que no se negocian
1. No inventar coordenadas, distancias, tablas, datos de estaciones ni textos clínicos. Si falta un dato, dejarlo en null o "pendiente" (o marcarlo VERIFICAR) y avisar.
2. Privacidad: sin registro ni inicio de sesión. No guardar nombres, teléfonos, ubicaciones, zona elegida ni tokens de dispositivo (RS-F04, RS-F10, RS-NF05). El GPS, si se usa, solo en el momento y sin enviarlo ni guardarlo.
3. Mostrar siempre la hora de la medición y de la última sincronización (hora de Bogotá) y el aviso cuando el dato esté desactualizado (RS-NF12).
4. Lenguaje simple, sin tecnicismos para la usuaria e informativo, sin indicaciones médicas (RU-NF01, RS-NF16).
5. Alcance geográfico: solo Ciudad Bolívar (RS-NF10).
6. Todo dato de demostración va rotulado "DATOS SIMULADOS".
7. Fuera de alcance: login, ML predictivo, pagos, BI, SMS, redes sociales y soporte.

## Requisitos de sistema vigentes (Sprints 2 y 3)
- RS-F04 selección de zona (manual o GPS sin persistir) · RS-F05 asociar la zona a la estación más cercana con una tabla estática interna.
- RS-F06 push por tema de zona (FCM) cuando el ICA pase a naranja o rojo · RS-NF02 publicar en menos de 5 min.
- RS-F07 una sola recomendación de autocuidado por nivel · RS-F08 ventilación según el dato vigente (cerrar en naranja/rojo, ventilar en verde) · RS-F09 aviso de reducir el ritmo al desplazarse en naranja/rojo.
- RS-NF04 coincidencia del 100 % entre el nivel mostrado y la recomendación · RS-F10 y RS-NF05 anonimato.
- RS-NF08 módulos separados (ingesta, motor ICA, notificaciones) · RS-NF07 y RS-NF17 las fallas de terceros no tumban el sistema · RS-NF15 HTTPS.

## Calendario 2026
Sprint 2 (zonas y app base) 19-30 oct · Sprint 3 (push y recomendaciones) 3-13 nov · Sprint 4 (privacidad y estabilidad) 17-20 nov · Sprint 5 (piloto y cierre) 24-27 nov.
