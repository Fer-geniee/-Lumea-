# Contrato de la API de gamificación

Para quien construya el frontend de la gamificación. Todos los ejemplos son **respuestas reales** del backend (26 y 27 sep, 5 y 8 oct 2026), no inventadas.

- Base: `http://127.0.0.1:5002` (igual que el resto de la API; ver `api.js` del frontend).
- Identificación del usuario: por `email`, como el resto de la API. **Cuando esté listo el login, esto puede cambiar** (se ajusta en un solo lugar del backend: `_usuario_id_desde_email` en `gamificacion.py`).
- Los números (XP por acción, topes, meta, niveles, pérdida por inactividad, avatares, ropa y accesorios) viven en `gamificacion_config.py` y son **provisionales**. No los copies en el frontend: `GET /progreso` los devuelve en `reglas`.

## Vocabulario de pantalla (Camino del cuidado, 8 oct 2026)

Lumea se reorientó con el «Camino del cuidado». **Es solo vocabulario de pantalla**: lo que se ve dice **«semillas»** donde la API dice XP y **«etapa»** donde dice nivel. **Las claves de la API no cambian**: `xp_total`, `xp_ganado`, `nivel`, `nivel_maximo`, `nivel_anterior`, `nivel_requerido`, `meta_diaria`, `subio_de_nivel`... siguen igual, para no romper el frontend. Cambia únicamente el texto que llega listo para mostrar (mensajes, nombres y descripciones, que escribe Isabella en `gamificacion_config.py`). Así que en la pantalla: `xp_total` se muestra como «semillas» y `nivel` como «etapa». Los otros cambios de esta fecha:

- **Bonus por registro** (`bonus_registro`): reemplaza al bonus de «elección nutritiva». Ya no depende del alimento: es el mismo para un banano que para un producto con sellos.
- **Sin pérdida por inactividad:** `xp_perdido_por_dia_inactivo` y `tope_perdida_por_periodo` valen 0. Nadie pierde semillas por ausentarse.
- **`mensaje_regreso`** ahora depende de los **días de ausencia**, no de haber perdido XP.
- **Compañeros gaze:** los seis avatares DiceBear son compañeros del estilo *gaze* 10.x, con `forma` y `color`; sus ojos muestran el ánimo.

## Reglas (para diseñar las pantallas)

- Se gana XP por **registrar**: una comida (guardada por `/predecir` o por `/confirmar-alimento`) o el estado de ánimo del día.
- **Puntos v2 (27 sep):** un bonus pequeño **por registrar** (`bonus_registro`, +5, máx. 3 al día, igual para cualquier alimento) y **misiones diarias** fijas (+10 cada una). Nunca se resta XP por lo que se comió: la penalización por ultraprocesados existe pero vale 0. Ver la sección "Puntos v2" más abajo.
- El XP **no depende** del ánimo reportado. Nunca mostrar mensajes que premien calorías, peso ni cuerpo, ni que premien sentirse bien, ni que regañen por lo que se comió.
- Cada acción tiene un **tope diario**. Pasado el tope, la acción se guarda igual, pero da 0 XP (`tope_diario_alcanzado: true`).
- **Racha:** días seguidos con al menos una actividad. Si un día no hay actividad, se reinicia.
- **Meta diaria:** llegar a `meta` XP en el día.
- **Pérdida por inactividad (27 sep; apagada desde el 8 oct):** el mecanismo existe: cada día completo sin ninguna actividad restaría `xp_perdido_por_dia_inactivo` XP, con un tope de `tope_perdida_por_periodo` por ausencia. **Hoy los dos valen 0: no se pierde nada.** Si algún día se encienden, el XP nunca baja de 0, **el nivel nunca baja** y **nada de lo desbloqueado se vuelve a bloquear** (todo depende del nivel máximo alcanzado).
- **Sin rankings** ni comparaciones con otros usuarios (lo promete `guialumea.html`).
- **Calcomanías (5 oct 2026, decisión de Isabella):** sí hay, y cambian la decisión del 27 sep de "sin insignias ni logros". No dan XP ni se quitan. Ver la sección "Calcomanías".

### Puntos v2: cuánto da cada cosa

| Qué | XP | Tope |
|---|---|---|
| Registrar una comida | +10 | 5 al día |
| Bonus por registro (extra, sobre la comida) | +5 | 3 al día |
| Misión "Registra una fruta" | +10 | 1 al día |
| Misión "Registra 3 comidas" | +10 | 1 al día |
| Misión "Haz tu check-in de ánimo" | +10 | 1 al día |
| Registrar el estado de ánimo | +5 | 1 al día |
| Día inactivo | **0** (apagada; el parámetro existe) | — |
| Registrar un ultraprocesado | **0** (parámetro existe, apagado) | — |

