# Guía del frontend de Lumea (para Sara)

Hola, Sara. Esta guía recorre las pantallas de Lumea una por una, en el orden en
que las usa una persona. Para cada pantalla dice:

- **qué muestra**;
- **qué ruta del backend usa** (y qué función de `api.js` la llama);
- **un ejemplo real de respuesta**: todos salieron del backend encendido el
  27 sep 2026, ninguno es inventado;
- **qué mostrar mientras carga, si hay un error y si no hay datos.**

No necesitas saber cómo funciona el backend por dentro: solo qué le pides y qué
te contesta.

## Antes de empezar

### 1. El backend tiene que estar encendido

El backend es el programa de Isabella que analiza las fotos y guarda los datos.
Se enciende en la carpeta `Backend/` con:

```bash
python3 app.py
```

Queda escuchando en `http://127.0.0.1:5002`. Si no está encendido, todas las
pantallas mostrarán el mensaje de error ("No se pudo conectar"). Eso es normal:
es justo el caso de error que hay que dibujar.

### 2. La dirección del backend está en UN solo archivo: `api.js`

`api.js` tiene la dirección del backend (`API_BASE_URL`) y una función por cada
cosa que se le puede pedir. **Ninguna página escribe la dirección a mano**: todas
cargan `api.js` y usan sus funciones. Así, si el día de la presentación el
backend corre en otro computador, se cambia una sola línea.

```html
<script src="api.js"></script>
<script src="sesion-nav.js"></script>
<script>
  // aquí ya puedes usar obtenerProgreso(), predecirComida(), etc.
</script>
```

Tu `crear-cuenta.html` nueva llama a `http://127.0.0.1:5001/perfil` escrito a
mano. Ese puerto está mal (es **5002**) y además se salta `api.js`. Cámbialo por
`crearOActualizarPerfil(datos)`.

Funciones que trae `api.js`:

| Función | Ruta del backend | Pantalla |
|---|---|---|
| `crearOActualizarPerfil(datos)` | `POST /perfil` | Crear cuenta |
| `buscarPerfilPorCorreo(email)` | `GET /perfil` | Iniciar sesión (por ahora) |
| `iniciarSesion(email, contrasena)` | `POST /login` | Iniciar sesión (cuando exista) |
| `guardarSesion(email)`, `obtenerSesion()`, `cerrarSesion()` | (ninguna: `localStorage`) | Todas |
| `obtenerProgreso(email)` | `GET /progreso` | Dashboard |
| `predecirComida(archivo, email)` | `POST /predecir` | Registrar comida |
| `confirmarAlimento(codigo, email)` | `POST /confirmar-alimento` | Confirmación |
| `registrarEstadoAnimo(email, estado)`, `obtenerEstadosAnimo(email)` | `POST` y `GET /estado-animo` | Check-in de ánimo |
| `obtenerHistorial(email)` | `GET /historial` | Mis registros |
| `obtenerAvatar(email)`, `elegirBaseAvatar(...)`, `equiparObjeto(...)`, `quitarObjeto(...)` | `GET /avatar`, `POST /avatar/base`, `/avatar/equipar`, `/avatar/quitar` | Personalizar avatar |
| `obtenerAvataresDiceBear(email)`, `elegirAvatarDiceBear(...)` | `GET /avatares`, `POST /avatar` | Respaldo del avatar |

Todas devuelven lo mismo: `{ ok, cuerpo }`. `ok` es `true` si todo salió bien, y
`cuerpo` es la respuesta del backend (los ejemplos de abajo).

### 3. El patrón de todas las pantallas: cargando, error, sin datos

Cada pantalla tiene cuatro estados posibles. Casi todo el código sigue este
molde:

```js
async function cargar() {
  mostrar("cargando");                       // 1. spinner mientras llega la respuesta
  try {
    const { ok, cuerpo } = await obtenerProgreso(email);
    if (!ok) {                               // 2. el backend respondió, pero con un error
      mostrarError(cuerpo.error || cuerpo.mensaje);
      return;
    }
    if (/* no hay nada que mostrar */ false) {
      mostrar("vacio");                      // 3. todo bien, pero sin datos todavía
      return;
    }
    pintar(cuerpo);                          // 4. lo normal
  } catch (error) {                          // 5. ni siquiera se pudo conectar
    mostrarError(`No se pudo conectar con el servidor. ¿Está encendido en ${API_BASE_URL}?`);
  }
}
```

