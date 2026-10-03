import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import json
import numpy as np
import tensorflow as tf
import keras
from PIL import Image
import io

Base_dir = os.path.dirname(os.path.abspath(__file__))

import tf_keras

# === Modelo 1: clases regionales colombianas (fine-tuning) ===
# Se carga con tf_keras (Keras 2 legacy), NO con `keras` a secas -- este
# modelo lo guarda ia_comida.py usando tf.keras.* con TF_USE_LEGACY_KERAS=1,
# es decir en formato Keras 2 real. `keras.models.load_model` (Keras 3
# siempre, sin importar esa variable -- ver CLAUDE.md) no puede deserializar
# ese formato: falla con "Could not locate class 'Functional'" porque el
# submodelo interno de MobileNetV2 queda con `registered_name: 'Functional'`,
# que Keras 3 trata como una clase custom sin registrar en vez de una clase
# nativa. modelo_101 SÍ se guardó ya en formato Keras 3 (entrenado aparte,
# en Colab) y por eso sigue cargando con `keras` normal más abajo.
Model_path_26 = os.path.join(Base_dir, "modelo_lumea_comida.keras")
class_path_26 = os.path.join(Base_dir, "clases.json")
modelo_26 = tf_keras.models.load_model(Model_path_26, compile=False)
with open(class_path_26, "r", encoding="utf-8") as f:
    classes_26 = json.load(f)

# === Modelo 2: 101 clases de Food-101 (base congelada, weights='imagenet') ===
Model_path_101 = os.path.join(Base_dir, "modelo_lumea101.keras")
class_path_101 = os.path.join(Base_dir, "clases_101.json")
modelo_101 = keras.models.load_model(Model_path_101, compile=False)
with open(class_path_101, "r", encoding="utf-8") as f:
    classes_101 = json.load(f)

# === Regla de decisión entre los dos modelos ("cascada") ===
# Antes: ganaba SIEMPRE el modelo con mayor confianza. Problema: Food-101 no
# tiene frutas ni platos colombianos, pero su softmax igual reparte el 100 %
# entre sus 101 clases (mundo cerrado) y puede estar muy "seguro" de algo
# imposible (banano -> macarons). Las confianzas de dos redes entrenadas por
# separado no son comparables (Guo et al., 2017).
# Ahora: el modelo REGIONAL (nuestro dominio) decide primero; Food-101 solo
# entra si el regional duda (confianza < UMBRAL_REGIONAL).
# UMBRAL_REGIONAL = 0.0 -> siempre regional (Food-101 nunca gana)
# UMBRAL_REGIONAL = 1.01 -> comportamiento anterior (gana el mayor)
UMBRAL_REGIONAL = float(os.getenv("LUMEA_UMBRAL_REGIONAL", "0.4"))

print(f"Modelo regional cargado: {len(classes_26)} clases.")
print(f"Modelo Food-101 cargado: {len(classes_101)} clases.")
print(f"Ensamble en cascada: decide el regional si su confianza >= {UMBRAL_REGIONAL:.2f}; si no, compara con Food-101.")


def _predecir_con_modelo(modelo, classes, image_array):
    """Corre un modelo sobre la imagen ya preprocesada y devuelve su mejor
    clase junto con la confianza (0-1) de esa clase."""
    predicciones = modelo.predict(image_array, verbose=0)
    clase_idx = int(np.argmax(predicciones[0]))
    confianza = float(predicciones[0][clase_idx])
    return classes[clase_idx], confianza


def predecir_alimento(image_bytes: bytes):
    """Recibe los bytes crudos de una imagen y devuelve la clase predicha,
    eligiendo entre el modelo regional (26 clases) y el de Food-101 (101
    clases) según cuál esté más seguro de su propia predicción.

    Nota importante: comparar la confianza cruda
    entre dos modelos entrenados por separado no es perfectamente comparable
    estadísticamente. 
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = image.resize((224, 224))
    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)

    # Modelo 26/35 clases: preprocess_input YA está dentro del grafo guardado
    # -- mandarle la imagen cruda (0-255), NO preprocesarla aquí también.
    alimento_26, confianza_26 = _predecir_con_modelo(modelo_26, classes_26, image_array)

    # Modelo 101 (Food-101): preprocess_input NO está dentro del grafo
    # -- este sí lo necesita aplicado manualmente antes de predict().
    # .copy(): preprocess_input modifica arreglos numpy EN EL MISMO LUGAR; sin
    # la copia, si alguien moviera esta línea antes del modelo regional, este
    # recibiría la imagen preprocesada dos veces (el bug de "todo es Dulces").
    image_array_101 = tf.keras.applications.mobilenet_v2.preprocess_input(image_array.copy())
    alimento_101, confianza_101 = _predecir_con_modelo(modelo_101, classes_101, image_array_101)

    # Cascada: si el regional está razonablemente seguro, decide él.
    # Si duda, se compara con Food-101 como antes.
    if confianza_26 >= UMBRAL_REGIONAL or confianza_26 >= confianza_101:
        alimento_codigo, confianza = alimento_26, confianza_26
        modelo_ganador = "regional_26"
    else:
        alimento_codigo, confianza = alimento_101, confianza_101
        modelo_ganador = "food101"

    return {
        "alimento_codigo": alimento_codigo,
        "confianza_porcentaje": round(confianza * 100, 2),
        "modelo_usado": modelo_ganador,  # útil para depurar / mostrar en el frontend si quieren
    }