- **Bonus por registro:** se suma a cada comida guardada (reconocida o confirmada), **sea cual sea el alimento y tenga o no sellos**. Lo único que lo limita es el tope diario (`maximo_por_dia`). Antes (27 sep al 8 oct) era una «elección nutritiva» que dependía de los sellos y del tipo de producto; Isabella lo cambió para que el XP premie registrar y no lo que se come.
- **Misiones:** fijas, iguales todos los días, una vez al día cada una. Cuentan desde la medianoche.
- **Ultraprocesados:** al registrar un producto de paquete, `/predecir` y `/confirmar-alimento` devuelven `mensaje_educativo`: un dato y una alternativa para otro día, nunca un regaño. **No se resta XP.**

### Por qué la penalización por ultraprocesados vale 0

El parámetro `XP_PENALIZACION_ULTRAPROCESADO` existe en `gamificacion_config.py`, pero vale 0, y con 0 no resta nada. Es a propósito:

1. **Honestidad de los registros.** Si registrar una gaseosa quita puntos, la forma fácil de no perderlos es no registrarla. La app deja de reflejar lo que de verdad se come y pierde su sentido.
2. **No asociar culpa a la comida en adolescentes.** La guía de la Academia Americana de Pediatría para prevenir la obesidad y los trastornos alimentarios en adolescentes (Golden et al., 2016, *Pediatrics* 138(3):e20161649) recomienda no promover dietas ni hablar de comida o peso en términos de culpa, y enfocarse en hábitos. Por eso, desde el 8 oct, nada de lo que se gana depende de qué se comió: ni siquiera el bonus, que ahora premia solo el registro.

Cambiarlo es una decisión del equipo, no un ajuste técnico.

### Cómo funciona la pérdida (hoy apagada; para explicarla en la sustentación)

**Hoy está apagada** (`xp_perdido_por_dia_inactivo = 0`): lo que sigue describe el mecanismo, que se conserva por si el equipo decide encenderlo.

No hay un servidor encendido todo el tiempo, así que nadie "resta XP a medianoche". La pérdida se calcula **cuando el usuario vuelve**: en `GET /progreso` o al registrar algo. Se cuentan los días completos entre la última actividad y hoy (hoy no cuenta: todavía puede registrar). El backend guarda cuánto lleva descontado en esa ausencia, así que preguntar dos veces el mismo día no descuenta dos veces.

Ejemplo con 5 XP por día y tope de 20 (valores de prueba, no los de hoy): registra el lunes y vuelve el jueves. Martes y miércoles fueron días inactivos, así que pierde 10 XP. Si vuelve a abrir la app el jueves, no pierde nada más. Si no registra nada y abre el viernes, pierde 5 más (15 en total). Nunca pasa de 20 en la misma ausencia.

### Mensaje de regreso: depende de los días de ausencia

`mensaje_regreso` (el texto de Isabella) sale cuando la persona vuelve después de **`DIAS_PARA_MENSAJE_REGRESO` (hoy 3) o más días completos sin actividad**, el mismo umbral de la calcomanía «volviste». Ya no depende de que se haya perdido XP.

- Sale **una sola vez por ausencia**, en la primera respuesta de `GET /progreso` después de volver: o bien al abrir `/progreso` antes de registrar nada, o bien después de registrar algo (el aviso espera a la siguiente visita a `/progreso`).
- Si la persona se ausenta otra vez, ese nuevo regreso vuelve a dar el mensaje.
- Hoy de 1 o 2 días sin actividad no dice nada. Los días son «completos»: hoy no cuenta, porque todavía puede registrar algo.
- Se anota en `eventos_xp` con 0 XP (`aviso_regreso_pendiente` y `aviso_regreso`), sin columnas nuevas.

## Qué ruta para qué

| Ruta | Para |
|---|---|
| `GET /progreso` | Dashboard: XP, nivel, racha, meta del día, aviso de regreso, cara DiceBear con el ánimo de hoy, resumen de calcomanías. |
| `GET /calcomanias` | Pantalla de calcomanías: las 10, con cuáles están ganadas y cómo conseguir las demás. |
| `GET /avatar` (singular) | Pantalla "personalizar avatar" (capas de Figma): base, ropa y accesorio. |
| `POST /avatar/base`, `POST /avatar/equipar`, `POST /avatar/quitar` | Cambiar el avatar por capas. |
| `GET /avatares` (plural) y `POST /avatar` | Avatares DiceBear: la cara del check-in de ánimo, y el avatar de **respaldo** si el diseño de Figma no llega a tiempo. |