- **Cargando:** un spinner de Bootstrap (`<span class="spinner-border spinner-border-sm"></span>`)
  y el botón deshabilitado, para que no lo presionen dos veces.
- **Error:** un `<div class="alert alert-danger">` con el mensaje. Los errores
  del backend siempre traen `error` (o `mensaje` en `/perfil`).
- **Sin datos:** un texto amable que invite a hacer algo ("Todavía no tienes
  comidas registradas. Registra la primera").

### 4. Reglas de contenido (importantes para el jurado)

- **Nunca la palabra "saludable"** (ni "sano", "bueno/malo", "balanceado", ni un
  chulo verde de aprobación sobre una comida). En su lugar van los **sellos de
  advertencia** oficiales (pantalla 4). Una comida sin sellos es "Sin sellos de
  advertencia", no "saludable".
- **Sin juicios ni regaños.** La app no califica lo que alguien comió ni cómo se
  siente. El ánimo da el mismo XP sea cual sea.
- **Sin comparaciones** con otras personas: nada de rankings.
- **Sin peso ni cuerpo** en ninguna pantalla de progreso.

Una sugerencia: `index.html` dice "estimaciones de calorías, proteínas,
carbohidratos y grasas saludables" (línea 129). La app no muestra eso y usa la
palabra "saludables". Vale la pena cambiar ese texto.

### 5. Cómo leer las fechas

El backend manda las fechas así: `"Sun, 27 Sep 2026 00:00:00 GMT"`. Es la
medianoche **en hora de Londres**, y en Colombia son 5 horas menos. Si la
conviertes sin más, sale **el día anterior**. Siempre usa `timeZone: "UTC"`:

```js
new Date(registro.fecha).toLocaleDateString("es-CO", {
  day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
}); // "27 de septiembre de 2026"
```

---

## Pantalla 1: Iniciar sesión

**Qué muestra:** correo, contraseña y el botón "Entrar". Si todo sale bien,
guarda la sesión (`guardarSesion(email)`) y lleva al dashboard.

**Ruta:** el login con contraseña (`POST /login`) **todavía no existe**: Isabella
lo está programando con Bcrypt. Por eso hay dos momentos.

**Hoy:** se busca el perfil por correo, sin revisar la contraseña:
`buscarPerfilPorCorreo(email)` → `GET /perfil?email=...`

Respuesta real si el correo existe (`200`):

```json
{
  "success": true,
  "perfil": {
    "id": 26,
    "nombre": "Ana",
    "email": "demo.guia@lumea.test",
    "edad": 15,
    "genero": "femenino",
    "altura": 158,
    "peso": 52.0,
    "objetivo": "comer_balanceado"
  }
}
```

Respuesta real si no existe (`404`):

```json
{ "success": false, "mensaje": "No hay perfil guardado con ese correo." }
```

**Cuando Isabella termine `/login`:** se cambia a `iniciarSesion(email, contrasena)`.
No hay ejemplo real todavía, pero ya se sabe cómo va a responder, porque sus
pruebas (`Backend/test_login.py`) lo exigen:

- `200` si el correo y la contraseña son correctos, con los datos del perfil
  (nunca la contraseña).
- `401` si la contraseña está mal **o** si el correo no existe, **con el mismo
  mensaje en los dos casos**. En pantalla: "Correo o contraseña incorrectos".
  Nunca digas "ese correo no existe": así nadie puede averiguar quién usa Lumea.
- `400` si falta el correo o la contraseña.

| Estado | Qué mostrar |
|---|---|
| Cargando | Botón deshabilitado con spinner: "Entrando..." |
| Error | `404` hoy (`401` con `/login`): "Correo o contraseña incorrectos". Sin conexión: el mensaje de conexión. |
| Sin datos | No aplica. |

---

## Pantalla 2: Dashboard (inicio de la persona)

**Qué muestra:** saludo, **nivel**, barra de XP hacia el siguiente nivel,
**racha** (días seguidos), **meta del día** y el **avatar**. Si la persona
volvió después de varios días, un aviso amable una sola vez.

**Ruta:** `obtenerProgreso(email)` → `GET /progreso?email=...`

Respuesta real de alguien que vuelve después de 3 días sin registrar nada
(recortada; completa en `CONTRATO_GAMIFICACION.md`):

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
      "url_con_animo": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=smile&eyes=default&eyebrows=defaultNatural"
    }
  }
}
```

Cómo usar cada dato:

- **Nivel:** `nivel`. **Nunca baja**, aunque se pierda XP.
- **Barra de XP:** el XP puede quedar por debajo del inicio del nivel (aquí 20,
  con el nivel 2 empezando en 30), así que no bajes de 0:
  ```js
  const p = cuerpo.progreso;
  const porcentaje = p.xp_siguiente_nivel === null ? 100
    : Math.max(0, p.xp_total - p.xp_inicio_nivel) / (p.xp_siguiente_nivel - p.xp_inicio_nivel) * 100;
  // texto: `Te faltan ${p.xp_faltante_siguiente_nivel} XP para el nivel ${p.nivel + 1}`
  ```
  (`xp_siguiente_nivel` es `null` en el último nivel: ahí la barra va llena.)
- **Racha:** `racha_actual` días. Si es 0: "Registra algo hoy para empezar una
  racha" (sin reproches).
- **Meta del día:** `meta_diaria.xp_hoy` de `meta_diaria.meta`.
  Si `cumplida`, un mensaje de felicitación.
- **Aviso de regreso:** si `mensaje_regreso` no es `null`, muéstralo arriba, en
  un recuadro amable (por ejemplo `alert alert-success`), con el botón para
  cerrarlo. Llega **una sola vez**: la siguiente vez ya viene `null`. Si
  muestras el número (`xp_perdido_desde_ultima_visita`), que sea pequeño.
  Nunca como regaño.
- **Avatar:** si el avatar de Figma está listo, las capas (pantalla 8). Si no,
  la cara DiceBear con el ánimo de hoy: `<img src="${p.avatar.url_con_animo}" alt="Tu avatar">`.
  Para saber si Figma está listo, mira `imagenes_listas` en `GET /avatar`.

| Estado | Qué mostrar |
|---|---|
| Cargando | Spinner en lugar de las tarjetas. |
| Error | `404` "No existe un perfil con ese correo" → vuelve a iniciar sesión. Sin conexión: el mensaje de conexión. |
| Sin datos | Una cuenta nueva responde con todo en 0 (`xp_total: 0`, `racha_actual: 0`, `ultima_fecha_actividad: null`). No es un error: "¡Bienvenida! Registra tu primera comida para empezar". |

---

## Pantalla 3: Registrar comida

**Qué muestra:** un botón para tomar o elegir una foto, la vista previa de la
foto y el botón "Analizar". (Ya existe: `registrar-comida.html`.)

**Ruta:** `predecirComida(archivo, email)` → `POST /predecir`. Manda la foto como
formulario (`multipart/form-data`) con el campo `file`, y el correo en `email`.
Con el correo, la comida queda guardada en el historial de esa persona y le da
XP.

```html
<input type="file" id="inputFoto" accept="image/*" capture="environment">
```

`capture="environment"` abre directamente la cámara trasera en el celular.

Si no se manda la foto, la respuesta real es `400`:

```json
{ "error": "No se encontró el campo de imagen en la petición." }
```

| Estado | Qué mostrar |
|---|---|
| Cargando | El análisis tarda unos segundos. Botón deshabilitado: "Analizando..." con spinner. |
| Error | `400`: "Elige una foto primero". `500`: "No pudimos analizar esa foto, intenta con otra". Sin conexión: el mensaje de conexión. |
| Sin datos | Antes de elegir la foto, el botón "Analizar" deshabilitado. |

La respuesta puede ser de tres tipos: se reconoció (pantalla 4), hay que
confirmar entre parecidos, o la certeza fue baja (pantalla 5).

---

## Pantalla 4: Resultado del análisis

**Cuándo:** `POST /predecir` respondió `"success": true`. La comida ya quedó
guardada.

**Qué muestra:** el nombre del alimento, la certeza de la IA, los **sellos de
advertencia**, el dato curioso y, si hubo, el XP ganado.

Respuesta real (foto `prueba.jpeg`):

```json
{
  "success": true,
  "alimento": "Arepa paisa (de maíz precocido, con sal)",
  "alimento_codigo": "arepa",
  "certeza": 99.01,
  "sellos_advertencia": [],
  "dato_curioso": "La arepa es tan antigua que ya la comían los pueblos indígenas de la región andina y el Caribe antes de la llegada de los españoles, mucho antes de que existiera el maíz precocido en bolsa.",
  "guardado_baseDatos": true,
  "mensaje": "Predicción realizada y guardada en la base de datos.",
  "gamificacion": {
    "accion": "comida_registrada",
    "xp_ganado": 10,
    "tope_diario_alcanzado": false,
    "xp_total": 10,
    "nivel": 1,
    "subio_de_nivel": false,
    "racha_actual": 1,
    "meta_diaria": { "xp_hoy": 10, "meta": 15, "cumplida": false, "recien_cumplida": false }
  }
}
```

(Recortada: también trae `alimento_app` y `modelo_usado`, que no hace falta
mostrar.)

### Los sellos: en vez de "saludable"

`sellos_advertencia` puede venir de tres formas:

| Valor | Qué mostrar |
|---|---|
| `["sodio", "azucares", "grasas_saturadas"]` | Un octágono negro por sello, con el texto oficial (tabla de abajo). |
| `[]` | "Sin sellos de advertencia". **Nunca** "saludable". |
| `null` | No se sabe: no muestres nada. |

| Código | Texto del sello |
|---|---|
| `sodio` | EXCESO EN SODIO |
| `azucares` | EXCESO EN AZÚCARES |
| `grasas_saturadas` | EXCESO EN GRASAS SATURADAS |
| `grasas_trans` | EXCESO EN GRASAS TRANS |
| `edulcorantes` | CONTIENE EDULCORANTES |

`registrar-comida.html` ya los dibuja así (con CSS: un cuadrado negro recortado
en forma de octágono):

```css
.sello {
  width: 88px; height: 88px;
  display: flex; align-items: center; justify-content: center; text-align: center;
  padding: 0.5rem; background: #000; color: #fff;
  font-size: 0.6rem; font-weight: 700; line-height: 1.15;
  clip-path: polygon(30% 0, 70% 0, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0 70%, 0 30%);
}
```

Los sellos son información, no un regaño: sin rojo, sin "¡cuidado!".

### El XP ganado

Si `gamificacion` no es `null`:

- "+`xp_ganado` XP". Si `tope_diario_alcanzado` es `true`, no muestres "+0 XP":
  basta con "Guardado en tu historial".
- Si `subio_de_nivel` es `true`: celebración ("¡Subiste al nivel 2!"). Puede
  haber ropa o accesorios nuevos para el avatar: un botón a "Personalizar
  avatar".
- Si `meta_diaria.recien_cumplida` es `true`: "¡Cumpliste la meta de hoy!".

Estos dos avisos vienen en `true` **una sola vez**, en la acción que los provocó.

| Estado | Qué mostrar |
|---|---|
| Cargando | Ya pasó en la pantalla 3. |
| Error | `guardado_baseDatos: false` con `success: true`: "Lo reconocimos, pero no se pudo guardar. Intenta de nuevo". |
| Sin datos | `dato_curioso` puede ser `null`: simplemente no lo muestres. |

---

## Pantalla 5: Confirmación

**Cuándo:** `POST /predecir` respondió `"seleccion_manual": true`. **No se guardó
nada todavía.** Hay dos casos.

### Caso A: comidas que se confunden entre sí (viene `opciones_detalle`)

Algunas comidas se parecen tanto (ajiaco, sancocho y mondongo; tamal y
envueltos; los dulces...) que la app siempre le pregunta a la persona cuál es.

Respuesta real (foto de una sopa):

```json
{
  "success": false,
  "seleccion_manual": true,
  "guardado_baseDatos": false,
  "alimento": "Sopas",
  "alimento_codigo": "sopas",
  "certeza": 99.75,
  "mensaje": "Ajiaco, sancocho y mondongo se ven muy parecidos -- confirma cuál es.",
  "opciones_sugeridas": ["ajiaco", "sancocho", "mondongo"],
  "opciones_detalle": [
    { "codigo": "ajiaco", "nombre": "Ajiaco", "grupo": "sopa", "marca": null },
    { "codigo": "sancocho", "nombre": "Sancocho", "grupo": "sopa", "marca": null },
    { "codigo": "mondongo", "nombre": "Mondongo", "grupo": "sopa", "marca": null }
  ]
}
```

**Qué muestra:** el `mensaje` como título y **un botón por opción**, con el
`nombre` de `opciones_detalle` (no el código). **Agrupa los botones por `grupo`**:
en el grupo del tamal, por ejemplo, salen los subtítulos "tamal", "envuelto" y
"otro", cada uno con sus botones; en los paquetes de frituras, "papas",
"plátano", "maíz"...; y en las bebidas, "gaseosa", "jugo", "té frío"...
Si todas las opciones son del mismo grupo (como las sopas), no hace falta
subtítulo. Así lo hace `registrar-comida.html`:

```js
const grupos = {};
cuerpo.opciones_detalle.forEach((opcion) => {
  if (!grupos[opcion.grupo]) grupos[opcion.grupo] = [];
  grupos[opcion.grupo].push(opcion);
});
// un subtítulo por grupo (si hay más de uno) y sus botones debajo
```

Al tocar un botón: `confirmarAlimento(opcion.codigo, email)` →
`POST /confirmar-alimento` con `{"alimento_codigo": "...", "email": "..."}`.

Respuesta real (confirmando un Chocoramo):

```json
{
  "success": true,
  "alimento": "Chocoramo (ponqué cubierto de chocolate)",
  "alimento_codigo": "chororamo",
  "certeza": 100.0,
  "sellos_advertencia": ["sodio", "azucares", "grasas_saturadas"],
  "dato_curioso": null,
  "guardado_baseDatos": true,
  "mensaje": "Confirmado manualmente y guardado en tu historial.",
  "gamificacion": {
    "accion": "comida_registrada",
    "xp_ganado": 10,
    "tope_diario_alcanzado": false,
    "xp_total": 30,
    "nivel": 2,
    "subio_de_nivel": true,
    "racha_actual": 1,
    "meta_diaria": { "xp_hoy": 30, "meta": 15, "cumplida": true, "recien_cumplida": false }
  }
}
```

Tiene la misma forma que la pantalla 4: muéstralo con el mismo código (sellos,
XP, celebración). Aquí `subio_de_nivel` es `true`: ¡celebración!

### Caso B: la certeza fue baja (sin `opciones_detalle`)

Respuesta real (se le pasó el logo de Lumea, que obviamente no es comida):

```json
{
  "success": false,
  "seleccion_manual": true,
  "guardado_baseDatos": false,
  "alimento": "Sopa de miso",
  "alimento_codigo": "miso_soup",
  "certeza": 66.77,
  "mensaje": "La certeza de la IA es muy baja para guardarse automáticamente.",
  "dato_curioso": "La sopa de miso se hace con una pasta fermentada de soya que puede tardar entre unos meses y varios años en madurar, según el sabor que se busque."
}
```

**Qué muestra:** "No estamos seguros de qué es. ¿Pruebas con otra foto, con más
luz y el plato centrado?", y el botón para elegir otra foto. **No** muestres el
`alimento` como si fuera la respuesta (aquí diría "Sopa de miso" para un logo).

| Estado | Qué mostrar |
|---|---|
| Cargando | Al tocar una opción: "Confirmando..." con spinner, y los botones deshabilitados. |
| Error | `400` si el código no existe (respuesta real: `{"error": "\"sopas\" no es un alimento reconocido en tabla_alimentos."}`). No debería pasar si usas los códigos de `opciones_detalle`. |
| Sin datos | No aplica. |

---

## Pantalla 6: Check-in de ánimo

**Qué muestra:** "¿Cómo te sientes hoy?" y **5 botones**, uno por estado de
ánimo. Cada botón puede llevar la cara del avatar con esa expresión. Después
de elegir, la cara del avatar cambia.

Los 5 estados (siempre estos códigos exactos):

| Código | Texto sugerido |
|---|---|
| `muy_mal` | Muy mal |
| `mal` | Mal |
| `neutral` | Normal |
| `bien` | Bien |
| `muy_bien` | Muy bien |

**Las caras de los botones:** vienen en `GET /progreso`, en
`progreso.avatar.urls_por_estado` (una URL por estado):

```js
const { cuerpo } = await obtenerProgreso(email);
const caras = cuerpo.progreso.avatar.urls_por_estado;
// <img src="${caras.muy_bien}" alt="Muy bien">
```

(Estas caras son de DiceBear y necesitan internet. El avatar de Figma no cambia
de cara: el ánimo siempre usa DiceBear.)

**Ruta para guardar:** `registrarEstadoAnimo(email, estado)` → `POST /estado-animo`
con `{"email": "...", "estado": "bien"}`.

Respuesta real:

```json
{
  "success": true,
  "mensaje": "Estado de ánimo registrado.",
  "gamificacion": {
    "accion": "estado_animo",
    "xp_ganado": 5,
    "tope_diario_alcanzado": false,
    "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=smile&eyes=default&eyebrows=defaultNatural",
    "xp_total": 35,
    "nivel": 2,
    "subio_de_nivel": false,
    "racha_actual": 1,
    "meta_diaria": { "xp_hoy": 35, "meta": 15, "cumplida": true, "recien_cumplida": false }
  }
}
```

`gamificacion.avatar_url` es la cara con el ánimo que se acaba de elegir:
ponla en grande. **Todos los ánimos dan el mismo XP**: no celebres más un "muy
bien" que un "muy mal". Para "mal" o "muy mal", un mensaje de acompañamiento
("Gracias por contarnos. Los días difíciles también cuentan"), nunca "¡ánimo,
sonríe!".

El ánimo cuenta XP una vez al día. Si la persona lo cambia más tarde, se guarda
igual pero da 0 XP (`tope_diario_alcanzado: true`): solo muestra "Actualizado".

**Historial de ánimo:** `obtenerEstadosAnimo(email)` → `GET /estado-animo`.
Respuesta real:

```json
{
  "success": true,
  "cantidad": 1,
  "historial": [
    { "id": 20, "estado": "bien", "fecha": "Sun, 27 Sep 2026 00:00:00 GMT" }
  ]
}
```

| Estado | Qué mostrar |
|---|---|
| Cargando | Los 5 botones deshabilitados con spinner en el elegido. |
| Error | `400` si el estado no es uno de los 5 (respuesta real: `{"error": "Estado no válido. Usa uno de: ['bien', 'mal', 'muy_bien', 'muy_mal', 'neutral']"}`). Sin conexión: el mensaje de conexión. |
| Sin datos | Historial vacío (real: `{"success": true, "cantidad": 0, "historial": []}`): "Todavía no has registrado cómo te sientes". |

---

## Pantalla 7: Mis registros

**Qué muestra:** la lista de comidas registradas, de la más reciente a la más
antigua, con nombre y fecha. (Ya existe: `mis-registros.html`.)

**Ruta:** `obtenerHistorial(email)` → `GET /historial?email=...`

Respuesta real (recortada a 2 de 3 registros):

```json
{
  "success": true,
  "cantidad_registros": 3,
  "historial": [
    {
      "id": 223,
      "usuario_id": 26,
      "alimento_codigo": "chororamo",
      "alimento_detectado": "Chocoramo (ponqué cubierto de chocolate)",
      "certeza_ia": 100.0,
      "calorias_aprox": 399,
      "balanceado": 0,
      "fecha": "Sun, 27 Sep 2026 00:00:00 GMT"
    },
    {
      "id": 222,
      "usuario_id": 26,
      "alimento_codigo": "ajiaco",
      "alimento_detectado": "Ajiaco santafereño",
      "certeza_ia": 100.0,
      "calorias_aprox": 82,
      "balanceado": 1,
      "fecha": "Sun, 27 Sep 2026 00:00:00 GMT"
    }
  ]
}
```

- Muestra `alimento_detectado` y la fecha (con `timeZone: "UTC"`, ver "Cómo leer
  las fechas").
- **No muestres `balanceado`** como etiqueta ("Balanceado", "Ocasional", colores
  verde y gris...): es un juicio sobre la comida.
- Los sellos todavía **no** vienen en `/historial`. Isabella puede agregarlos
  después. Mientras tanto, la lista va sin sellos.

| Estado | Qué mostrar |
|---|---|
| Cargando | "Cargando tu historial..." con spinner. |
| Error | Sin conexión: el mensaje de conexión. |
| Sin datos | Respuesta real: `{"success": true, "cantidad_registros": 0, "historial": []}` → "Todavía no tienes comidas registradas" y un enlace a "Registrar comida". |

---

## Pantalla 8: Perfil → Personalizar avatar

**Qué muestra:** el avatar grande, armado **por capas**. Debajo, las 2 **bases**
para elegir, y la **ropa** y los **accesorios**. Lo desbloqueado se puede tocar
para ponérselo o quitárselo. Lo bloqueado sale con **candado** y el nivel que
necesita.

Las imágenes las está diseñando Laura en Figma (ver
`ESPECIFICACION_AVATARES_FIGMA.md`). **Mientras no existan**, el backend responde
igual, con los nombres de archivo y `"imagen_lista": false`, y la pantalla
muestra un marcador. Así puedes construirla ya.

**Rutas:**

- Ver todo: `obtenerAvatar(email)` → `GET /avatar?email=...`
- Elegir base: `elegirBaseAvatar(email, "base_2")` → `POST /avatar/base`
- Ponerse algo: `equiparObjeto(email, "ropa", "buzo_verde")` → `POST /avatar/equipar`
- Quitárselo: `quitarObjeto(email, "ropa")` → `POST /avatar/quitar`

Las tres de cambiar responden **lo mismo que `GET /avatar`**, ya con el cambio:
redibuja la pantalla con esa respuesta, sin volver a pedir nada.

Respuesta real de `GET /avatar` (nivel 2, sin imágenes todavía; recortada a
un objeto de cada tipo, completa en `CONTRATO_GAMIFICACION.md`):

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
        "url": "http://127.0.0.1:5002/static/avatar/ropa_buzo_verde.png" }
    ],
    "accesorio": [
      { "id": "audifonos", "tipo": "accesorio", "nombre": "Audífonos", "archivo": "accesorio_audifonos.png", "imagen_lista": false,
        "nivel_requerido": 4, "desbloqueado": false, "niveles_faltantes": 2, "puesto": false,
        "url": "http://127.0.0.1:5002/static/avatar/accesorio_audifonos.png" }
    ]
  },
  "respaldo_dicebear": {
    "id": "sol", "nombre": "Sol",
    "url": "https://api.dicebear.com/9.x/avataaars/svg?seed=lumea-sol&facialHairProbability=0&mouth=default&eyes=default&eyebrows=defaultNatural"
  }
}
```

