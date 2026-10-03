import os

# Debe ir antes de cualquier import de tensorflow/keras (ver nota en predict.py)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_USE_LEGACY_KERAS"] = "1"

from flask import Flask, request, jsonify, send_from_directory
from PIL import UnidentifiedImageError
from flask_cors import CORS
from database import BaseDatos
from gamificacion import registrar_gamificacion, registrar_actividad, mensaje_educativo
from grupos_confusion import grupo_para, codigos_de_opciones, detalle_de_opciones
from sellos import obtener_sellos
from predict import predecir_alimento  # única fuente de inferencia (fusión con predict.py)

app = Flask(__name__)
CORS(app)

db = BaseDatos()
# Tablas y endpoints de gamificación (/progreso, /avatares, /avatar): viven
# en gamificacion.py; los números, en gamificacion_config.py.
registrar_gamificacion(app, db)
if db.conexion and db.conexion.is_connected():
    print("Conexión a la base de datos establecida, Flask inicializado y CORS habilitado.")
else:
    print("ATENCIÓN: Flask arrancó SIN base de datos. Enciende MySQL (Ajustes del Sistema → MySQL → Start) y reinicia app.py.")

# Los grupos de alimentos que siempre piden confirmación manual (sopas,
# dulces...) están en grupos_confusion.py.


def formatear_nombre(nombre_tecnico):
    """Retorna el nombre para mostrar en pantalla, dado el código técnico del modelo."""
    traducciones = {
        'apple_pie': 'Tarta de manzana',
        'baby_back_ribs': 'Costillas de cerdo',
        'baklava': 'Baklava',
        'beef_carpaccio': 'Carpaccio de ternera',
        'beef_tartare': 'Tartar de ternera',
        'beet_salad': 'Ensalada de remolacha',
        'beignets': 'Buñuelos',
        'bibimbap': 'Bibimbap',
        'bread_pudding': 'Budín de pan',
        'breakfast_burrito': 'Burrito de desayuno',
        'bruschetta': 'Bruschetta',
        'caesar_salad': 'Ensalada César',
        'cannoli': 'Cannoli',
        'caprese_salad': 'Ensalada Caprese',
        'carrot_cake': 'Pastel de zanahoria',
        'ceviche': 'Ceviche',
        'cheesecake': 'Tarta de queso',
        'cheese_plate': 'Plato de quesos',
        'chicken_curry': 'Curry de pollo',
        'chicken_quesadilla': 'Quesadilla de pollo',
        'chicken_wings': 'Alitas de pollo',
        'chocolate_cake': 'Pastel de chocolate',
        'chocolate_mousse': 'Mousse de chocolate',
        'churros': 'Churros',
        'clam_chowder': 'Sopa de almejas',
        'club_sandwich': 'Sándwich club',
        'crab_cakes': 'Pasteles de cangrejo',
        'creme_brulee': 'Crema catalana',
        'croque_madame': 'Croque Madame',
        'cup_cakes': 'Magdalenas',
        'deviled_eggs': 'Huevos rellenos',
        'donuts': 'Donas',
        'dumplings': 'Dumplings',
        'edamame': 'Edamame',
        'eggs_benedict': 'Huevos benedictinos',
        'escargots': 'Caracoles',
        'falafel': 'Falafel',
        'filet_mignon': 'Filete mignon',
        'fish_and_chips': 'Pescado con patatas fritas',
        'foie_gras': 'Foie gras',
        'french_fries': 'Papas fritas',
        'french_onion_soup': 'Sopa de cebolla francesa',
        'french_toast': 'Tostadas francesas',
        'fried_calamari': 'Calamares fritos',
        'fried_rice': 'Arroz frito',
        'frozen_yogurt': 'Yogur helado',
        'garlic_bread': 'Pan de ajo',
        'gnocchi': 'Ñoquis',
        'greek_salad': 'Ensalada griega',
        'grilled_cheese_sandwich': 'Sándwich de queso a la parrilla',
        'grilled_salmon': 'Salmón a la parrilla',
        'guacamole': 'Guacamole',
        'gyoza': 'Gyoza',
        'hamburger': 'Hamburguesa',
        'hot_and_sour_soup': 'Sopa agripicante',
        'hot_dog': 'Perro caliente',
        'huevos_rancheros': 'Huevos rancheros',
        'hummus': 'Hummus',
        'ice_cream': 'Helado',
        'lasagna': 'Lasaña',
        'lobster_bisque': 'Bisque de langosta',
        'lobster_roll_sandwich': 'Sándwich de langosta',
        'macaroni_and_cheese': 'Macarrones con queso',
        'macarons': 'Macarons',
        'miso_soup': 'Sopa de miso',
        'mussels': 'Mejillones',
        'nachos': 'Nachos',
        'omelette': 'Tortilla francesa',
        'onion_rings': 'Aros de cebolla',
        'oysters': 'Ostras',
        'pad_thai': 'Pad Thai',
        'paella': 'Paella',
        'pancakes': 'Panqueques',
        'panna_cotta': 'Panna cotta',
        'peking_duck': 'Pato Pekín',
        'pho': 'Pho',
        'pizza': 'Pizza',
        'pork_chop': 'Chuleta de cerdo',
        'poutine': 'Poutine',
        'prime_rib': 'Costilla de res',
        'pulled_pork_sandwich': 'Sándwich de cerdo desmenuzado',
        'ramen': 'Ramen',
        'ravioli': 'Raviolis',
        'red_velvet_cake': 'Pastel de red velvet',
        'risotto': 'Risotto',
        'samosa': 'Samosa',
        'sashimi': 'Sashimi',
        'scallops': 'Vieiras',
        'seaweed_salad': 'Ensalada de algas',
        'shrimp_and_grits': 'Camarones con sémola',
        'spaghetti_bolognese': 'Espaguetis a la boloñesa',
        'spaghetti_carbonara': 'Espaguetis a la carbonara',
        'spring_rolls': 'Rollitos de primavera',
        'steak': 'Bistec',
        'strawberry_shortcake': 'Pastel de fresa',
        'sushi': 'Sushi',
        'tacos': 'Tacos',
        'takoyaki': 'Takoyaki',
        'tiramisu': 'Tiramisú',
        'tuna_tartare': 'Tartar de atún',
        'waffles': 'Waffles',
    }
    return traducciones.get(nombre_tecnico, nombre_tecnico.replace('_', ' ').title())


