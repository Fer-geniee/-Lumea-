# Contrato de la API de gamificación

Para quien construya el frontend de la gamificación. Todos los ejemplos son **respuestas reales** del backend (26 y 27 sep 2026), no inventadas.

- Base: `http://127.0.0.1:5002` (igual que el resto de la API; ver `api.js` del frontend).
- Identificación del usuario: por `email`, como el resto de la API. **Cuando esté listo el login, esto puede cambiar** (se ajusta en un solo lugar del backend: `_usuario_id_desde_email` en `gamificacion.py`).
- Los números (XP por acción, topes, meta, niveles, pérdida por inactividad, avatares, ropa y accesorios) viven en `gamificacion_config.py` y son **provisionales**. No los copies en el frontend: `GET /progreso` los devuelve en `reglas`.

## Reglas (para diseñar las pantallas)

- Se gana XP por **registrar**: una comida (guardada por `/predecir` o por `/confirmar-alimento`) o el estado de ánimo del día.
- El XP **no depende** de qué se comió ni de qué ánimo se reportó. Nunca mostrar mensajes que premien comer "bien", calorías, peso ni cuerpo, ni que premien sentirse bien.
- Cada acción tiene un **tope diario**. Pasado el tope, la acción se guarda igual, pero da 0 XP (`tope_diario_alcanzado: true`).
- **Racha:** días seguidos con al menos una actividad. Si un día no hay actividad, se reinicia.
- **Meta diaria:** llegar a `meta` XP en el día.
- **Pérdida por inactividad (nuevo, 27 sep):** cada día completo sin ninguna actividad resta `xp_perdido_por_dia_inactivo` XP (hoy 5), con un tope de `tope_perdida_por_periodo` (hoy 20) por cada ausencia. El XP nunca baja de 0. **El nivel nunca baja** y **nada de lo desbloqueado se vuelve a bloquear**: ambos dependen del nivel máximo alcanzado. Con `xp_perdido_por_dia_inactivo = 0` la pérdida está apagada.
- **Sin rankings** ni comparaciones con otros usuarios (lo promete `guialumea.html`).
- **Sin insignias ni logros** por ahora (decisión del equipo, 27 sep).

### Cómo funciona la pérdida (para explicarla en la sustentación)

No hay un servidor encendido todo el tiempo, así que nadie "resta XP a medianoche". La pérdida se calcula **cuando el usuario vuelve**: en `GET /progreso` o al registrar algo. Se cuentan los días completos entre la última actividad y hoy (hoy no cuenta: todavía puede registrar). El backend guarda cuánto lleva descontado en esa ausencia, así que preguntar dos veces el mismo día no descuenta dos veces.

Ejemplo con los valores de hoy: registra el lunes y vuelve el jueves. Martes y miércoles fueron días inactivos, así que pierde 10 XP. Si vuelve a abrir la app el jueves, no pierde nada más. Si no registra nada y abre el viernes, pierde 5 más (15 en total). Nunca pasa de 20 en la misma ausencia.

## Qué ruta para qué

| Ruta | Para |
|---|---|
| `GET /progreso` | Dashboard: XP, nivel, racha, meta del día, aviso de regreso, cara DiceBear con el ánimo de hoy. |
| `GET /avatar` (singular) | Pantalla "personalizar avatar" (capas de Figma): base, ropa y accesorio. |
| `POST /avatar/base`, `POST /avatar/equipar`, `POST /avatar/quitar` | Cambiar el avatar por capas. |
| `GET /avatares` (plural) y `POST /avatar` | Avatares DiceBear: la cara del check-in de ánimo, y el avatar de **respaldo** si el diseño de Figma no llega a tiempo. |

Ojo: `GET /avatar` (capas) y `POST /avatar` (DiceBear) comparten la dirección pero son cosas distintas.

## `GET /progreso?email=<correo>`

Estado completo del usuario. Un usuario sin actividad todavía recibe ceros (no es error). Aquí se descuenta la pérdida por inactividad pendiente.

Ejemplo real de alguien que vuelve después de 3 días sin actividad (tenía 35 XP y nivel 2). Para sacar este ejemplo se corrió en la base de datos la fecha de la última actividad 4 días atrás:

```json
{
  "success": true,
  "progreso": {
    "xp_total": 20,
    "nivel": 2,
    "xp_inicio_nivel": 30,
    "xp_siguiente_nivel": 80,
    "xp_faltante_siguiente_nivel": 60,
    "racha_actual": 0,
    "racha_maxima": 1,
    "ultima_fecha_actividad": "2026-09-23",
    "xp_perdido_desde_ultima_visita": 15,
    "mensaje_regreso": "¡Te extrañamos! Tu nivel y todo lo que desbloqueaste siguen siendo tuyos. Cuando quieras, registra algo hoy y vuelve a sumar XP.",
    "meta_diaria": { "xp_hoy": 35, "meta": 15, "cumplida": true },
    "avatar": {
      "id": "sol",
      "nombre": "Sol",
      "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural",
      "estado_animo_hoy": "bien",
      "url_con_animo": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=smile&eyes=default&eyebrows=defaultNatural",
      "urls_por_estado": {
        "muy_mal": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=sad&eyes=default&eyebrows=sadConcerned",
        "mal": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=concerned&eyes=default&eyebrows=sadConcernedNatural",
        "neutral": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=serious&eyes=default&eyebrows=defaultNatural",
        "bien": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=smile&eyes=default&eyebrows=defaultNatural",
        "muy_bien": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=smile&eyes=happy&eyebrows=raisedExcitedNatural"
      }
    },
    "reglas": {
      "acciones": {
        "comida_registrada": { "xp": 10, "maximo_por_dia": 5 },
        "estado_animo": { "xp": 5, "maximo_por_dia": 1 }
      },
      "meta_diaria_xp": 15,
      "niveles": [0, 30, 80, 150, 250, 400, 600, 850, 1150, 1500],
      "xp_perdido_por_dia_inactivo": 5,
      "tope_perdida_por_periodo": 20
    }
  }
}
```

