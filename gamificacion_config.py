"""
gamificacion_config.py -- TODAS las reglas numéricas de la gamificación.

Es el único archivo que hay que tocar para ajustar la mecánica (por
ejemplo, cuando llegue la guía de componentes del profesor). Los
endpoints y la lógica (gamificacion.py) leen de aquí; ningún número está
escrito en ellos.

Los valores actuales son PROVISIONALES (acordados el 26 sep 2026 para
tener algo funcionando), no el diseño final.

Reglas de contenido que cualquier cambio debe respetar (ver
DEFENSA_TECNICA_LUMEA.md, sección 5 -- población adolescente):
- El XP premia SOLO la constancia en el hábito de registrar. Nunca debe
  depender de QUÉ se comió (saludable o no, calorías), de peso, de
  calorías "quemadas" ni de nada del cuerpo.
- Registrar el estado de ánimo da el mismo XP sea cual sea el ánimo:
  premiar "estar bien" empujaría a reportar un ánimo falso.
- Hay tope diario por acción: registrar 20 comidas no da más que
  registrar las del día. Premia constancia, no volumen.
- Sin rankings ni comparaciones entre usuarios (el frontend promete
  "sin comparaciones con otros", guialumea.html).
"""

# XP que da cada acción y cuántas veces al día cuenta. Pasado el máximo,
# la acción se sigue registrando normalmente, solo que da 0 XP. Para
# agregar una acción nueva basta con agregarla aquí y llamar a
# registrar_actividad(db, usuario_id, "<accion>") desde el endpoint.
ACCIONES = {
    "comida_registrada": {"xp": 10, "maximo_por_dia": 5},
    "estado_animo": {"xp": 5, "maximo_por_dia": 1},
}

# XP diario para "cumplir la meta" (1 comida + estado de ánimo, o 2 comidas).
META_DIARIA_XP = 15

# XP mínimo para estar en cada nivel. La posición en la lista es el nivel:
# NIVELES[0] -> nivel 1, NIVELES[1] -> nivel 2, ... Debe empezar en 0 e ir
# en orden creciente. Si se cambian, el nivel de cada usuario se recalcula
# solo a partir de su XP total.
NIVELES = [0, 30, 80, 150, 250, 400, 600, 850, 1150, 1500]

# ===== Avatares (DiceBear, estilo "avataaars") =====
# Estilo avataaars de Pablo Stanley: "Free for personal and commercial
# use" (diseño) + MIT (código de DiceBear). Solo cara y hombros -- nada
# de cuerpo, a propósito. Versión fija (9.x) porque es la versión cuyos
# valores de parámetros se verificaron contra el esquema oficial
# (@dicebear/avataaars 9.4.2, 26 sep 2026).
DICEBEAR_URL = "https://api.dicebear.com/9.x/avataaars/svg"

# Parámetros que llevan TODOS los avatares. Sin barba: la audiencia son
# estudiantes de colegio.
DICEBEAR_PARAMETROS_FIJOS = {"facialHairProbability": 0}

# Cada avatar se dibuja a partir de una semilla FIJA del catálogo -- nunca
# del correo ni de otro dato del usuario, para no enviarle datos
# personales a un servicio externo.
AVATARES = [
    {"id": "sol", "nombre": "Sol", "semilla": "lumea-sol", "xp_requerido": 0},
    {"id": "luna", "nombre": "Luna", "semilla": "lumea-luna", "xp_requerido": 0},
    {"id": "rio", "nombre": "Río", "semilla": "lumea-rio", "xp_requerido": 80},
    {"id": "montana", "nombre": "Montaña", "semilla": "lumea-montana", "xp_requerido": 250},
    {"id": "orquidea", "nombre": "Orquídea", "semilla": "lumea-orquidea", "xp_requerido": 600},
    {"id": "colibri", "nombre": "Colibrí", "semilla": "lumea-colibri", "xp_requerido": 1150},
]
AVATAR_POR_DEFECTO = "sol"

# Expresión del avatar cuando no hay estado de ánimo registrado hoy.
EXPRESION_NEUTRA = {"mouth": "default", "eyes": "default", "eyebrows": "defaultNatural"}

# Expresión del avatar según el estado de ánimo (mismas claves que
# BaseDatos.ESTADOS_VALIDOS). Valores tomados SOLO de las opciones
# oficiales de DiceBear; se evitan a propósito las exageradas o feas
# (vomit, screamOpen, xDizzy, eyeRoll...). test_gamificacion.py verifica
# que todos los valores existan en DiceBear.
EXPRESION_POR_ESTADO = {
    "muy_mal": {"mouth": "sad", "eyes": "default", "eyebrows": "sadConcerned"},
    "mal": {"mouth": "concerned", "eyes": "default", "eyebrows": "sadConcernedNatural"},
    "neutral": {"mouth": "serious", "eyes": "default", "eyebrows": "defaultNatural"},
    "bien": {"mouth": "smile", "eyes": "default", "eyebrows": "defaultNatural"},
    "muy_bien": {"mouth": "smile", "eyes": "happy", "eyebrows": "raisedExcitedNatural"},
}
