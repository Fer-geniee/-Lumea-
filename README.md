# Lumea · Backend · El cerebro detrás de Lumea 

API REST en Flask que recibe la foto de un alimento, la reconoce con dos redes
MobileNetV2 (transfer learning) entrenadas con dos datasets (uno regional, de
35 clases, y Food-101), consulta su información nutricional en MySQL y
responde en JSON. También maneja perfiles con login (bcrypt), estado de ánimo,
historial y gamificación.

## Cómo correrlo

```bash
cd Backend
pip install -r requirements.txt
python3 app.py            # http://127.0.0.1:5002  ·  demo de cámara: /camara
```

Necesita **MySQL encendido** y un archivo `.env` en `Backend/` (el nombre exacto es `.env`; nunca se sube) con
`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `USDA_API_KEY`. Sin MySQL, `app.py` arranca pero casi todo falla.
El puerto es el **5002** (el 5000 lo ocupa AirPlay Receiver en macOS). Si cambia, hay que cambiarlo también en el frontend
(`api.js`, `API_BASE_URL`): son dos repositorios.

**Todo se ejecuta desde esta carpeta** (`python3 pruebas/test_api.py`, no desde
dentro de `pruebas/`): algunos scripts usan rutas relativas como `dataset/`.

### Datos que hay que cargar en MySQL

Las tablas se crean solas al arrancar, pero `tabla_alimentos` llega vacía:

| Qué | Cómo |
|---|---|
| Nutrición de los 168 alimentos | Los CSV de `datos/alimentos_*.csv` (con sus `*_fuentes.csv`), con `cargar_alimentos_desde_csv()` de `database.py` |
| Datos curiosos (141) | `python3 herramientas/cargar_datos_curiosos.py` lee `datos/datos_curiosos.csv`. Con `--comprobar` solo compara con MySQL, sin escribir. |
| Sellos de advertencia | `cargar_sellos.py --cargar` (en `Pipelines de datos/`, en el repositorio de la raíz del proyecto, no en este) |

Los importadores que generaron esos CSV (USDA, ICBF, Open Food Facts) también viven en `Pipelines de datos/`.

## Estructura

```
Backend/
├── app.py                 Rutas de la API (Flask). Orquesta; no tiene lógica de IA.
├── predict.py             Carga los dos modelos y decide en cascada (primero el regional).
├── database.py            Toda la capa MySQL (consultas parametrizadas, migraciones suaves).
├── gamificacion.py        XP, niveles, rachas, misiones y la persona voxel-art (Blueprint de Flask).
├── gamificacion_config.py Todos los números de la gamificación, en un solo lugar.
├── grupos_confusion.py    Alimentos que siempre piden confirmación humana.
├── sellos.py              Sellos de advertencia (Res. 810 de 2021).
├── dato_del_dia.py        El dato curioso del día (GET /dato-del-dia), el mismo para todos en un día de Bogotá.
├── camara.html            Demo de la cámara (servida por la ruta /camara).
├── static/                Imágenes de las capas PNG del avatar (en desuso desde el 9 oct).
├── modelo_lumea_comida.keras + clases.json      Modelo regional (35 clases).
├── modelo_lumea101.keras + clases_101.json      Modelo Food-101 (101 clases).
├── consejos.py            Elige el consejo de cada alimento; los textos están en consejos_config.py.
├── pruebas/               Pruebas automáticas (ver «Pruebas»).
├── entrenamiento/         Entrenamiento del modelo regional y limpieza/recolección del dataset.
├── herramientas/          Evaluación y diagnóstico del modelo (incluye la prueba de campo) crear_usuario_demo.py (cuenta de demostración para el video) y cargar_datos_curiosos.py.
├── datos/                 Tablas nutricionales en CSV con sus fuentes (USDA, ICBF, receta), grupos_plato.csv y datos_curiosos.csv.
├── docs/                  Contratos de la API, guía del frontend, colección de Postman.
└── historico/             Evidencia de etapas anteriores (ver abajo). No se usan en producción.
```

Los modelos y `clases*.json` viven en la raíz a propósito: `predict.py` los carga
y `entrenamiento/ia_comida.py` los escribe ahí.

## La API

| Ruta | Para |
|---|---|
| `POST /predecir` | Foto del alimento (campo `file`, y `email` opcional). Reconoce con los dos modelos; si la certeza es alta lo registra solo, si no pide confirmar (`opciones_detalle`). |
| `POST /confirmar-alimento` | La persona elige el alimento cuando la IA duda o es un grupo de confusión (sopas, dulces, tamales, frituras, gaseosas). |
| `POST /perfil`, `GET /perfil` | Crear cuenta (con contraseña) o editar datos; ver el perfil. Sin peso ni altura; edad de 11 a 120; los menores de 18 marcan que su acudiente sabe. |
| `POST /login` | Inicio de sesión (bcrypt). Sin sesión ni token: el resto de la API identifica por correo. |
| `POST /estado-animo`, `GET /estado-animo` | Check-in de ánimo (5 niveles) y los últimos (`?dias=7`). |
| `GET /historial` | Comidas de la persona, cada una con `sellos_advertencia`, `es_fruta`, `grupo` y `sellos` (dato e idea de cada sello). |
| `GET /alimentos` | Lista de alimentos con su nutrición. |
| `GET /dato-del-dia` | El mismo dato curioso para todas las personas durante un día de Bogotá. Sin parámetros ni datos personales. |
| `GET /progreso`, `GET /calcomanias` | Semillas, etapa, racha, meta del día, misiones y calcomanías. |
| `GET /avatar` | La persona voxel-art: rasgos, lo que lleva puesto, el armario por etapas. |
| `POST /avatar/rasgos`, `/avatar/equipar`, `/avatar/quitar` | Cambiar cómo se ve la persona (libre) y qué prenda lleva (por etapa). |
| `GET /avatares`, `POST /avatar` | Compañeros DiceBear *gaze*. |
| `POST /avatar/base` | **En desuso** (capas PNG que no llegaron). |

Contratos con respuestas reales: `docs/CONTRATO_GAMIFICACION.md` y `docs/CONTRATO_CONFIRMACION.md`. Guía para el frontend:
`docs/GUIA_FRONTEND_SARA.md`. Para probar sin el frontend: `docs/Lumea.postman_collection.json` (variables `base_url`, `email`, `contrasena`).

## El Camino del cuidado (gamificación)

Está pensada para estudiantes de colegio: **premia registrar, nunca lo que se comió**, y nada depende de calorías, peso, cuerpo
ni del ánimo reportado.

- **Semillas** (lo que antes fue XP): se ganan por registrar una comida, un check-in de ánimo y las misiones del día. Hay tope diario por
  acción. **Nunca se pierden**: la pérdida por inactividad existe en el código pero está apagada. Nunca se resta por lo que se comió.
- **Etapas** (10 niveles): el nivel máximo nunca baja, y todo lo que se desbloquea por etapa se queda desbloqueado.
- **Compañeros**: criaturas DiceBear *gaze* cuyos ojos muestran el ánimo.
- **La persona y sus prendas**: un avatar *voxel-art* que el frontend dibuja en el navegador (no le pide nada a DiceBear). Los
  **rasgos** (13: piel, peinado, ojos, cejas, nariz, ropa de abajo, fondo...) son libres; cada etapa desbloquea **una prenda o accesorio** nuevo.
- **Calcomanías** (10): se ganan por lo que la persona hace; no dan semillas, no se quitan y no hay ranking.

Todos los números viven en `gamificacion_config.py`. Fundamento y autoría: `DEFENSA_TECNICA_LUMEA.md` (secciones 11 y 12, en el repositorio de la raíz del proyecto).

## Fuentes de datos

- **Nutrición**: Tabla de Composición de Alimentos Colombianos (TCAC 2018, ICBF), USDA FoodData Central, estimaciones por receta
  para platos regionales y Open Food Facts por producto (revisado a mano: tiene errores de carga). Cada CSV tiene su `*_fuentes.csv`.
- **Consejos y datos del día**: Guías Alimentarias Basadas en Alimentos del ICBF y recomendaciones de la OMS (azúcares libres,
  frutas y verduras). Los textos de `consejos_config.py` los aprobó Isabella.
- **Sellos de advertencia y `es_saludable`**: Resolución 810 de 2021 del Ministerio de Salud, con la modificación de la
  Resolución 2492 de 2022. «Sin sellos» no significa «saludable».
- **Datos curiosos** (`datos/datos_curiosos.csv`): **generados con IA, revisados por Isabella, sin verificación individual contra
  una fuente científica**. Son conocimiento general, no citas.

## Privacidad

- **Menores.** La edad mínima es 11 años. A quien tiene menos de 18 se le pide marcar que su madre, padre o acudiente sabe que
  usa Lumea (`acudiente_sabe`, con fecha). **Es un aviso, no una autorización verificada**; un lanzamiento real necesitaría la
  autorización del representante legal (Ley 1581 de 2012, art. 7, y Decreto 1377 de 2013, art. 12) y una política de tratamiento de datos.
- **Lo que se guarda**: nombre, correo, edad, género, objetivo, la contraseña como hash de bcrypt, el historial de comidas
  (código, nombre, certeza) y el ánimo. **No se piden peso ni altura.**
- **Las fotos no se guardan**: se procesan en memoria y solo se registra el resultado.
- **Secretos.** `.env` está en `.gitignore` y no se sube; `fotos_prueba/` tampoco. La contraseña nunca sale en respuestas ni en el log.
- **Terceros.** Los avatares y compañeros se dibujan en el navegador: el correo y los datos de la persona no se envían a DiceBear.

## Pruebas

Desde `Backend/`. Las de «con servidor» necesitan `app.py` corriendo (si el 5002 está ocupado, levanta otro en el 5099 y exporta
`LUMEA_URL=http://127.0.0.1:5099`). Todas necesitan MySQL, y la mayoría crean un usuario de prueba y lo borran al final.