Ojo: `GET /avatar` (capas) y `POST /avatar` (DiceBear) comparten la dirección pero son cosas distintas.

## Calcomanías (insignias) · nuevo, 5 oct 2026

**Cambia una decisión.** El 27 sep el equipo decidió "sin insignias ni logros". El **5 oct 2026, Isabella** decidió agregar **calcomanías**, porque dan una razón visible para volver sin competir con nadie. Siguen valiendo las reglas de contenido: se ganan por lo que la persona **hace** (registrar, volver, ayudar a la IA), nunca por qué comió, calorías, peso, cuerpo ni qué ánimo reportó. **No dan XP**, **no se quitan** y **no hay ranking**. Los nombres son provisionales: se renombran en `CALCOMANIAS` de `gamificacion_config.py`.

| id | nombre | se gana cuando | rol |
|---|---|---|---|
| `primera_foto` | Primera foto | registra su primera comida | `comida` |
| `diez_registros` | Diez registros | lleva 10 comidas registradas | `comida` |
| `tres_al_dia` | Tres al día | cumple por primera vez la misión de 3 comidas | `mision` |
| `fruta` | Fruta del día | cumple por primera vez la misión de fruta | `mision` |
| `como_llegas` | Cómo llegas | hace su primer check-in de ánimo | `emocion` |
| `ayudaste_ia` | Le ayudaste a la IA | confirma un plato cuando la IA dudó | `duda` |
| `racha_3` | Tres días seguidos | llega a una racha de 3 días | `logro` |
| `racha_7` | Una semana | llega a una racha de 7 días | `logro` |
| `volviste` | Volviste | regresa después de 3 o más días sin actividad | `logro` |
| `nivel_5` | Nivel 5 | llega al nivel 5 | `logro` |

`rol` le dice al frontend qué dibujo o color usar. Cada calcomanía se otorga **una sola vez** por usuario (la base lo impide).

### Dónde llegan

1. **En el momento**: la clave `gamificacion` de `/predecir`, `/confirmar-alimento` y `POST /estado-animo` trae `calcomanias_nuevas` (lista vacía si ninguna): las ganadas **con esta acción**, para celebrarlas una sola vez. Cada una trae `{id, nombre, descripcion, rol}`.
2. **Resumen**: `GET /progreso` trae `"calcomanias": {"ganadas": 4, "total": 10}`.
3. **Colección**: `GET /calcomanias?email=<correo>`.

### `GET /calcomanias?email=<correo>`

Respuesta real (recortada: son 10 en total) de alguien que registró un banano y un mango, y su check-in de ánimo:

```json
{
  "success": true,
  "ganadas": 4,
  "total": 10,
  "calcomanias": [
    { "id": "primera_foto", "nombre": "Primera foto", "descripcion": "Registraste tu primera comida.",
      "como_se_gana": "Registra tu primera comida.", "rol": "comida", "ganada": true, "fecha": "2026-10-05" },
    { "id": "diez_registros", "nombre": "Diez registros", "descripcion": "Llevas 10 comidas registradas.",
      "como_se_gana": "Registra 10 comidas.", "rol": "comida", "ganada": false, "fecha": null },
    { "id": "tres_al_dia", "nombre": "Tres al día", "descripcion": "Registraste 3 comidas en un mismo día.",
      "como_se_gana": "Cumple la misión de registrar 3 comidas en un día.", "rol": "mision", "ganada": false, "fecha": null }
  ]
}
```

- Siempre vienen las 10, en el orden del catálogo. Las que faltan traen `ganada: false` y `fecha: null`; usa `como_se_gana` para decirle a la persona cómo conseguirlas (sin presión).
- Errores: `400` sin `email`, `404` si el correo no tiene perfil (igual que las otras rutas).
- **Quien ya cumplía una regla antes de que existieran las calcomanías** la recibe al consultar esta ruta, **sin anunciarla** como nueva (`calcomanias_nuevas` no la trae). Su `fecha` es la del día de la consulta, porque no se sabe cuándo la cumplió. Para esos usuarios, `ayudaste_ia` se deduce de comidas guardadas con certeza 100 (así se guarda una confirmación humana).

## `GET /progreso?email=<correo>`

Estado completo del usuario. Un usuario sin actividad todavía recibe ceros (no es error). Aquí se descuenta la pérdida por inactividad pendiente.