# ====== Predicción de alimentos ======
@app.route('/predecir', methods=['POST'])
def predecir():
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró el campo de imagen en la petición.'}), 400
    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo o la imagen está vacía.'}), 400

    try:
        # Una sola lectura de los bytes (evita el bug de doble .read() del stream)
        img_bytes = file.read()
        # Foto vacía o archivo que no es imagen: es un error de quien envía
        # (400), no del servidor (500).
        if not img_bytes:
            return jsonify({'error': 'La imagen está vacía.'}), 400
        try:
            resultado = predecir_alimento(img_bytes)
        except UnidentifiedImageError:
            return jsonify({'error': 'El archivo no es una imagen válida (usa una foto JPG o PNG).'}), 400

        nombre_tecnico = resultado['alimento_codigo']
        mejor_certeza = resultado['confianza_porcentaje']

        # Campo opcional (multipart/form-data, junto a 'file'): si viene y
        # corresponde a un perfil existente, la predicción queda ligada a ese
        # usuario en historial_comida. Sin 'email' (o con uno que no tiene
        # perfil todavía) la predicción igual se guarda, solo que sin dueño.
        usuario_id = None
        email = request.form.get('email')
        if email:
            perfil = db.obtener_perfil_por_email(email)
            if perfil:
                usuario_id = perfil['id']

        info_alimento = db.obtener_informacion_alimento(nombre_tecnico)
        if info_alimento:
            nombre_amigable = info_alimento.get("nombre_pantalla") or formatear_nombre(nombre_tecnico)
            calorias = info_alimento.get("calorias", 250)
            es_balanceado = info_alimento.get("es_saludable", 1)
            dato_curioso = info_alimento.get("dato_curioso")
        else:
            nombre_amigable = formatear_nombre(nombre_tecnico)
            calorias = None 
            es_balanceado = 1
            dato_curioso = None

        guardado_exitoso = False

        grupo_activado = grupo_para(nombre_tecnico)
        if grupo_activado:
            respuesta = {
                'success': False,
                'guardado_baseDatos': False,
                'seleccion_manual': True,
                'mensaje': grupo_activado["mensaje"],
                'certeza': round(mejor_certeza, 2),
                'alimento': nombre_amigable,
                'alimento_codigo': nombre_tecnico,
                'dato_curioso': dato_curioso,
                'opciones_sugeridas': codigos_de_opciones(grupo_activado),
                'opciones_detalle': detalle_de_opciones(grupo_activado),
                'modelo_usado': resultado.get('modelo_usado'),
            }
            return jsonify(respuesta), 200

        if mejor_certeza >= 70.0:
            guardado_exitoso = db.registrar_comida(
                nombre_tecnico,
                nombre_amigable,
                mejor_certeza,
                calorias,
                es_balanceado,
                usuario_id,
            )
            # Lista de sellos de la Res. 810 ([] = ninguno, None = no se sabe).
            # Mostrar "Sin sellos de advertencia", nunca "saludable": ver CONTRATO_CONFIRMACION.md.
            sellos = obtener_sellos(db, nombre_tecnico)
            gamificacion = registrar_actividad(
                db, usuario_id, "comida_registrada", alimento_codigo=nombre_tecnico, sellos=sellos,
            ) if guardado_exitoso else None
            respuesta = {
                'success': True,
                'alimento_codigo': nombre_tecnico,
                'alimento_app': nombre_amigable,
                'guardado_baseDatos': guardado_exitoso,
                'mensaje': "Predicción realizada y guardada en la base de datos." if guardado_exitoso
                           else "Predicción realizada pero no se pudo guardar en la base de datos.",
                'certeza': round(mejor_certeza, 2),
                'alimento': nombre_amigable,
                'dato_curioso': dato_curioso,
                'sellos_advertencia': sellos,
                # Producto de paquete: un dato y una alternativa, nunca un regaño.
                'mensaje_educativo': mensaje_educativo(nombre_tecnico),
                'modelo_usado': resultado.get('modelo_usado'),
                'gamificacion': gamificacion,
            }
        else:
            respuesta = {
                'success': False,
                'guardado_baseDatos': False,
                'seleccion_manual': True,
                'mensaje': "La certeza de la IA es muy baja para guardarse automáticamente.",
                'certeza': round(mejor_certeza, 2),
                'alimento': nombre_amigable,
                'alimento_codigo': nombre_tecnico,
                'dato_curioso': dato_curioso,
                'modelo_usado': resultado.get('modelo_usado'),
            }

        return jsonify(respuesta), 200
    except Exception as e:
        return jsonify({'error': f'Error al procesar la imagen: {str(e)}'}), 500