| Prueba | Qué revisa | Pruebas |
|---|---|---|
| `python3 pruebas/test_api.py` (con servidor) | Todos los endpoints | 103 |
| `python3 pruebas/test_flujo_completo.py [--log archivo]` (con servidor) | El recorrido completo de una estudiante; con `--log`, que el log no tenga hashes ni contraseñas | 43 |
| `python3 pruebas/test_gamificacion.py` | Lógica de gamificación, avatar y rasgos | 104 |
| `python3 pruebas/test_login.py` (con servidor) | Login con bcrypt | 8 |
| `python3 pruebas/test_confirmacion.py` | Grupos de confirmación y sellos | 14 |
| `python3 pruebas/test_consejos.py` | Consejos y su mapa de grupos | 26 |
| `python3 pruebas/test_concurrencia.py` | Peticiones simultáneas | 1 |
| `python3 pruebas/test_perfil.py` | Perfil: sin peso, edad, acudiente | 11 |
| `python3 pruebas/test_dato_del_dia.py` | `/dato-del-dia` | 12 |
| `python3 pruebas/test_historial.py` | `grupo` y `sellos` en `/historial` | 6 |

En total **328**. Además, `python3 "../Pipelines de datos/verificar_integridad_clases.py"` (desde `Backend/`, solo en el repositorio de la raíz) revisa que
las clases del modelo tengan fila de nutrición, y `python3 herramientas/verificar_modelo.py` revisa un modelo antes de reemplazarlo.

