import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import json
import numpy as np
import tensorflow as tf
import keras
from PIL import Image
import io

Base_dir = os.path.dirname(os.path.abspath(__file__))

# === Modelo 1: 26 clases regionales colombianas (fine-tuning) ===
Model_path_26 = os.path.join(Base_dir, "modelo_lumea_comida.keras")
class_path_26 = os.path.join(Base_dir, "clases.json")
modelo_26 = keras.models.load_model(Model_path_26, compile=False)
with open(class_path_26, "r", encoding="utf-8") as f:
    classes_26 = json.load(f)

# === Modelo 2: 101 clases de Food-101 (base congelada, weights='imagenet') ===
Model_path_101 = os.path.join(Base_dir, "modelo_lumea.h5")
class_path_101 = os.path.join(Base_dir, "clases_101.json")
modelo_101 = keras.models.load_model(Model_path_101, compile=False)
with open(class_path_101, "r", encoding="utf-8") as f:
    classes_101 = json.load(f)

print(f"Modelo regional cargado: {len(classes_26)} clases.")
print(f"Modelo Food-101 cargado: {len(classes_101)} clases.")
print("Ensamble listo: cada predicción compara ambos modelos y usa el de mayor confianza.")


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

    Nota importante (documentada, no oculta): comparar la confianza cruda
    entre dos modelos entrenados por separado no es perfectamente comparable
    estadísticamente -un modelo puede tender a dar valores más altos que el
    otro en general-. Es una heurística simple y razonable para el alcance
    de este proyecto, con esa limitación conocida.
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = image.resize((224, 224))

    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)
    image_array = tf.keras.applications.mobilenet_v2.preprocess_input(image_array)

    alimento_26, confianza_26 = _predecir_con_modelo(modelo_26, classes_26, image_array)
    alimento_101, confianza_101 = _predecir_con_modelo(modelo_101, classes_101, image_array)

    if confianza_26 >= confianza_101:
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