### Cómo se apilan las capas (CSS)

Todas las imágenes miden lo mismo y tienen fondo transparente. El truco es
ponerlas **una encima de otra en la misma caja**: la caja con
`position: relative` y cada imagen con `position: absolute` ocupando toda la
caja. La que se agrega después queda encima.

```html
<div id="avatar" class="avatar-capas"></div>
```

```css
.avatar-capas {
  position: relative;          /* las capas se ubican respecto a esta caja */
  width: 256px;
  height: 256px;
}
.avatar-capas img,
.avatar-capas .marcador {
  position: absolute;          /* todas en la misma esquina... */
  inset: 0;                    /* ...ocupando toda la caja */
  width: 100%;
  height: 100%;
}
.avatar-capas .marcador {      /* lo que se ve mientras no hay imagen */
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1rem;
  border: 2px dashed var(--lumea-accent-border);
  border-radius: 1rem;
  background: var(--lumea-accent-soft);
  color: var(--lumea-text-muted);
  font-size: 0.85rem;
}
.objeto.bloqueado { opacity: 0.55; }
```

```js
// capas ya viene en orden: la primera (la base) va abajo.
function dibujarAvatar(contenedor, capas) {
  contenedor.innerHTML = "";
  const faltan = capas.filter((capa) => !capa.imagen_lista).map((capa) => capa.archivo);
  if (faltan.length > 0) {
    const marcador = document.createElement("div");
    marcador.className = "marcador";
    marcador.textContent = "Imagen en camino: " + faltan.join(", ");
    contenedor.appendChild(marcador);            // queda abajo de todo
  }
  capas.filter((capa) => capa.imagen_lista).forEach((capa) => {
    const img = document.createElement("img");
    img.src = capa.url;
    img.alt = "";                                // decorativa: el nombre va en texto aparte
    contenedor.appendChild(img);                 // cada una queda encima de la anterior
  });
}
```

