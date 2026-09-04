import os

# Debe ir antes de cualquier import de tensorflow/keras (ver nota en predict.py)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_USE_LEGACY_KERAS"] = "1"

from flask import Flask, request, jsonify
from flask_cors import CORS
from database import BaseDatos
from predict import predecir_alimento  # única fuente de inferencia (fusión con predict.py)

app = Flask(__name__)
CORS(app)

db = BaseDatos()
print("Conexión a la base de datos establecida, Flask inicializado y CORS habilitado.")


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
        # TODO: agregar aquí los 26 códigos de tus platos regionales colombianos
        # a medida que definas sus nombres_técnicos en el dataset de entrenamiento.
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
        resultado = predecir_alimento(img_bytes)

        nombre_tecnico = resultado['alimento_codigo']
        mejor_certeza = resultado['confianza_porcentaje']

        info_alimento = db.obtener_informacion_alimento(nombre_tecnico)
        if info_alimento:
            nombre_amigable = info_alimento.get("nombre_pantalla") or formatear_nombre(nombre_tecnico)
            calorias = info_alimento.get("calorias", 250)
            es_balanceado = info_alimento.get("es_saludable", 1)
        else:
            nombre_amigable = formatear_nombre(nombre_tecnico)
            calorias = 250  # Placeholder: revisar cuando tabla_alimentos esté poblada con datos reales
            es_balanceado = 1

        guardado_exitoso = False

        if mejor_certeza >= 70.0:
            guardado_exitoso = db.registrar_comida(
                nombre_tecnico,
                nombre_amigable,
                mejor_certeza,
                calorias,
                es_balanceado,
            )
            respuesta = {
                'success': True,
                'alimento_codigo': nombre_tecnico,
                'alimento_app': nombre_amigable,
                'guardado_baseDatos': guardado_exitoso,
                'mensaje': "Predicción realizada y guardada en la base de datos." if guardado_exitoso
                           else "Predicción realizada pero no se pudo guardar en la base de datos.",
                'certeza': round(mejor_certeza, 2),
                'alimento': nombre_amigable,
            }
        else:
            respuesta = {
                'success': False,
                'guardado_baseDatos': False,
                'seleccion_manual': True,
                'mensaje': "La certeza de la IA es muy baja para guardarse automáticamente.",
                'certeza': round(mejor_certeza, 2),
                'alimento': nombre_amigable,
            }

        return jsonify(respuesta), 200
    except Exception as e:
        return jsonify({'error': f'Error al procesar la imagen: {str(e)}'}), 500


# ====== Historial ======
@app.route('/historial', methods=['GET'])
def ruta_historial():
    try:
        historial = db.obtener_historial_comida()
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


# ==== Cargar alimentos desde CSV ====
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)