# ====== Confirmación manual ======
# Genérico -- no es solo para el grupo de sopas. Cubre CUALQUIER caso donde
# /predecir respondió seleccion_manual=true (certeza <70%, o el forzado del
# grupo ajiaco/sancocho/mondongo/sopas) y el usuario elige a mano cuál
# alimento es en realidad. Sin estado compartido con la predicción
# original -- el cliente simplemente manda el código que el usuario eligió.
@app.route('/confirmar-alimento', methods=['POST'])
def confirmar_alimento():
    datos = request.get_json(silent=True) or {}
    alimento_codigo = datos.get('alimento_codigo')
    if not alimento_codigo:
        return jsonify({'error': 'Falta el campo "alimento_codigo".'}), 400

    info_alimento = db.obtener_informacion_alimento(alimento_codigo)
    if not info_alimento:
        # Incluye deliberadamente los códigos de agrupación visual ("sopas",
        # "dulces", ver grupos_confusion.py): no tienen fila en
        # tabla_alimentos a propósito, así que también se rechazan aquí --
        # nunca se inventa una fila para algo sin nutrición propia real.
        return jsonify({'error': f'"{alimento_codigo}" no es un alimento reconocido en tabla_alimentos.'}), 400

    usuario_id = None
    email = datos.get('email')
    if email:
        perfil = db.obtener_perfil_por_email(email)
        if perfil:
            usuario_id = perfil['id']

    nombre_amigable = info_alimento.get("nombre_pantalla") or formatear_nombre(alimento_codigo)
    calorias = info_alimento.get("calorias", 250)
    es_balanceado = info_alimento.get("es_saludable", 1)
    dato_curioso = info_alimento.get("dato_curioso")

    # 100.0: es una confirmación humana, no una predicción de la IA -- no
    # hay "certeza" que reportar, así que se usa el máximo por convención
    # (ver diseño propuesto/aprobado en la conversación del proyecto).
    guardado_exitoso = db.registrar_comida(
        alimento_codigo, nombre_amigable, 100.0, calorias, es_balanceado, usuario_id,
    )
    sellos = obtener_sellos(db, alimento_codigo)  # ver /predecir
    gamificacion = registrar_actividad(
        db, usuario_id, "comida_registrada", alimento_codigo=alimento_codigo, sellos=sellos,
    ) if guardado_exitoso else None

    respuesta = {
        'success': True,
        'alimento_codigo': alimento_codigo,
        'alimento_app': nombre_amigable,
        'guardado_baseDatos': guardado_exitoso,
        'mensaje': "Confirmado manualmente y guardado en tu historial." if guardado_exitoso
                   else "Confirmado, pero no se pudo guardar en la base de datos.",
        'certeza': 100.0,
        'alimento': nombre_amigable,
        'dato_curioso': dato_curioso,
        'sellos_advertencia': sellos,
        'mensaje_educativo': mensaje_educativo(alimento_codigo),
        'gamificacion': gamificacion,
    }
    return jsonify(respuesta), 200