### Candado y nivel que falta

```js
function dibujarObjetos(contenedor, objetos) {
  contenedor.innerHTML = "";
  objetos.forEach((objeto) => {
    const boton = document.createElement("button");
    boton.className = "btn btn-sm rounded-pill objeto " +
      (objeto.puesto ? "btn-lumea" : "btn-lumea-outline") +
      (objeto.desbloqueado ? "" : " bloqueado");
    if (objeto.desbloqueado) {
      boton.textContent = objeto.nombre;
      boton.addEventListener("click", () => cambiar(objeto.puesto
        ? quitarObjeto(email, objeto.tipo)                  // si ya lo tiene puesto, se lo quita
        : equiparObjeto(email, objeto.tipo, objeto.id)));   // si no, se lo pone
    } else {
      boton.disabled = true;
      boton.innerHTML = `<i class="bi bi-lock-fill"></i> ${objeto.nombre} · Nivel ${objeto.nivel_requerido}`;
      boton.title = `Te faltan ${objeto.niveles_faltantes} nivel(es)`;
    }
    contenedor.appendChild(boton);
  });
}

async function cambiar(promesa) {
  const { ok, cuerpo } = await promesa;
  if (ok) pintar(cuerpo);              // la respuesta ya trae el avatar actualizado
  else mostrarError(cuerpo.error);
}

function pintar(datos) {
  dibujarAvatar(document.getElementById("avatar"), datos.capas);
  dibujarObjetos(document.getElementById("listaRopa"), datos.objetos.ropa);
  dibujarObjetos(document.getElementById("listaAccesorios"), datos.objetos.accesorio);
  // y las bases: un botón por datos.bases, marcado si "seleccionada"
}
```