Ejemplo real de alguien que vuelve después de 6 días sin actividad (5 días completos), con la pérdida apagada. Para sacarlo se corrió en la base de datos la fecha de la última actividad 6 días atrás:

```json
{
  "progreso": {
    "avatar": {
      "color": "C9C3F0",
      "estado_animo_hoy": "bien",
      "forma": "arch",
      "id": "luna",
      "nombre": "Luna",
      "url": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=dots",
      "url_con_animo": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=happy",
      "urls_por_estado": {
        "bien": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=happy",
        "mal": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=small",
        "muy_bien": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=grin",
        "muy_mal": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=bars",
        "neutral": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=dots"
      }
    },
    "calcomanias": {
      "ganadas": 4,
      "total": 10
    },
    "mensaje_regreso": "🌿 Siempre puedes volver, tu camino no termina cuando haces una pausa, ni cuando te encuentras con dificultades. El camino continúa cuando perdonas y sostienes las dificultades en paz. ¡Qué bueno tenerte de vuelta!",
    "meta_diaria": {
      "cumplida": true,
      "meta": 15,
      "xp_hoy": 40
    },
    "misiones": [
      {
        "cumplida": true,
        "id": "fruta",
        "nombre": "Agradece y disfruta una fruta de la creación",
        "xp": 10
      },
      {
        "cumplida": false,
        "id": "tres_comidas",
        "nombre": "Cuida de ti en tus tres comidas",
        "xp": 10
      },
      {
        "cumplida": true,
        "id": "check_in_animo",
        "nombre": "Haz una pausa y escucha cómo te sientes",
        "xp": 10
      }
    ],
    "nivel": 2,
    "racha_actual": 0,
    "racha_maxima": 1,
    "reglas": {
      "acciones": {
        "bonus_registro": {
          "maximo_por_dia": 3,
          "xp": 5
        },
        "comida_registrada": {
          "maximo_por_dia": 5,
          "xp": 10
        },
        "estado_animo": {
          "maximo_por_dia": 1,
          "xp": 5
        }
      },
      "meta_diaria_xp": 15,
      "misiones_diarias": [
        {
          "id": "fruta",
          "nombre": "Agradece y disfruta una fruta de la creación",
          "xp": 10
        },
        {
          "id": "tres_comidas",
          "nombre": "Cuida de ti en tus tres comidas",
          "xp": 10
        },
        {
          "id": "check_in_animo",
          "nombre": "Haz una pausa y escucha cómo te sientes",
          "xp": 10
        }
      ],
      "niveles": [
        0,
        30,
        80,
        150,
        250,
        400,
        600,
        850,
        1150,
        1500
      ],
      "tope_perdida_por_periodo": 0,
      "xp_penalizacion_ultraprocesado": 0,
      "xp_perdido_por_dia_inactivo": 0
    },
    "ultima_fecha_actividad": "2026-10-02",
    "xp_faltante_siguiente_nivel": 40,
    "xp_inicio_nivel": 30,
    "xp_perdido_desde_ultima_visita": 0,
    "xp_siguiente_nivel": 80,
    "xp_total": 40
  },
  "success": true
}
```

(`meta_diaria.xp_hoy` y las misiones muestran lo de hoy: en la prueba se registró algo ese mismo día para tener una racha y una cara con ánimo; con una ausencia de verdad `racha_actual` sería 0.)

La segunda llamada responde lo mismo pero con `"mensaje_regreso": null`: **el aviso se da una sola vez**. Respuesta real de esa segunda llamada, en esos dos campos:

```json
{
  "xp_total": 40,
  "xp_perdido_desde_ultima_visita": 0,
  "mensaje_regreso": null
}
```

**Misiones del día** (campo `misiones` de `GET /progreso`, respuesta real después de registrar una fruta, tres comidas y el ánimo):

```json
"misiones": [
  { "id": "fruta", "nombre": "Registra una fruta", "xp": 10, "cumplida": true },
  { "id": "tres_comidas", "nombre": "Registra 3 comidas", "xp": 10, "cumplida": true },
  { "id": "check_in_animo", "nombre": "Haz tu check-in de ánimo", "xp": 10, "cumplida": true }
]
```

**Calcomanías** (campo `calcomanias` de `GET /progreso`, respuesta real después de registrar dos frutas y el ánimo):

```json
"calcomanias": { "ganadas": 4, "total": 10 }
```

Y `reglas` trae además `misiones_diarias` y `xp_penalizacion_ultraprocesado` (hoy 0), y `acciones` incluye `bonus_registro`.