# ====== Perfil de usuario ======
# ==== Reglas de la contraseña ====
# Mínimo 6 caracteres (lo que promete el formulario de crear cuenta) y máximo
# 72 BYTES: bcrypt no acepta contraseñas más largas (lanza ValueError). Son
# bytes, no letras: la ñ y las tildes ocupan 2 bytes en UTF-8.
CONTRASENA_MIN_CARACTERES = 6
CONTRASENA_MAX_BYTES = 72


def error_de_contraseña(contraseña):
    """El mensaje de error si la contraseña no sirve, o None si está bien."""
    if not isinstance(contraseña, str) or len(contraseña) < CONTRASENA_MIN_CARACTERES:
        return f'La contraseña debe tener al menos {CONTRASENA_MIN_CARACTERES} caracteres.'
    if len(contraseña.encode('utf-8')) > CONTRASENA_MAX_BYTES:
        return 'La contraseña es demasiado larga (máximo 72 bytes; las tildes y la ñ cuentan doble).'
    return None


@app.route('/perfil', methods=['POST'])
def guardar_perfil():
    """Crea la cuenta (con contraseña obligatoria) o actualiza los datos de un
    perfil que ya existe. POST /perfil NO cambia contraseñas: identifica a la
    persona solo por el correo (ver REVISION_CODIGO_ISABELLA.md, problema 5)."""
    if not db.conexion or not db.conexion.is_connected():
        # 503 = el servicio no está disponible: no es culpa de lo que envió el usuario.
        return jsonify({'error': 'Sin conexión con la base de datos. ¿MySQL está encendido?'}), 503
    datos = request.get_json(silent=True) or {}
    requeridos = ['nombre', 'email', 'edad', 'genero', 'peso', 'altura']
    faltantes = [campo for campo in requeridos if campo not in datos]
    if faltantes:
        return jsonify({'error': f'Faltan campos: {", ".join(faltantes)}'}), 400

    contraseña = datos.get('contraseña')
    tiene_contraseña = db.estado_contraseña(datos['email'])  # None = el correo no tiene perfil
    if contraseña is not None:
        error = error_de_contraseña(contraseña)
        if error:
            return jsonify({'error': error}), 400
        if tiene_contraseña:
            # Ya hay una cuenta con contraseña: registrarse otra vez no puede
            # reemplazarla (ni cambiarle los datos a esa persona).
            return jsonify({'error': 'Ya existe una cuenta con ese correo. Inicia sesión con tu contraseña.'}), 409
    elif tiene_contraseña is None:
        # Cuenta nueva sin contraseña: desde el login con Bcrypt es obligatoria.
        return jsonify({'error': f'La contraseña es obligatoria para crear una cuenta (mínimo {CONTRASENA_MIN_CARACTERES} caracteres).'}), 400

    exito = db.guardar_perfil(
        datos['nombre'], datos['email'], datos['edad'], datos['genero'],
        datos['peso'], datos['altura'], datos.get('objetivo'), contraseña,
    )
    if exito:
        return jsonify({'success': True, 'mensaje': 'Perfil guardado.'}), 200
    return jsonify({'error': 'No se pudo guardar el perfil (revisa que "objetivo" sea uno de los valores válidos).'}), 400


