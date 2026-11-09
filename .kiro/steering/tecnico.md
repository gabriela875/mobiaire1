---
inclusion: always
---
# MobiAire · convenciones técnicas

- Python 3 con librería estándar y requests (firebase-admin solo en notificaciones). Interfaz en HTML, JS y CSS sin framework (web/). Servidor: web/server.py (http.server, solo lectura).
- Carpetas: motor_ica/ (ICA, semáforo y la nueva conversion_waqi.py), ingesta/ (IDEAM: API, normalizador, cálculo, almacén), web/ (incluye waqi.py con token y caché de 10 min), y las nuevas zonas/ y notificaciones/ como módulos separados. Las pruebas van junto a cada módulo (test_*.py).
- Antes de terminar cualquier tarea, python -m pytest debe pasar (hoy son 55 pruebas) y se agregan pruebas de lo nuevo.
- Estilo: código simple y corto, comentarios mínimos, nombres y mensajes en español, funciones pequeñas y puras cuando se pueda. No agregar dependencias sin avisar.
- Configuración solo por variables de entorno (.env, plantilla en .env.example). Claves, tokens y credenciales de Firebase nunca en el repo ni en los logs; confirmar que .gitignore los excluye.
- Las fallas de fuentes externas (IDEAM, WAQI, FCM) se registran y no tumban el ciclo de ingesta ni el servidor.
- Comandos: python -m pytest · python -m ingesta.ingesta --una-vez | --demo | (continuo) · python -m ingesta.resumen --html · python -m ingesta.validar "ciudad bolivar" · python -m web.server (http://127.0.0.1:8000).
- Formato de datos: leer ingesta/calculo.py e ingesta/almacen.py para ver los campos de resultados.json; no duplicarlos ni cambiarlos sin necesidad.
- Respuestas en el chat: breves. No pegar el código completo; resumir los cambios por archivo.