Notas:
- `nivel` es el **nivel máximo alcanzado**: nunca baja. Si algún día se enciende la pérdida, `xp_total` podría quedar **por debajo** de `xp_inicio_nivel`. Para la barra de progreso usa `max(0, xp_total - xp_inicio_nivel) / (xp_siguiente_nivel - xp_inicio_nivel)`, o muestra «te faltan `xp_faltante_siguiente_nivel` semillas para la etapa siguiente».
- `xp_siguiente_nivel` y `xp_faltante_siguiente_nivel` son `null` en el último nivel.
- `xp_perdido_desde_ultima_visita` vale 0 mientras la pérdida esté apagada (si se enciende, también incluye lo que se descontó si el usuario registró algo antes de abrir `/progreso`).
- Muestra `mensaje_regreso` tal cual, con tono amable; no lo reescribas. Si algún día se enciende la pérdida y quieres mostrar el número, que sea discreto; nunca como regaño.
- `racha_actual` ya viene "vigente": si la última actividad fue antes de ayer, llega en 0.
- `avatar` es el **compañero** DiceBear *gaze* 10.x, con su `forma` y su `color` (hexadecimal de 6 dígitos, **sin `#`**). `avatar.url` es el compañero con los ojos neutros. `url_con_animo` usa el último estado de ánimo de **hoy** (neutros si no hay; en ese caso `estado_animo_hoy` es `null`). `urls_por_estado` sirve para dibujar el selector de ánimo con el propio compañero. Las URL son **quietas**: gaze solo anima si se le pide `animationVariant`, y eso lo agrega el frontend donde quiera.

Errores: `400` sin `email`, `404` si el correo no tiene perfil.

## Avatar por capas (diseño de Figma), opcional

El avatar del perfil se arma apilando PNG transparentes del mismo tamaño: abajo la **base** (2 para elegir), encima la **ropa** y encima el **accesorio**. La ropa y los accesorios se desbloquean con el **nivel máximo** y nunca se vuelven a bloquear. Cada usuario lleva como máximo una prenda y un accesorio, o ninguno.

**Mientras no existan las imágenes**, todo responde igual, con los nombres de archivo y `"imagen_lista": false`: el frontend muestra un marcador en vez de la imagen. Si el diseño no llega a tiempo, el perfil usa el avatar DiceBear (`respaldo_dicebear`). Especificación para la diseñadora: `ESPECIFICACION_AVATARES_FIGMA.md`.

### `GET /avatar?email=<correo>`

Respuesta real (nivel máximo 2, sin imágenes todavía):

```json
{
  "success": true,
  "nivel_maximo": 2,
  "imagenes_listas": false,
  "base": { "id": "base_1", "nombre": "Base 1", "archivo": "base_1.png", "imagen_lista": false,
            "url": "http://127.0.0.1:5002/static/avatar/base_1.png" },
  "puesto": { "ropa": null, "accesorio": null },
  "capas": [
    { "tipo": "base", "id": "base_1", "archivo": "base_1.png", "imagen_lista": false,
      "url": "http://127.0.0.1:5002/static/avatar/base_1.png" }
  ],
  "bases": [
    { "id": "base_1", "nombre": "Base 1", "archivo": "base_1.png", "imagen_lista": false, "seleccionada": true,
      "url": "http://127.0.0.1:5002/static/avatar/base_1.png" },
    { "id": "base_2", "nombre": "Base 2", "archivo": "base_2.png", "imagen_lista": false, "seleccionada": false,
      "url": "http://127.0.0.1:5002/static/avatar/base_2.png" }
  ],
  "objetos": {
    "ropa": [
      { "id": "buzo_verde", "tipo": "ropa", "nombre": "Buzo verde", "archivo": "ropa_buzo_verde.png", "imagen_lista": false,
        "nivel_requerido": 1, "desbloqueado": true, "niveles_faltantes": 0, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/ropa_buzo_verde.png" },
      { "id": "camiseta_lumea", "tipo": "ropa", "nombre": "Camiseta Lumea", "archivo": "ropa_camiseta_lumea.png", "imagen_lista": false,
        "nivel_requerido": 3, "desbloqueado": false, "niveles_faltantes": 1, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/ropa_camiseta_lumea.png" },
      { "id": "ruana", "tipo": "ropa", "nombre": "Ruana", "archivo": "ropa_ruana.png", "imagen_lista": false,
        "nivel_requerido": 6, "desbloqueado": false, "niveles_faltantes": 4, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/ropa_ruana.png" }
    ],
    "accesorio": [
      { "id": "gafas", "tipo": "accesorio", "nombre": "Gafas", "archivo": "accesorio_gafas.png", "imagen_lista": false,
        "nivel_requerido": 2, "desbloqueado": true, "niveles_faltantes": 0, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/accesorio_gafas.png" },
      { "id": "audifonos", "tipo": "accesorio", "nombre": "Audífonos", "archivo": "accesorio_audifonos.png", "imagen_lista": false,
        "nivel_requerido": 4, "desbloqueado": false, "niveles_faltantes": 2, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/accesorio_audifonos.png" },
      { "id": "sombrero_vueltiao", "tipo": "accesorio", "nombre": "Sombrero vueltiao", "archivo": "accesorio_sombrero_vueltiao.png", "imagen_lista": false,
        "nivel_requerido": 8, "desbloqueado": false, "niveles_faltantes": 6, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/accesorio_sombrero_vueltiao.png" }
    ]
  },
  "respaldo_dicebear": {
    "color": "F6B73C",
    "forma": "circle",
    "id": "sol",
    "nombre": "Sol",
    "url": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-sol&shapeVariant=circle&bodyColor=F6B73C&eyesVariant=dots"
  }
}
```

