"""
gamificacion_config.py -- TODAS las reglas numéricas de la gamificación.

Es el único archivo que hay que tocar para ajustar la mecánica (por
ejemplo, cuando llegue la guía de componentes del profesor). Los
endpoints y la lógica (gamificacion.py) leen de aquí; ningún número está
escrito en ellos.

Los valores actuales son PROVISIONALES (acordados el 26 sep 2026 para
tener algo funcionando), no el diseño final. La pérdida por inactividad y
el avatar por capas se agregaron el 27 sep 2026 (reunión del equipo).
Por decisión del equipo NO hay insignias ni logros por ahora.
"Puntos v2" (27 sep 2026, diseño decidido por el equipo): bonus por
elección nutritiva, misiones diarias fijas y penalización por
ultraprocesados que existe pero vale 0.

Reglas de contenido que cualquier cambio debe respetar (ver
DEFENSA_TECNICA_LUMEA.md, sección 5 -- población adolescente):
- La mayor parte del XP premia la constancia en el hábito de registrar.
  Lo único que depende de QUÉ se comió es un bonus pequeño y POSITIVO
  (elección nutritiva, con tope diario). Nunca se resta XP por lo que se
  comió: XP_PENALIZACION_ULTRAPROCESADO vale 0 (ver su comentario). Nada
  depende de peso, calorías "quemadas" ni del cuerpo.
- Registrar el estado de ánimo da el mismo XP sea cual sea el ánimo:
  premiar "estar bien" empujaría a reportar un ánimo falso.
- Hay tope diario por acción: registrar 20 comidas no da más que
  registrar las del día. Premia constancia, no volumen.
- Sin rankings ni comparaciones entre usuarios (el frontend promete
  "sin comparaciones con otros", guialumea.html).
- Perder XP nunca le quita a nadie lo que ya logró: el NIVEL no baja y lo
  desbloqueado no se vuelve a bloquear. Los mensajes de regreso son
  amables, nunca un regaño.
"""

# XP que da cada acción y cuántas veces al día cuenta. Pasado el máximo,
# la acción se sigue registrando normalmente, solo que da 0 XP. Para
# agregar una acción nueva basta con agregarla aquí y llamar a
# registrar_actividad(db, usuario_id, "<accion>") desde el endpoint.
ACCIONES = {
    "comida_registrada": {"xp": 10, "maximo_por_dia": 5},
    # Extra que se suma a comida_registrada si el alimento FINAL es una
    # elección nutritiva (ver ELECCION_NUTRITIVA más abajo). No se registra
    # sola: la otorga gamificacion.py al registrar una comida.
    "eleccion_nutritiva": {"xp": 5, "maximo_por_dia": 3},
    "estado_animo": {"xp": 5, "maximo_por_dia": 1},
}

# ===== Elección nutritiva =====
# Un alimento cuenta como elección nutritiva si, al registrarlo:
# - es el alimento FINAL (el reconocido o el confirmado), nunca un código
#   de grupo de confirmación ("sopas", "dulces", "tamal"...);
# - no tiene sellos de advertencia (lista vacía; si no se sabe, no cuenta);
# - no es un producto de paquete (los de GRUPOS_PRODUCTO_DE_PAQUETE).
# Es un bonus pequeño y positivo. No convierte lo demás en "malo".
#
# Grupos de grupos_confusion.py cuyos productos son de paquete
# (ultraprocesados): dulces, papas/chitos y bebidas azucaradas.
GRUPOS_PRODUCTO_DE_PAQUETE = ["dulces", "frituras_empaquetadas", "gaseosas_bebidas_azucaradas"]

# ===== Ultraprocesados: penalización (apagada) y mensaje educativo =====
# XP que se RESTARÍA al registrar un producto de paquete. EXISTE para poder
# discutirlo, pero vale 0 A PROPÓSITO, y con 0 no resta nada:
# - Honestidad de los registros: si registrar una gaseosa quita puntos, la
#   forma fácil de no perderlos es no registrarla. La app deja de reflejar
#   lo que de verdad se come y pierde su sentido.
# - No asociar culpa a la comida en adolescentes: la guía de la Academia
#   Americana de Pediatría para prevenir obesidad y trastornos
#   alimentarios en adolescentes (Golden et al., 2016, Pediatrics
#   138(3):e20161649) recomienda no promover dietas ni hablar de comida o
#   peso en términos de culpa, y enfocarse en hábitos.
# Cambiarlo es una decisión del equipo, no un ajuste técnico.
XP_PENALIZACION_ULTRAPROCESADO = 0