## Créditos

- **Isabella Fernanda Obando Ordóñez**: Líder técnica y de producto, arquitecta de software. Backend (Python, Flask, MySQL), modelos de IA y datos nutricionales, gamificación «Camino del cuidado», consejos y dirección del rediseño.
- **Sara Jiménez**: Desarrolladora frontend y diseñadora UI (páginas, estilos y primera interfaz web).
- **Laura Narváez**: Diseñadora UX/UI y redactora de contenidos (diseños en Figma, logo, paleta original, textos de la app, términos y condiciones y «Conócenos»).
- **Claude (Anthropic)**: Consultora (planeación, revisión y acompañamiento). **Claude Code**: aAistente de programación bajo la dirección de Isabella; cada aporte está registrado en la bitácora de IA.

## Uso de IA

- **En el producto**: dos redes MobileNetV2 con transfer learning reconocen los alimentos (modelo regional de 35 clases y Food-101).
- **En el desarrollo**: gran parte del código del backend, de las pruebas y de la documentación la escribió con ayuda de Claude Code
  (Anthropic) bajo la dirección de Isabella; **las decisiones y la revisión son de ella**. Los textos de `consejos_config.py` partieron
  de un borrador de Claude y los editó y aprobó Isabella. Los datos curiosos se generaron con IA y Isabella los revisó (ver «Fuentes de datos»).
- **Qué no hace la IA**: no decide qué se premia ni cuánto; esas reglas están en `gamificacion_config.py`, escritas y aprobadas por personas.

## Etapas del proyecto (`historico/`)

- `etapa1_frontend_escritorio/`: la primera versión, una app de escritorio en
  Python. Su base de datos local SQLite (`lumea.db`) también está aquí, fuera de git.
- `diagnostico_keras2/`: scripts del incidente de compatibilidad Keras 2 → 3
  (pesos corruptos en BatchNorm). Apuntan a archivos `.h5` que ya no existen; se
  conservan como evidencia del método de diagnóstico.
- `predict_antes.py`: la regla de decisión anterior ("gana el modelo más seguro"),
  reemplazada por la cascada tras la prueba de campo del 1 de octubre de 2026.

Detalle completo: `DEFENSA_TECNICA_LUMEA.md`, sección 10.