@app.route('/perfil', methods=['GET'])
def obtener_perfil():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Falta el parámetro "email".'}), 400
    perfil = db.obtener_perfil_por_email(email)
    if perfil:
        return jsonify({'success': True, 'perfil': perfil}), 200
    return jsonify({'success': False, 'mensaje': 'No hay perfil guardado con ese correo.'}), 404

# ==== Login de usuario (verificación de contraseña) ====
# El MISMO mensaje para contraseña incorrecta, correo inexistente y perfil viejo
# sin contraseña: así nadie puede usar el login para averiguar qué correos
# están registrados. La "ayuda" explica qué hacer a quien tiene un perfil viejo.
RESPUESTA_CREDENCIALES_INVALIDAS = {
    "error": "Correo o contraseña incorrectos.",
    "ayuda": "Si creaste tu cuenta antes de que Lumea pidiera contraseña, vuelve a "
             "registrarte con el mismo correo para crear una.",
}


@app.route('/login', methods=['POST'])
def login():
    # silent=True: si no llega JSON (o llega algo raro), data queda en {} y se
    # responde 400 con la misma forma que las demás rutas, en vez de un 415/500.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    email = data.get('email')
    contraseña = data.get('contraseña')

    if not email or not contraseña or not isinstance(contraseña, str):
        return jsonify({"error": "Correo y contraseña son requeridos"}), 400

    try:
        # 1. Usar el método de verificación segura (maneja usuarios inexistentes y cuentas viejas)
        if not db.verificar_contraseña(email, contraseña):
            # 💡 SEGURIDAD: Respondemos 401 tanto para contraseña incorrecta, cuenta vieja o email inexistente
            return jsonify(RESPUESTA_CREDENCIALES_INVALIDAS), 401

        # 2. Si es válida, obtenemos los datos limpios (sin el password_hash)
        perfil = db.obtener_datos_login(email)
        
        return jsonify({
            "success": True,
            "message": "Inicio de sesión exitoso",
            "perfil": perfil
        }), 200
        
    except Exception as e:
        print(f"Error interno en inicio de sesión: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


# ====== Estado de ánimo (check-in diario, separado del perfil) ======
@app.route('/estado-animo', methods=['POST'])
def registrar_estado_animo():
    datos = request.get_json(silent=True) or {}
    estado = datos.get('estado')
    email = datos.get('email')
    if not estado:
        return jsonify({'error': 'Falta el campo "estado".'}), 400
    if not email:
        return jsonify({'error': 'Falta el campo "email".'}), 400

    perfil = db.obtener_perfil_por_email(email)
    if not perfil:
        return jsonify({'error': 'No existe un perfil con ese correo.'}), 404

    exito = db.registrar_estado_animo(estado, perfil['id'])
    if exito:
        # El XP es el mismo sea cual sea el estado (ver gamificacion_config.py);
        # el estado solo cambia la expresión del avatar.
        gamificacion = registrar_actividad(db, perfil['id'], "estado_animo", estado_animo=estado)
        return jsonify({'success': True, 'mensaje': 'Estado de ánimo registrado.', 'gamificacion': gamificacion}), 200
    return jsonify({'error': f'Estado no válido. Usa uno de: {sorted(db.ESTADOS_VALIDOS)}'}), 400


@app.route('/estado-animo', methods=['GET'])
def obtener_estado_animo():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Falta el parámetro "email".'}), 400
    perfil = db.obtener_perfil_por_email(email)
    if not perfil:
        return jsonify({'error': 'No existe un perfil con ese correo.'}), 404
    registros = db.obtener_estado_animo_reciente(perfil['id'])
    return jsonify({'success': True, 'cantidad': len(registros), 'historial': registros}), 200


# ====== Historial ======
@app.route('/historial', methods=['GET'])
def ruta_historial():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Falta el parámetro "email".'}), 400
    perfil = db.obtener_perfil_por_email(email)
    if not perfil:
        return jsonify({'error': 'No existe un perfil con ese correo.'}), 404
    try:
        historial = db.obtener_historial_comida(perfil['id'])
        # Sellos de advertencia de cada registro ([] = ninguno, None = no se
        # sabe), igual que en /predecir. Se consultan una vez por alimento.
        sellos_por_codigo = {}
        for registro in historial:
            codigo = registro.get('alimento_codigo')
            if codigo not in sellos_por_codigo:
                sellos_por_codigo[codigo] = obtener_sellos(db, codigo) if codigo else None
            registro['sellos_advertencia'] = sellos_por_codigo[codigo]
        return jsonify({
            'success': True,
            'cantidad_registros': len(historial),
            'historial': historial,
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error al consultar el historial: {str(e)}'}), 500


# ===== Alimentos disponibles =====
@app.route('/alimentos', methods=['GET'])
def lista_alimentos():
    try:
        if not db.conexion or not db.conexion.is_connected():
            return jsonify({'error': 'Sin conexión a la base de datos'}), 500

        cursor = db.conexion.cursor(dictionary=True)
        cursor.execute(
            "SELECT alimento_codigo, nombre_pantalla, calorias, es_saludable FROM tabla_alimentos"
        )
        alimentos = cursor.fetchall()
        cursor.close()

        return jsonify({
            'success': True,
            'cantidad': len(alimentos),
            'alimentos': alimentos,
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error al obtener la lista de alimentos: {str(e)}'}), 500


# ==== Cargar alimentos desde CSV ====  # YA NO SE USA, ASÍ QUE DEBE ELIMINARSE 
@app.route('/cargar-alimentos-csv', methods=['POST'])
def cargar_alimentos_csv():
    """
    Sube un archivo .csv con la estructura:
    alimento_codigo,nombre_pantalla,calorias,es_saludable
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No se adjuntó ningún archivo CSV.'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'El archivo debe tener extensión .csv'}), 400

    try:
        contenido_csv = file.read().decode('utf-8')
        # Nombre corregido: coincide con el método real de database.py
        # (antes se llamaba a cargar_alimentos_desde_csv_contenido, que no existe)
        exito, mensaje = db.cargar_alimentos_desde_csv(contenido_csv)

        if exito:
            return jsonify({'success': True, 'mensaje': mensaje}), 200
        else:
            return jsonify({'error': mensaje}), 400
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {str(e)}'}), 500


# ==== Demo de la cámara (feria) ====
# Sirve SOLO el archivo camara.html desde esta misma carpeta. Al estar en la
# misma dirección que la API (http://127.0.0.1:5002/camara), el navegador no
# necesita CORS y permite la cámara (127.0.0.1 es un "contexto seguro").
# send_from_directory con un nombre fijo no expone ningún otro archivo (.env).
@app.route('/camara')
def pagina_camara():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'camara.html')


if __name__ == '__main__':
    # use_reloader=False es crítico aquí: el reloader de Flask arranca la app
    # en un proceso hijo aparte para poder reiniciarla sola al detectar
    # cambios. TensorFlow en macOS (sobre todo Apple Silicon) tiene problemas
    # documentados cuando su inicialización queda dividida entre el proceso
    # padre y ese hijo -- puede colgar peticiones indefinidamente, sin error
    # ni log. Puerto 5001 evitado por AirPlay Receiver (ver nota anterior).
    app.run(host='0.0.0.0', port=5002, debug=True, use_reloader=False)