# Lo que se muestra al registrar un producto de paquete: un dato y una
# alternativa para otro día. Nunca un regaño, sin "malo", "evita" ni
# "saludable".
MENSAJES_ULTRAPROCESADO = {
    "gaseosas_bebidas_azucaradas": (
        "Dato: las gaseosas y bebidas azucaradas tienen bastante azúcar añadida. "
        "Si otro día quieres variar, el agua con limón o un jugo de fruta natural también refrescan."
    ),
    "frituras_empaquetadas": (
        "Dato: los paquetes de papas y chitos suelen tener bastante sal y grasa. "
        "Si otro día se te antoja algo crujiente, las palomitas hechas en casa o el maní sin sal son otra opción."
    ),
    "dulces": (
        "Dato: los dulces de paquete tienen bastante azúcar añadida. "
        "Si otro día quieres algo dulce distinto, una fruta como el mango o el banano también lo es."
    ),
}

# ===== Misiones diarias (fijas, una vez al día cada una) =====
# Las condiciones están en gamificacion.py (misiones_nuevas); aquí van el
# nombre que se muestra y el XP. Los ids no se cambian sin cambiar también
# gamificacion.py.
MISIONES_DIARIAS = [
    {"id": "fruta", "nombre": "Registra una fruta", "xp": 10},
    {"id": "tres_comidas", "nombre": "Registra 3 comidas", "xp": 10},
    {"id": "check_in_animo", "nombre": "Haz tu check-in de ánimo", "xp": 10},
]
# Qué alimentos cuentan como fruta para la misión (clases del modelo).
FRUTAS = ["banano", "fresa", "mango", "manzana", "naranja", "pera", "pina", "uva"]
# Cuántas comidas pide la misión "tres_comidas".
COMIDAS_PARA_MISION = 3

# XP diario para "cumplir la meta" (1 comida + estado de ánimo, o 2 comidas).
META_DIARIA_XP = 15

# XP mínimo para estar en cada nivel. La posición en la lista es el nivel:
# NIVELES[0] -> nivel 1, NIVELES[1] -> nivel 2, ... Debe empezar en 0 e ir
# en orden creciente. Si se cambian, el nivel de cada usuario se recalcula
# solo a partir de su XP total.
NIVELES = [0, 30, 80, 150, 250, 400, 600, 850, 1150, 1500]

# ===== Pérdida de XP por inactividad =====
# Un "día inactivo" es un día completo sin NINGUNA actividad registrada
# (ni comida ni estado de ánimo). Hoy nunca cuenta como inactivo: todavía
# se puede registrar algo.
#
# Como no hay servidor encendido todo el tiempo (no hay tareas
# programadas), la pérdida se calcula "perezosamente": cuando el usuario
# vuelve (GET /progreso o al registrar una actividad) se descuentan los
# días que falten. Nunca se descuenta dos veces el mismo día.
#
# - XP_PERDIDO_POR_DIA_INACTIVO: cuánto se pierde por cada día inactivo.
#   Con 0, la pérdida queda desactivada.
# - TOPE_PERDIDA_POR_PERIODO: lo máximo que se pierde en un mismo
#   "período" de inactividad (los días seguidos sin actividad entre una
#   actividad y la siguiente). Quien se va un mes pierde como máximo esto.
#   Al registrar una actividad empieza un período nuevo.
#
# El XP nunca baja de 0. El NIVEL nunca baja (se guarda el nivel máximo
# alcanzado aparte del XP actual) y nada de lo desbloqueado se vuelve a
# bloquear, porque se desbloquea por nivel máximo.
XP_PERDIDO_POR_DIA_INACTIVO = 5
TOPE_PERDIDA_POR_PERIODO = 20

# Lo que ve el usuario al volver si perdió XP. Amable, nunca un regaño, y
# sin mencionar comida, peso ni cuerpo.
MENSAJE_REGRESO = (
    "¡Te extrañamos! Tu nivel y todo lo que desbloqueaste siguen siendo tuyos. "
    "Cuando quieras, registra algo hoy y vuelve a sumar XP."
)