Este código se probó en el navegador contra el backend, con imágenes de prueba:
base, buzo y gafas quedan bien apilados, y lo bloqueado sale con candado.

Si se intenta poner algo bloqueado, el backend responde `403` (respuesta real):

```json
{ "error": "El objeto \"audifonos\" todavía está bloqueado.", "nivel_maximo": 1, "nivel_requerido": 4, "niveles_faltantes": 3 }
```

Con los botones bloqueados deshabilitados no debería pasar, pero si pasa,
muestra el mensaje.

**Lo desbloqueado no se vuelve a bloquear:** se desbloquea por el **nivel
máximo**, que nunca baja. Aunque alguien pierda XP por no entrar, conserva todo.

### Si el diseño de Figma no llega a tiempo

- Mientras `imagenes_listas` sea `false`, en el **dashboard** muestra la cara de
  DiceBear (`respaldo_dicebear.url`, o `progreso.avatar.url_con_animo`). En
  **esta pantalla** deja los marcadores para poder probarla.
- Si el día de la presentación todavía no están las imágenes, se esconde
  "Personalizar avatar" y se usa el selector DiceBear: `obtenerAvataresDiceBear(email)`
  (`GET /avatares`: 6 caras, cada una con `desbloqueado`, `nivel_requerido` y
  `niveles_faltantes`) y `elegirAvatarDiceBear(email, id)` (`POST /avatar`).
  Mismo candado, misma lógica.

