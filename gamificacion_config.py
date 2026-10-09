"""
Fundamento: ¿Por qué implementamos gamificación en Lumea?
- La gamificación es una estrategia de diseño que utiliza elementos de juego en contextos 
no lúdicos para motivar y aumentar la participación de los usuarios.
- En Lumea, la gamificación se implementa para fomentar hábitos saludables de alimentación 
y bienestar emocional, incentivando a los usuarios a registrar sus comidas y estados de ánimo de manera constante.
- La gamificación busca crear una experiencia más atractiva y motivadora para los usuarios,
promoviendo la constancia y el compromiso con su bienestar personal.    
Asimismo, se tiene en cuenta la población adolescente, evitando comparaciones entre usuarios y promoviendo un enfoque positivo y de apoyo. 
Y las enseñanzas de San Francisco de Asís, que nos inspiran a cuidar de nosotros mismos y de nuestro entorno con amor y respeto.

gamificacion_config.py -- TODAS las reglas numéricas de la gamificación.


Es el único archivo que hay que tocar para ajustar la mecánica. Los
endpoints y la lógica (gamificacion.py) leen de aquí; ningún número está
escrito en ellos.

Los valores actuales son PROVISIONALES, fueron acordados el 26 sep 2026 para
tener algo funcionando, no el diseño final. La pérdida por inactividad y
el avatar por capas se agregaron el 27 sep 2026 (reunión del equipo).
El 27 sep el equipo decidió NO tener insignias; el 5 oct 2026 Isabella
cambió esa decisión y se agregaron las calcomanías (ver CALCOMANIAS).
"Puntos v2" (27 sep 2026, diseño decidido por el equipo): bonus por
registro, misiones diarias fijas y penalización por
ultraprocesados que existe pero vale 0.

Reglas de contenido que cualquier cambio debe respetar (ver
DEFENSA_TECNICA_LUMEA.md, sección 5 -- población adolescente):
- La mayor parte del XP premia la constancia en el hábito de registrar.
  Nada de lo que se gana depende de QUÉ se comió: el bonus por registro
  es el mismo para cualquier alimento (con tope diario). Nunca se resta XP
  por lo que se comió: XP_PENALIZACION_ULTRAPROCESADO vale 0 (ver su comentario). Nada
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
    # Extra que se suma a comida_registrada al registrar cualquier comida
    # (no depende del alimento ni de sus sellos). No se registra sola: la
    # otorga gamificacion.py al registrar una comida, con su propio tope.
    "bonus_registro": {"xp": 5, "maximo_por_dia": 3},
    "estado_animo": {"xp": 5, "maximo_por_dia": 1},
}

# ===== Productos de paquete =====
# Grupos de grupos_confusion.py cuyos productos son de paquete
# (ultraprocesados): dulces, papas/chitos y bebidas azucaradas. Hoy solo
# sirven para el mensaje educativo (MENSAJES_ULTRAPROCESADO) y para
# XP_PENALIZACION_ULTRAPROCESADO (que vale 0). El bonus por registro NO
# depende de ellos.
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

# ===== Calcomanías (insignias) =====
# Se ganan por lo que la persona HACE, nunca por qué comió, ni por calorías,
# peso, cuerpo o ánimo reportado. No dan XP, no se quitan y no hay ranking.
# Decisión de Isabella, 5 oct 2026 (cambia la del 27 sep "sin insignias").
# Los nombres son provisionales: se pueden renombrar aquí sin tocar nada más.
#
# "umbral" es el número que pide la regla (comidas, días de racha, nivel,
# días de ausencia); las reglas están en gamificacion.py (REGLAS_CALCOMANIAS)
# y los ids no se cambian sin cambiar también ese diccionario.
# "rol" le dice al frontend qué dibujo/color usar.
CALCOMANIAS = [
    {"id": "primera_foto", "nombre": "Primer paso", "descripcion": "Has dado el primer paso en el camino del cuidado.",
     "como_se_gana": "Registra tu primera comida.", "rol": "comida", "umbral": 1},
    {"id": "diez_registros", "nombre": "Diez momentos", "descripcion": "Llevas 10 comidas registradas, cuidando de ti y de tu cuerpo.",
     "como_se_gana": "Registra 10 comidas.", "rol": "comida", "umbral": 10},
    {"id": "tres_al_dia", "nombre": "Un día completo", "descripcion": "Prestas atención a tu alimentación tres veces en el día.",
     "como_se_gana": "Cumple la misión de registrar 3 comidas en un día.", "rol": "mision", "umbral": 1},
    {"id": "fruta", "nombre": "Una fruta para alegrar tu día", "descripcion": "Has comido y registrado una fruta.",
     "como_se_gana": "Cumple la misión de registrar una fruta.", "rol": "mision", "umbral": 1},
    {"id": "como_llegas", "nombre": "Cómo llegas", "descripcion": "Te detuviste un momento a reconocer cómo te sientes.",
     "como_se_gana": "Haz tu primer check-in de ánimo.", "rol": "emocion", "umbral": 1},
    {"id": "ayudaste_ia", "nombre": "Inteligencia humana al rescate", "descripcion": "Confirmaste un plato cuando la IA dudó.",
     "como_se_gana": "Confirma un plato cuando la IA no esté segura.", "rol": "duda", "umbral": 1},
    {"id": "racha_3", "nombre": "Tres días caminando juntos", "descripcion": "Mantuviste tu actividad durante 3 días seguidos.",
     "como_se_gana": "Llega a una racha de 3 días.", "rol": "logro", "umbral": 3},
    {"id": "racha_7", "nombre": "Siete días caminando juntos", "descripcion": "Cuidaste de ti con perseverancia durante una semana completa.",
     "como_se_gana": "Llega a una racha de 7 días.", "rol": "logro", "umbral": 7},
    {"id": "volviste", "nombre": "El camino continua", "descripcion": "Después de una pausa vuelves a cuidar de ti y de tu cuerpo.",
     "como_se_gana": "Vuelve después de 3 o más días sin actividad.", "rol": "logro", "umbral": 3},
    {"id": "nivel_5", "nombre": "Etapa: El Jardín", "descripcion": "Llegaste a una etapa nueva en tu camino de bienestar",
     "como_se_gana": "Llega a la etapa 5.", "rol": "logro", "umbral": 5},
]

# ===== Misiones diarias (fijas, una vez al día cada una) =====
# Las condiciones están en gamificacion.py (misiones_nuevas); aquí van el
# nombre que se muestra y el XP. Los ids no se cambian sin cambiar también
# gamificacion.py.
MISIONES_DIARIAS = [
    {"id": "fruta", "nombre": "Agradece y disfruta una fruta de la creación", "xp": 10},
    {"id": "tres_comidas", "nombre": "Cuida de ti en tus tres comidas", "xp": 10},
    {"id": "check_in_animo", "nombre": "Haz una pausa y escucha cómo te sientes", "xp": 10},
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
XP_PERDIDO_POR_DIA_INACTIVO = 0
TOPE_PERDIDA_POR_PERIODO = 0

# Lo que ve el usuario al volver después de una pausa (ver
# DIAS_PARA_MENSAJE_REGRESO). Amable, nunca un regaño, y sin mencionar
# comida, peso ni cuerpo.
MENSAJE_REGRESO = (
    "🌿 Siempre puedes volver, "
    "tu camino no termina cuando haces una pausa, ni cuando te encuentras con dificultades. "
    "El camino continúa cuando perdonas y sostienes las dificultades en paz. "
    "¡Qué bueno tenerte de vuelta!"
)

# Cuántos días completos sin actividad hacen falta para que, al volver, salga
# el MENSAJE_REGRESO (una sola vez por ausencia). Es el mismo umbral de la
# calcomanía "volviste". Como la pérdida de XP está en 0, el mensaje ya no
# depende de que se haya perdido algo: depende solo de los días de ausencia.
DIAS_PARA_MENSAJE_REGRESO = 3

# ===== Avatares DiceBear (la cara que cambia con el estado de ánimo) =====
# Se usan para el check-in de ánimo, y como avatar de respaldo si las
# imágenes de Figma (más abajo) no están listas a tiempo.
# Compañeros del estilo "gaze" de DiceBear 10.x: cada uno tiene una forma
# y un color, y SUS OJOS muestran el estado de ánimo (EXPRESION_POR_ESTADO,
# más abajo). Versión fija (10.x) porque es la versión cuyos valores se
# verificaron en @dicebear/styles 10.6.0 (7 oct 2026); test_gamificacion.py
# los valida. Las URL son quietas: la animación la agrega el frontend.
DICEBEAR_URL = "https://api.dicebear.com/10.x/gaze/svg"
DICEBEAR_PARAMETROS_FIJOS = {}
EXPRESION_NEUTRA = {"eyesVariant": "dots"}
EXPRESION_POR_ESTADO = {
    "muy_mal": {"eyesVariant": "bars"},
    "mal": {"eyesVariant": "small"},
    "neutral": {"eyesVariant": "dots"},
    "bien": {"eyesVariant": "happy"},
    "muy_bien": {"eyesVariant": "grin"},
}


# Cada avatar se dibuja a partir de una semilla FIJA del catálogo -- nunca
# del correo ni de otro dato del usuario, para no enviarle datos
# personales a un servicio externo.
#
# nivel_requerido se compara con el NIVEL MÁXIMO alcanzado (no con el XP
# actual), así que perder XP por inactividad nunca vuelve a bloquear un
# avatar. Son los mismos umbrales que antes estaban en XP (80 XP = nivel
# 3, 250 = nivel 5, 600 = nivel 7, 1150 = nivel 9).


AVATARES = [
    {"id": "sol", "nombre": "Sol", "semilla": "lumea-sol", "forma": "circle", "color": "F6B73C", "nivel_requerido": 1},
    {"id": "luna", "nombre": "Luna", "semilla": "lumea-luna", "forma": "arch", "color": "C9C3F0", "nivel_requerido": 1},
    {"id": "rio", "nombre": "Río", "semilla": "lumea-rio", "forma": "pill", "color": "52DCD8", "nivel_requerido": 3},
    {"id": "montana", "nombre": "Montaña", "semilla": "lumea-montana", "forma": "triangle", "color": "8FBF7A", "nivel_requerido": 5},
    {"id": "orquidea", "nombre": "Orquídea", "semilla": "lumea-orquidea", "forma": "diamond", "color": "E89BC4", "nivel_requerido": 7},
    {"id": "colibri", "nombre": "Colibrí", "semilla": "lumea-colibri", "forma": "egg", "color": "3FB6A8", "nivel_requerido": 9},
]
AVATAR_POR_DEFECTO = "sol"

# ===== La persona: avatar voxel-art de DiceBear 10.x (9 oct 2026) =====
# Decisión de Isabella: las imágenes por capas de la diseñadora no llegan a
# tiempo, así que la persona es un avatar "voxel-art" de DiceBear (CC0) que el
# FRONTEND dibuja en el navegador (el backend nunca le pide nada a DiceBear).
# El backend solo guarda y valida qué opciones lleva cada persona.
#
# Dos partes:
# - RASGOS: cómo se ve la persona (piel, peinado, ojos...). Son LIBRES: nunca
#   se bloquean, porque la identidad no es un premio.
# - OBJETOS_AVATAR: el armario. Cada etapa (nivel) desbloquea una prenda o un
#   accesorio que CAMBIA a la persona (`parametros` son opciones de DiceBear).
#
# Los valores válidos salen de voxel-art.json (@dicebear/styles 10.6.0, en el
# frontend: vendor/dicebear/estilos/). Los colores van en hexadecimal sin "#".
ESTILO_PERSONA = "voxel-art"

# Tipos de objeto del armario. Cada usuario lleva como máximo UN objeto de
# cada tipo. La ropa nunca queda vacía: sin nada elegido lleva la de
# OBJETOS_POR_DEFECTO. El accesorio sí puede estar vacío.
TIPOS_OBJETO = ["ropa", "accesorio"]

# Una prenda o accesorio por cada una de las 10 etapas de NIVELES (borrador:
# Isabella revisa los nombres). nivel_requerido se compara con el NIVEL MÁXIMO
# alcanzado, así que un objeto desbloqueado nunca se vuelve a bloquear. Las
# gorras y gorros (cap, beanie) no entran: en voxel-art reemplazan el peinado.
# Sin nada que resalte el cuerpo (población adolescente, ver
# DEFENSA_TECNICA_LUMEA.md sección 5).
OBJETOS_AVATAR = [
    {"id": "camiseta_lisa", "tipo": "ropa", "nombre": "Camiseta lisa", "parametros": {"outfitVariant": "plain"}, "nivel_requerido": 1},
    {"id": "camiseta_rayas", "tipo": "ropa", "nombre": "Camiseta de rayas", "parametros": {"outfitVariant": "stripes"}, "nivel_requerido": 2},
    {"id": "gafas_redondas", "tipo": "accesorio", "nombre": "Gafas redondas", "parametros": {"glassesVariant": "round"}, "nivel_requerido": 3},
    {"id": "overol", "tipo": "ropa", "nombre": "Overol de jardín", "parametros": {"outfitVariant": "overalls"}, "nivel_requerido": 4},
    {"id": "camisa_cuadros", "tipo": "ropa", "nombre": "Camisa de cuadros", "parametros": {"outfitVariant": "checker"}, "nivel_requerido": 5},
    {"id": "buzo_capota", "tipo": "ropa", "nombre": "Buzo con capota", "parametros": {"outfitVariant": "hoodie"}, "nivel_requerido": 6},
    {"id": "gafas_sol", "tipo": "accesorio", "nombre": "Gafas de sol", "parametros": {"glassesVariant": "shades"}, "nivel_requerido": 7},
    {"id": "chaqueta", "tipo": "ropa", "nombre": "Chaqueta", "parametros": {"outfitVariant": "jacket"}, "nivel_requerido": 8},
    {"id": "vestido", "tipo": "ropa", "nombre": "Vestido", "parametros": {"outfitVariant": "dress"}, "nivel_requerido": 9},
    {"id": "traje", "tipo": "ropa", "nombre": "Traje", "parametros": {"outfitVariant": "suit"}, "nivel_requerido": 10},
]
OBJETOS_POR_DEFECTO = {"ropa": "camiseta_lisa"}   # puesto al crear la cuenta


# Rasgos libres. Por cada clave: su nombre en español, sus opciones
# ({valor: nombre}) y, solo en mejillas y barba, `ninguno`: el nombre de la
# opción "sin esto", que se guarda como null.
RASGOS = {
    "skinColor": {"nombre": "Tono de piel", "opciones": {
        valor: f"Tono {n}" for n, valor in enumerate(
            ["f5d0b0", "eab890", "dda878", "c99062", "b07347", "95562f", "7d4a26", "6a3d1f"], start=1)}},
    "topVariant": {"nombre": "Peinado", "opciones": {
        "short": "Corto", "spiky": "De puntas", "bowl": "Corte totuma", "sideSwept": "De lado",
        "curly": "Crespo", "mohawk": "Mohicano", "buns": "Moños", "ponytail": "Cola de caballo",
        "bob": "Melena corta", "shoulderLength": "A los hombros", "longStraight": "Largo liso",
        "longWavy": "Largo ondulado", "partedLong": "Largo con partidura", "braids": "Trenzas",
        "twinTails": "Dos colitas", "afro": "Afro", "halfShaved": "Medio rapado"}},
    "hairColor": {"nombre": "Color de pelo", "opciones": {
        "2c222b": "Negro", "3b2f2f": "Café muy oscuro", "5a3825": "Café oscuro", "7b4a2d": "Café",
        "a56b46": "Café claro", "c98850": "Miel", "d9b380": "Rubio oscuro", "e8d4a8": "Rubio",
        "b55239": "Cobrizo", "d6455d": "Rosado", "6d5acf": "Morado", "3fb27f": "Verde"}},
    "eyesVariant": {"nombre": "Ojos", "opciones": {
        "open": "Abiertos", "soft": "Suaves", "happy": "Contentos", "sleepy": "Soñolientos",
        "side": "Mirando de lado", "closed": "Cerrados", "wide": "Muy abiertos", "star": "De estrella"}},
    "mouthVariant": {"nombre": "Boca", "opciones": {
        "smile": "Sonrisa", "bigSmile": "Sonrisa grande", "flat": "Recta", "ooh": "Sorprendida",
        "tongue": "Lengua afuera", "smirk": "Sonrisa de lado", "laugh": "Risa",
        "wideSmile": "Sonrisa ancha", "frown": "Boca hacia abajo", "grin": "Dientes"}},
    "cheeksVariant": {"nombre": "Mejillas", "ninguno": "Ninguno", "opciones": {
        "blush": "Rubor", "pixel": "Cuadritos", "freckles": "Pecas"}},
    "beardVariant": {"nombre": "Barba", "ninguno": "Ninguna", "opciones": {
        "full": "Barba completa", "mustache": "Bigote", "goatee": "Perilla", "stubble": "Barba corta"}},
    "shirtColor": {"nombre": "Color de la camiseta", "opciones": {
        "e64980": "Rosado", "f76707": "Naranja", "fab005": "Amarillo", "40c057": "Verde",
        "12b886": "Turquesa", "228be6": "Azul", "4c6ef5": "Añil", "7950f2": "Morado",
        "e8590c": "Mandarina", "495057": "Gris"}},
    # Rasgos agregados el 9 oct (B8). Todos libres, igual que los de arriba.
    "eyebrowsVariant": {"nombre": "Cejas", "opciones": {
        "flat": "Rectas", "raised": "Levantadas", "angry": "Fruncidas", "soft": "Suaves"}},
    "noseVariant": {"nombre": "Nariz", "opciones": {
        "block": "Cuadrada", "wide": "Ancha", "small": "Pequeña", "tall": "Alargada"}},
    # pantsColor tiene `notEqualTo: ["shirt"]` en voxel-art.json, pero DiceBear solo lo aplica
    # cuando ELIGE el color al azar: si el pantalón y la camiseta se piden del mismo color
    # (hoy solo coincide el gris 495057), los dibuja iguales sin cambiar ninguno (probado
    # con @dicebear/core 10.7.0). Por eso la API NO lo rechaza.
    "pantsColor": {"nombre": "Color del pantalón", "opciones": {
        "3b5b8c": "Azul jean", "2f4160": "Azul noche", "4a4e69": "Gris violeta",
        "6b4f3a": "Café", "495057": "Gris oscuro", "7a86a8": "Azul grisáceo"}},
    "shoesColor": {"nombre": "Color de los zapatos", "opciones": {
        "f1f3f5": "Blancos", "343a40": "Negros", "d6336c": "Rosados",
        "1971c2": "Azules", "f08c00": "Naranjas", "6741d9": "Morados"}},
    # Sin fondo = null (el frontend lo dibuja transparente).
    "backgroundColor": {"nombre": "Fondo", "ninguno": "Sin fondo", "opciones": {
        "b6e3f4": "Celeste", "c0aede": "Lila", "d1d4f9": "Lavanda",
        "ffd5dc": "Rosa claro", "ffdfbf": "Durazno"}},
}

# Una persona neutra, para quien todavía no ha elegido nada.
RASGOS_POR_DEFECTO = {
    "skinColor": "c99062", "topVariant": "short", "hairColor": "3b2f2f", "eyesVariant": "open",
    "mouthVariant": "smile", "cheeksVariant": None, "beardVariant": None, "shirtColor": "40c057",
    "eyebrowsVariant": "flat", "noseVariant": "small", "pantsColor": "3b5b8c", "shoesColor": "343a40",
    "backgroundColor": None,
}

# ----- EN DESUSO (9 oct): las capas PNG de la diseñadora -----
# Se conservan para no romper a quien ya las use (/avatar/base, "capas",
# "imagen_lista"), pero la persona ya no se arma con ellas. Sin imágenes, las
# rutas responden igual con `imagen_lista: false`.
CARPETA_IMAGENES_AVATAR = "avatar"
BASES_AVATAR = [
    {"id": "base_1", "nombre": "Base 1", "archivo": "base_1.png"},
    {"id": "base_2", "nombre": "Base 2", "archivo": "base_2.png"},
]
BASE_POR_DEFECTO = "base_1"
