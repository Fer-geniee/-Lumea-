# Contrato de la API de gamificación

Para quien construya el frontend de la gamificación. Todos los ejemplos son **respuestas reales** del backend (26 sep 2026), no inventadas.

- Base: `http://127.0.0.1:5002` (igual que el resto de la API; ver `conexion-api.js`).
- Identificación del usuario: por `email`, como el resto de la API. **Cuando esté listo el login, esto puede cambiar** (se ajusta en un solo lugar del backend: `_usuario_id_desde_email` en `gamificacion.py`).
- Los números (XP por acción, topes, meta, niveles, avatares) viven en `gamificacion_config.py` y son **provisionales**. No los copies en el frontend: `GET /progreso` los devuelve en `reglas`.

## Reglas (para diseñar las pantallas)

- Se gana XP por **registrar**: una comida (guardada por `/predecir` o por `/confirmar-alimento`) o el estado de ánimo del día.
- El XP **no depende** de qué se comió ni de qué ánimo se reportó. Nunca mostrar mensajes que premien comer "bien", calorías, peso ni cuerpo, ni que premien sentirse bien.
- Cada acción tiene un **tope diario**. Pasado el tope, la acción se guarda igual, pero da 0 XP (`tope_diario_alcanzado: true`).
- **Racha:** días seguidos con al menos una actividad. Si un día no hay actividad, se reinicia.
- **Meta diaria:** llegar a `meta` XP en el día.
- **Sin rankings** ni comparaciones con otros usuarios (lo promete `guialumea.html`).

## Endpoints nuevos

### `GET /progreso?email=<correo>`

Estado completo del usuario. Un usuario sin actividad todavía recibe ceros (no es error).

```json
{
  "success": true,
  "progreso": {
    "xp_total": 15,
    "nivel": 1,
    "xp_inicio_nivel": 0,
    "xp_siguiente_nivel": 30,
    "racha_actual": 1,
    "racha_maxima": 1,
    "ultima_fecha_actividad": "2026-09-26",
    "meta_diaria": { "xp_hoy": 15, "meta": 15, "cumplida": true },
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
      "niveles": [0, 30, 80, 150, 250, 400, 600, 850, 1150, 1500]
    }
  }
}
```

Notas:
- `xp_siguiente_nivel` es `null` en el último nivel.
- `racha_actual` ya viene "vigente": si la última actividad fue antes de ayer, llega en 0.
- `avatar.url` es la cara neutra. `url_con_animo` usa el último estado de ánimo de **hoy** (neutra si no hay; en ese caso `estado_animo_hoy` es `null`).
- `urls_por_estado` sirve para dibujar el selector de ánimo con la cara del propio avatar.

Errores: `400` sin `email`, `404` si el correo no tiene perfil.

### `GET /avatares?email=<correo>`

Catálogo completo, con lo que el usuario ya desbloqueó (por XP total).

```json
{
  "success": true,
  "xp_total": 15,
  "avatar_actual": "sol",
  "avatares": [
    { "id": "sol",  "nombre": "Sol",  "xp_requerido": 0,  "desbloqueado": true,  "seleccionado": true,
      "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural" },
    { "id": "luna", "nombre": "Luna", "xp_requerido": 0,  "desbloqueado": true,  "seleccionado": false,
      "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-luna&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural" },
    { "id": "rio",  "nombre": "Río",  "xp_requerido": 80, "desbloqueado": false, "seleccionado": false,
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
| `403` | El avatar existe pero está bloqueado | `{"error": "El avatar \"rio\" todavía está bloqueado.", "xp_requerido": 80, "xp_faltante": 65}` |
| `404` | El correo no tiene perfil | `{"error": "No existe un perfil con ese correo."}` |

## Cambios en endpoints que ya existían

Se agregó **una clave nueva**, `gamificacion`, a las respuestas de `POST /predecir` (cuando guarda), `POST /confirmar-alimento` y `POST /estado-animo`. Nada existente cambió de nombre ni de forma.

`gamificacion` es `null` cuando no aplica (predicción sin `email`, o si el registro no se guardó). Si no es `null`:

```json
{
  "accion": "comida_registrada",
  "xp_ganado": 10,
  "tope_diario_alcanzado": false,
  "xp_total": 15,
  "nivel": 1,
  "subio_de_nivel": false,
  "racha_actual": 1,
  "meta_diaria": { "xp_hoy": 15, "meta": 15, "cumplida": true, "recien_cumplida": true }
}
```

- `subio_de_nivel` y `meta_diaria.recien_cumplida` son `true` solo en la acción que lo provocó: úsalos para mostrar una celebración una sola vez.
- En `POST /estado-animo` viene además `avatar_url`: la cara del avatar con la expresión del ánimo que se acaba de registrar.

## Eliminado

`GET /puntos-racha` (la versión mínima anterior) ya no existe: responde `404`. El frontend nunca lo usó.

## Imágenes de los avatares

Las URLs apuntan a DiceBear (`api.dicebear.com`, estilo *avataaars* de Pablo Stanley: diseño "free for personal and commercial use"; código MIT). Se cargan con un `<img src="...">` normal. Dos cosas a tener en cuenta:
- **Necesitan internet.** Si el día de la presentación no hay conexión, no se van a ver. Si eso es un riesgo, se pueden descargar los SVG y servirlos localmente.
- La semilla de cada avatar es fija (`lumea-sol`, ...). Nunca se manda el correo ni otro dato del usuario a DiceBear.