| Estado | Qué mostrar |
|---|---|
| Cargando | Spinner en la caja del avatar; al tocar un objeto, deshabilitar los botones hasta que responda. |
| Error | `403` (bloqueado) y `400` (no existe): el mensaje de `error`. `404`: volver a iniciar sesión. Sin conexión: el mensaje de conexión. |
| Sin datos | Cuenta nueva: base 1 y nada puesto. No es un error: "Elige tu base y estrena tu primera prenda". |

---

## Postman: probar el backend sin el frontend

Postman es un programa para hacerle peticiones al backend "a mano" y ver qué
responde, sin escribir código. Sirve para entender cada ruta antes de
conectarla.

1. Descarga Postman (gratis) de postman.com e instálalo. No hace falta crear
   una cuenta para usarlo localmente.
2. Clic en **Import** (arriba a la izquierda) y elige el archivo
   **`Backend/Lumea.postman_collection.json`**.
3. A la izquierda aparece la colección **"Lumea API"**, con carpetas numeradas
   (1. Perfil, 2. Predicción y confirmación, ...).
4. Clic en el nombre de la colección → pestaña **Variables**. Hay dos:
   - `base_url`: la dirección del backend (`http://127.0.0.1:5002`).
   - `email`: el correo con el que vas a probar. Cámbialo por uno tuyo de
     prueba y guarda (Ctrl+S / Cmd+S).