(Claves reordenadas para leerlas mejor; el backend las manda en orden alfabético.)

- `capas` ya viene **en el orden de apilado** (la primera va abajo). Dibuja una `<img>` por capa, una encima de otra.
- `imagen_lista: false` → esa imagen todavía no existe: muestra un marcador. `imagenes_listas` es `true` solo cuando existen las 8.
- `niveles_faltantes` es 0 si ya está desbloqueado. Para el candado: "Nivel `nivel_requerido`" o "Te faltan `niveles_faltantes` niveles".

Errores: `400` sin `email`, `404` sin perfil.

### `POST /avatar/base`

```json
{ "email": "ana@correo.com", "base_id": "base_2" }
```

`200`: el mismo cuerpo de `GET /avatar`, ya con la base nueva (así el frontend redibuja con la respuesta). Las dos bases están disponibles desde el inicio.

### `POST /avatar/equipar`

```json
{ "email": "ana@correo.com", "tipo": "ropa", "item_id": "buzo_verde" }
```

`200`: el mismo cuerpo de `GET /avatar`. Extracto real de `puesto` y `capas` después de ponerse el buzo con la base 2:

```json
{
  "puesto": {
    "ropa": { "id": "buzo_verde", "nombre": "Buzo verde", "archivo": "ropa_buzo_verde.png", "imagen_lista": false,
              "url": "http://127.0.0.1:5002/static/avatar/ropa_buzo_verde.png" },
    "accesorio": null
  },
  "capas": [
    { "tipo": "base", "id": "base_2", "archivo": "base_2.png", "imagen_lista": false, "url": "http://127.0.0.1:5002/static/avatar/base_2.png" },
    { "tipo": "ropa", "id": "buzo_verde", "archivo": "ropa_buzo_verde.png", "imagen_lista": false, "url": "http://127.0.0.1:5002/static/avatar/ropa_buzo_verde.png" }
  ]
}
```

Ponerse otra prenda reemplaza la anterior (solo una por tipo).

| Código | Cuándo | Cuerpo |
|---|---|---|
| `400` | Falta `tipo` o `item_id`, el tipo no existe, el objeto no existe, o el objeto es de otro tipo | `{"error": "..."}` |
| `403` | El objeto existe pero está bloqueado | `{"error": "El objeto \"audifonos\" todavía está bloqueado.", "nivel_maximo": 1, "nivel_requerido": 4, "niveles_faltantes": 3}` |
| `404` | El correo no tiene perfil | `{"error": "No existe un perfil con ese correo."}` |

### `POST /avatar/quitar`

```json
{ "email": "ana@correo.com", "tipo": "ropa" }
```

`200`: el mismo cuerpo de `GET /avatar`, sin nada de ese tipo. Quitar cuando no hay nada puesto no es error. `400` si el tipo no existe.

## Avatares DiceBear (ánimo y respaldo)

### `GET /avatares?email=<correo>`

Catálogo completo, con lo que el usuario ya desbloqueó. **Cambió el 27 sep:** ahora se desbloquea por **nivel máximo** (`nivel_requerido`), ya no por XP (`xp_requerido` desapareció), para que perder XP no vuelva a bloquear nada. Los umbrales son los mismos de antes (80 XP = nivel 3, etc.).