(`meta_diaria.xp_hoy` dice 35 porque en la prueba se registró ese mismo día; con una ausencia de verdad sería 0.)

La segunda llamada del mismo día responde lo mismo pero con `"xp_perdido_desde_ultima_visita": 0` y `"mensaje_regreso": null`: **el aviso se da una sola vez**.

Notas:
- `nivel` es el **nivel máximo alcanzado**: nunca baja. Después de perder XP, `xp_total` puede quedar **por debajo** de `xp_inicio_nivel` (en el ejemplo, 20 con el nivel 2 empezando en 30). Para la barra de progreso usa `max(0, xp_total - xp_inicio_nivel) / (xp_siguiente_nivel - xp_inicio_nivel)`, o muestra "te faltan `xp_faltante_siguiente_nivel` XP para el nivel 3".
- `xp_siguiente_nivel` y `xp_faltante_siguiente_nivel` son `null` en el último nivel.
- `xp_perdido_desde_ultima_visita` también incluye lo que se descontó si el usuario registró algo antes de abrir `/progreso`.
- Muestra `mensaje_regreso` tal cual, con tono amable. Si quieres mostrar el número, que sea discreto; nunca como regaño.
- `racha_actual` ya viene "vigente": si la última actividad fue antes de ayer, llega en 0.
- `avatar` es el avatar **DiceBear**. `avatar.url` es la cara neutra. `url_con_animo` usa el último estado de ánimo de **hoy** (neutra si no hay; en ese caso `estado_animo_hoy` es `null`). `urls_por_estado` sirve para dibujar el selector de ánimo con la cara del propio avatar.

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
    "id": "sol", "nombre": "Sol",
    "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural"
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
  "success": true,
  "xp_total": 35,
  "nivel_maximo": 2,
  "avatar_actual": "sol",
  "avatares": [
    { "id": "sol",  "nombre": "Sol",  "nivel_requerido": 1, "desbloqueado": true,  "niveles_faltantes": 0, "seleccionado": true,
      "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural" },
    { "id": "luna", "nombre": "Luna", "nivel_requerido": 1, "desbloqueado": true,  "niveles_faltantes": 0, "seleccionado": false,
      "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-luna&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural" },
    { "id": "rio",  "nombre": "Río",  "nivel_requerido": 3, "desbloqueado": false, "niveles_faltantes": 1, "seleccionado": false,
      "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-rio&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural" }
  ]
}
```

(Recortado a 3 de los 6 avatares.) Errores: `400` sin `email`, `404` sin perfil.

### `POST /avatar`

Body (JSON):

```json
{ "email": "ana@correo.com", "avatar_id": "luna" }
```

Respuesta `200`:

```json
{
  "success": true,
  "avatar": {
    "id": "luna",
    "nombre": "Luna",
    "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-luna&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural"
  }
}
```

| Código | Cuándo | Cuerpo |
|---|---|---|
| `400` | Falta `avatar_id`, falta `email`, o el avatar no existe | `{"error": "..."}` |
| `403` | El avatar existe pero está bloqueado (**cambió**: antes decía `xp_faltante`) | `{"error": "El avatar \"rio\" todavía está bloqueado.", "nivel_maximo": 1, "nivel_requerido": 3, "niveles_faltantes": 2}` |
| `404` | El correo no tiene perfil | `{"error": "No existe un perfil con ese correo."}` |

## Cambios en endpoints que ya existían

`POST /predecir` (cuando guarda), `POST /confirmar-alimento` y `POST /estado-animo` traen la clave `gamificacion`. Es `null` cuando no aplica (predicción sin `email`, o si el registro no se guardó). Si no es `null` (respuesta real de `/confirmar-alimento`):

```json
{
  "accion": "comida_registrada",
  "xp_ganado": 10,
  "tope_diario_alcanzado": false,
  "xp_total": 30,
  "nivel": 2,
  "subio_de_nivel": true,
  "racha_actual": 1,
  "meta_diaria": { "xp_hoy": 30, "meta": 15, "cumplida": true, "recien_cumplida": false }
}
```

- `subio_de_nivel` y `meta_diaria.recien_cumplida` son `true` solo en la acción que lo provocó: úsalos para mostrar una celebración una sola vez. Al subir de nivel puede haber ropa o accesorios nuevos: `GET /avatar` los muestra desbloqueados.
- `nivel` es el nivel máximo (nunca baja).
- Si el usuario vuelve después de días inactivos y registra algo **antes** de abrir `/progreso`, `xp_total` ya viene con la pérdida descontada; el aviso llega en la siguiente llamada a `GET /progreso`.
- En `POST /estado-animo` viene además `avatar_url`: la cara DiceBear con la expresión del ánimo que se acaba de registrar.

## Eliminado

`GET /puntos-racha` (la versión mínima anterior) ya no existe: responde `404`. El frontend nunca lo usó.

## Imágenes

- **DiceBear** (`api.dicebear.com`, estilo *avataaars* de Pablo Stanley: diseño "free for personal and commercial use"; código MIT). Se cargan con un `<img src="...">` normal. **Necesitan internet**: si el día de la presentación no hay conexión, no se van a ver (se pueden descargar los SVG y servirlos localmente). La semilla de cada avatar es fija (`lumea-sol`, ...): nunca se manda el correo ni otro dato del usuario a DiceBear.
- **Capas de Figma**: las sirve el propio backend desde `Backend/static/avatar/` (`http://127.0.0.1:5002/static/avatar/<archivo>`). No necesitan internet.