5. Con el backend encendido, abre **1. Perfil → Crear o actualizar perfil** y
   dale **Send**. Así existe el perfil de prueba.
6. Ya puedes probar cualquier otra: **Send** y abajo aparece la respuesta.
   - Para **Predecir alimento (foto)**, en la pestaña **Body** elige una foto en
     el campo `file`.
   - Cada petición tiene una descripción (clic en el nombre) que explica qué
     hace.

## Si algo falla: qué significa cada código

| Código | En palabras | Qué hacer |
|---|---|---|
| `200` | Todo bien. | Mostrar la respuesta. |
| `400` | La petición está mal hecha: faltó un dato o está mal escrito. | Revisar qué se mandó. El `error` lo dice. |
| `401` | No autorizado: correo o contraseña incorrectos (cuando exista `/login`). | "Correo o contraseña incorrectos". |
| `403` | Prohibido: existe, pero está bloqueado (un objeto del avatar). | Mostrar el candado. |
| `404` | No existe: el perfil o la ruta. | Revisar el correo, o volver a iniciar sesión. |
| `500` | Se rompió algo en el backend. | Mensaje genérico y avisarle a Isabella. |
| "Failed to fetch" | No se pudo conectar: el backend está apagado o la dirección de `api.js` está mal. | Encender el backend o revisar `API_BASE_URL`. |

Más detalle: `CONTRATO_GAMIFICACION.md` (progreso y avatar) y
`CONTRATO_CONFIRMACION.md` (confirmación y sellos), en la misma carpeta.