```json
{
  "avatar_actual": "sol",
  "avatares": [
    {
      "color": "F6B73C",
      "desbloqueado": true,
      "forma": "circle",
      "id": "sol",
      "nivel_requerido": 1,
      "niveles_faltantes": 0,
      "nombre": "Sol",
      "seleccionado": true,
      "url": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-sol&shapeVariant=circle&bodyColor=F6B73C&eyesVariant=dots"
    },
    {
      "color": "C9C3F0",
      "desbloqueado": true,
      "forma": "arch",
      "id": "luna",
      "nivel_requerido": 1,
      "niveles_faltantes": 0,
      "nombre": "Luna",
      "seleccionado": false,
      "url": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=dots"
    },
    {
      "color": "52DCD8",
      "desbloqueado": false,
      "forma": "pill",
      "id": "rio",
      "nivel_requerido": 3,
      "niveles_faltantes": 1,
      "nombre": "Río",
      "seleccionado": false,
      "url": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-rio&shapeVariant=pill&bodyColor=52DCD8&eyesVariant=dots"
    }
  ],
  "nivel_maximo": 2,
  "success": true,
  "xp_total": 40
}
```

(Recortado a 3 de los 6 compañeros; cada uno trae `forma` y `color`, que ya van dentro de la `url`, por si el frontend no quiere leerla.) Errores: `400` sin `email`, `404` sin perfil.

### `POST /avatar`

Body (JSON):

```json
{ "email": "ana@correo.com", "avatar_id": "luna" }
```

Respuesta `200`:

```json
{
  "avatar": {
    "color": "C9C3F0",
    "forma": "arch",
    "id": "luna",
    "nombre": "Luna",
    "url": "https://api.dicebear.com/10.x/gaze/svg?seed=lumea-luna&shapeVariant=arch&bodyColor=C9C3F0&eyesVariant=dots"
  },
  "success": true
}
```

| Código | Cuándo | Cuerpo |
|---|---|---|
| `400` | Falta `avatar_id`, falta `email`, o el avatar no existe | `{"error": "..."}` |
| `403` | El avatar existe pero está bloqueado (**cambió**: antes decía `xp_faltante`) | `{"error": "El avatar \"rio\" todavía está bloqueado.", "nivel_maximo": 1, "nivel_requerido": 3, "niveles_faltantes": 2}` |
| `404` | El correo no tiene perfil | `{"error": "No existe un perfil con ese correo."}` |

## Cambios en endpoints que ya existían

`POST /predecir` (cuando guarda), `POST /confirmar-alimento` y `POST /estado-animo` traen la clave `gamificacion`. Es `null` cuando no aplica (predicción sin `email`, o si el registro no se guardó). Si no es `null` (respuesta real de `/confirmar-alimento` con banano, la primera comida del día):

```json
{
  "accion": "comida_registrada",
  "calcomanias_nuevas": [
    {
      "descripcion": "Has dado el primer paso en el camino del cuidado.",
      "id": "primera_foto",
      "nombre": "Primer paso",
      "rol": "comida"
    },
    {
      "descripcion": "Has comido y registrado una fruta.",
      "id": "fruta",
      "nombre": "Una fruta para alegrar tu día",
      "rol": "mision"
    },
    {
      "descripcion": "Confirmaste un plato cuando la IA dudó.",
      "id": "ayudaste_ia",
      "nombre": "Inteligencia humana al rescate",
      "rol": "duda"
    }
  ],
  "desbloqueos": [],
  "detalle_xp": [
    {
      "motivo": "comida_registrada",
      "xp": 10
    },
    {
      "motivo": "bonus_registro",
      "xp": 5
    },
    {
      "motivo": "mision_fruta",
      "xp": 10
    }
  ],
  "meta_diaria": {
    "cumplida": true,
    "meta": 15,
    "recien_cumplida": true,
    "xp_hoy": 25
  },
  "misiones_cumplidas": [
    {
      "id": "fruta",
      "nombre": "Agradece y disfruta una fruta de la creación",
      "xp": 10
    }
  ],
  "nivel": 1,
  "nivel_anterior": 1,
  "racha_actual": 1,
  "subio_de_nivel": false,
  "tope_diario_alcanzado": false,
  "xp_ganado": 25,
  "xp_total": 25
}
```

- **`xp_ganado` es el total de esta acción** (antes era solo el de la acción base): muéstralo como "+25 XP". `detalle_xp` dice de dónde salió cada parte, por si quieres mostrarlo ("+10 comida, +5 bonus por registro, +10 misión").
- `misiones_cumplidas` trae las misiones que se cumplieron **con esta acción**: celebración ("¡Misión cumplida: Registra una fruta!").
- `tope_diario_alcanzado` se refiere a la acción base (la comida o el ánimo).

Y la misma respuesta, con una bebida de paquete (la tercera comida del día), trae además en la raíz:

