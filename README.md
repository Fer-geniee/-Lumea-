# Lumea · Backend

API REST en Flask que recibe la foto de un alimento, la reconoce con dos redes
MobileNetV2 (transfer learning), consulta su información nutricional en MySQL y
responde en JSON. También maneja perfiles con login (bcrypt), estado de ánimo,
historial y gamificación.

## Cómo correrlo

```bash
cd Backend
pip install -r requirements.txt
python3 app.py            # http://127.0.0.1:5002  ·  demo de cámara: /camara
```

Necesita MySQL encendido y un archivo `.env` (nunca se sube) con `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `USDA_API_KEY`.

**Todo se ejecuta desde esta carpeta** (`python3 pruebas/test_api.py`, no desde
dentro de `pruebas/`): algunos scripts usan rutas relativas como `dataset/`.

## Estructura

```
Backend/
├── app.py                 Rutas de la API (Flask). Orquesta; no tiene lógica de IA.
├── predict.py             Carga los dos modelos y decide en cascada (primero el regional).
├── database.py            Toda la capa MySQL (consultas parametrizadas, migraciones suaves).
├── gamificacion.py        XP, niveles, rachas, misiones y avatar (Blueprint de Flask).
├── gamificacion_config.py Todos los números de la gamificación, en un solo lugar.
├── grupos_confusion.py    Alimentos que siempre piden confirmación humana.
├── sellos.py              Sellos de advertencia (Res. 810 de 2021).
├── camara.html            Demo de la cámara (servida por la ruta /camara).
├── static/                Imágenes de avatares.
├── modelo_lumea_comida.keras + clases.json      Modelo regional (35 clases).
├── modelo_lumea101.keras + clases_101.json      Modelo Food-101 (101 clases).
├── pruebas/               Pruebas automáticas de la API, login, gamificación y confirmación.
├── entrenamiento/         Entrenamiento del modelo regional y limpieza/recolección del dataset.
├── herramientas/          Evaluación y diagnóstico del modelo (incluye la prueba de campo) y crear_usuario_demo.py (cuenta de demostración para el video).
├── datos/                 Tablas nutricionales en CSV con sus fuentes (USDA, ICBF, receta).
├── docs/                  Contratos de la API, guía del frontend, colección de Postman.
└── historico/             Evidencia de etapas anteriores (ver abajo). No se usa en producción.
```

Los modelos y `clases*.json` viven en la raíz a propósito: `predict.py` los carga
y `entrenamiento/ia_comida.py` los escribe ahí.

## Etapas del proyecto (`historico/`)

- `etapa1_frontend_escritorio/`: la primera versión, una app de escritorio en
  Python. Su base de datos local SQLite (`lumea.db`) también está aquí, fuera de git.
- `diagnostico_keras2/`: scripts del incidente de compatibilidad Keras 2 → 3
  (pesos corruptos en BatchNorm). Apuntan a archivos `.h5` que ya no existen; se
  conservan como evidencia del método de diagnóstico.
- `predict_antes.py`: la regla de decisión anterior ("gana el modelo más seguro"),
  reemplazada por la cascada tras la prueba de campo del 1 de octubre de 2026.

Detalle completo: `DEFENSA_TECNICA_LUMEA.md`, sección 10.