# ===== Avatares DiceBear (la cara que cambia con el estado de ánimo) =====
# Se usan para el check-in de ánimo, y como avatar de respaldo si las
# imágenes de Figma (más abajo) no están listas a tiempo.
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
#
# nivel_requerido se compara con el NIVEL MÁXIMO alcanzado (no con el XP
# actual), así que perder XP por inactividad nunca vuelve a bloquear un
# avatar. Son los mismos umbrales que antes estaban en XP (80 XP = nivel
# 3, 250 = nivel 5, 600 = nivel 7, 1150 = nivel 9).
AVATARES = [
    {"id": "sol", "nombre": "Sol", "semilla": "lumea-sol", "nivel_requerido": 1},
    {"id": "luna", "nombre": "Luna", "semilla": "lumea-luna", "nivel_requerido": 1},
    {"id": "rio", "nombre": "Río", "semilla": "lumea-rio", "nivel_requerido": 3},
    {"id": "montana", "nombre": "Montaña", "semilla": "lumea-montana", "nivel_requerido": 5},
    {"id": "orquidea", "nombre": "Orquídea", "semilla": "lumea-orquidea", "nivel_requerido": 7},
    {"id": "colibri", "nombre": "Colibrí", "semilla": "lumea-colibri", "nivel_requerido": 9},
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

# ===== Avatar por capas (diseño en Figma) -- OPCIONAL =====
# El avatar del perfil se arma apilando imágenes PNG del mismo tamaño y
# con fondo transparente: abajo la BASE, encima la ROPA y encima el
# ACCESORIO. Lo que se desbloquea subiendo de nivel son la ropa y los
# accesorios. Especificación para la diseñadora:
# ESPECIFICACION_AVATARES_FIGMA.md.
#
# Es opcional: mientras las imágenes no existan, las rutas responden igual
# (con los nombres de archivo e "imagen_lista": false) y el frontend
# muestra un marcador. Si el diseño no llega a tiempo, el perfil usa el
# avatar DiceBear de arriba.
#
# Las imágenes van en Backend/static/<CARPETA_IMAGENES_AVATAR>/ y Flask
# las sirve en http://127.0.0.1:5002/static/avatar/<archivo>.
CARPETA_IMAGENES_AVATAR = "avatar"

# Las 2 bases tienen la misma silueta y postura, para que cada prenda y
# accesorio sirva en las dos. Las dos están disponibles desde el inicio.
BASES_AVATAR = [
    {"id": "base_1", "nombre": "Base 1", "archivo": "base_1.png"},
    {"id": "base_2", "nombre": "Base 2", "archivo": "base_2.png"},
]
BASE_POR_DEFECTO = "base_1"

# Tipos de objeto, en el orden en que se apilan encima de la base (el
# último queda arriba). Cada usuario lleva como máximo UN objeto de cada
# tipo, o ninguno.
TIPOS_OBJETO = ["ropa", "accesorio"]

# Propuesta inicial: 3 de ropa y 3 accesorios. nivel_requerido se compara
# con el NIVEL MÁXIMO alcanzado, así que un objeto desbloqueado nunca se
# vuelve a bloquear. Sin nada que resalte el cuerpo (población
# adolescente, ver DEFENSA_TECNICA_LUMEA.md sección 5).
OBJETOS_AVATAR = [
    {"id": "buzo_verde", "tipo": "ropa", "nombre": "Buzo verde", "archivo": "ropa_buzo_verde.png", "nivel_requerido": 1},
    {"id": "camiseta_lumea", "tipo": "ropa", "nombre": "Camiseta Lumea", "archivo": "ropa_camiseta_lumea.png", "nivel_requerido": 3},
    {"id": "ruana", "tipo": "ropa", "nombre": "Ruana", "archivo": "ropa_ruana.png", "nivel_requerido": 6},
    {"id": "gafas", "tipo": "accesorio", "nombre": "Gafas", "archivo": "accesorio_gafas.png", "nivel_requerido": 2},
    {"id": "audifonos", "tipo": "accesorio", "nombre": "Audífonos", "archivo": "accesorio_audifonos.png", "nivel_requerido": 4},
    {"id": "sombrero_vueltiao", "tipo": "accesorio", "nombre": "Sombrero vueltiao", "archivo": "accesorio_sombrero_vueltiao.png", "nivel_requerido": 8},
]