```json
{
  "alimento_codigo": "cocacola_original",
  "sellos_advertencia": [
    "azucares",
    "edulcorantes"
  ],
  "mensaje_educativo": "Dato: las gaseosas y bebidas azucaradas tienen bastante azúcar añadida. Si otro día quieres variar, el agua con limón o un jugo de fruta natural también refrescan.",
  "gamificacion": {
    "xp_ganado": 25,
    "detalle_xp": [
      {
        "motivo": "comida_registrada",
        "xp": 10
      },
      {
        "motivo": "bonus_registro",
        "xp": 5
      },
      {
        "motivo": "mision_tres_comidas",
        "xp": 10
      }
    ]
  }
}
```

(Recortada; la respuesta completa también trae `consejo`, ver `CONTRATO_CONFIRMACION.md`.) El **mismo bonus por registro** que una fruta, **sin resta**, y `mensaje_educativo` para mostrar con tono amable. Es `null` para lo que no es de paquete.

- `subio_de_nivel` y `meta_diaria.recien_cumplida` son `true` solo en la acción que lo provocó: úsalos para mostrar una celebración una sola vez.
- **Subida de nivel completa (5 oct):** `nivel_anterior` es el nivel máximo **antes** de esta acción (igual a `nivel` si no subió). `desbloqueos` lista todo lo que se abrió al subir: cada avatar u objeto con `nivel_anterior < nivel_requerido <= nivel`, y `[]` si no subió. Cada elemento es `{tipo, id, nombre, nivel_requerido}`, con `tipo` = `"avatar"` (DiceBear), `"ropa"` o `"accesorio"`. Respuesta real (un mango que llevó a alguien del nivel 1 al 2):

  ```json
  "nivel_anterior": 1, "nivel": 2, "subio_de_nivel": true,
  "desbloqueos": [ { "tipo": "accesorio", "id": "gafas", "nombre": "Gafas", "nivel_requerido": 2 } ]
  ```

  Si un solo salto cruza varios niveles, vienen todos, sin repetir. Para ponerse lo nuevo, `GET /avatar`.
- `calcomanias_nuevas`: las calcomanías ganadas con esta acción (ver "Calcomanías"); `[]` si ninguna. Es `[]` también si algo falló al otorgarlas: el XP se guarda igual.
- `nivel` es el nivel máximo (nunca baja).
- Si el usuario vuelve después de días inactivos y registra algo **antes** de abrir `/progreso`, el `mensaje_regreso` llega en la siguiente llamada a `GET /progreso` (y, si algún día se enciende la pérdida, `xp_total` ya viene con lo descontado).
- En `POST /estado-animo` viene además `avatar_url`: el compañero DiceBear con los ojos del ánimo que se acaba de registrar.

## Eliminado

`GET /puntos-racha` (la versión mínima anterior) ya no existe: responde `404`. El frontend nunca lo usó.

## Otros cambios del 5 oct 2026 (para la pantalla de Progreso)

- `GET /historial`: cada registro suma `es_fruta` (booleano; `true` si el alimento está en `FRUTAS` de `gamificacion_config.py`). Respuesta real de un registro: `{"alimento_codigo": "mango", "alimento_detectado": "Mango", "es_fruta": true, "sellos_advertencia": [], ...}`. No lo uses para juzgar la comida: sirve, por ejemplo, para marcar con un dibujo las frutas de la semana.
- `GET /estado-animo`: sin cambios por defecto (los últimos 30 registros, con `id`, `fecha` y `estado`). Nuevo parámetro opcional `?dias=7`: solo los registros de los últimos 7 días (hoy cuenta), aunque haya más de 30. Respuesta real: `{"success": true, "cantidad": 1, "historial": [{"id": 50, "fecha": "Mon, 05 Oct 2026 00:00:00 GMT", "estado": "bien"}]}`. `dias` menor que 1 o que no es un número entero responde `400`.

## Imágenes

- **DiceBear** (`api.dicebear.com/10.x/gaze/svg`, estilo *gaze*, versión 10.x; valores de forma y ojos verificados el 7 oct 2026 en `@dicebear/styles` 10.6.0). Se cargan con un `<img src="...">` normal. **Necesitan internet**: si el día de la presentación no hay conexión, no se van a ver (se pueden descargar los SVG y servirlos localmente). La semilla de cada avatar es fija (`lumea-sol`, ...): nunca se manda el correo ni otro dato del usuario a DiceBear.
- **Capas de Figma**: las sirve el propio backend desde `Backend/static/avatar/` (`http://127.0.0.1:5002/static/avatar/<archivo>`). No necesitan internet.
