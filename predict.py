import os

# CRÍTICO: estas variables de entorno deben fijarse ANTES de importar tensorflow/keras.
# TensorFlow las lee una sola vez, al inicializarse en el import. Si se fijan después,
# no tienen ningún efecto (este era uno de los bugs: en app.py original se fijaba
# después de `import keras`).
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import json
import numpy as np
import tensorflow as tf
import keras
from PIL import Image
import io

Base_dir = os.path.dirname(os.path.abspath(__file__))
Model_path = os.path.join(Base_dir, "modelo_lumea_comida.h5")
class_path = os.path.join(Base_dir, "clases.json")

# compile=False: no necesitamos optimizer/loss para inferencia, y esto evita
# errores de deserialización cuando el modelo se guardó con una versión de
# Keras distinta a la que lo carga (el choque Keras 3 / Keras 2 que documentaste).
modelo = keras.models.load_model(Model_path, compile=False)

with open(class_path, "r", encoding="utf-8") as f:
    classes = json.load(f)

print(f"Modelo cargado. {len(classes)} clases disponibles.")


def predecir_alimento(image_bytes: bytes):
    """Recibe los bytes crudos de una imagen y devuelve la clase predicha.

    Usa PIL + io.BytesIO (una sola lectura de los bytes, ya en memoria) para
    evitar el bug de doble lectura del stream de Flask.
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = image.resize((224, 224))

    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)
    # Mismo preprocesamiento usado en entrenamiento (rango [-1, 1])
    image_array = tf.keras.applications.mobilenet_v2.preprocess_input(image_array)

    predicciones = modelo.predict(image_array, verbose=0)

    # IMPORTANTE: NO usar keras.applications.mobilenet_v2.decode_predictions aquí.
    # Esa función asume 1000 clases de ImageNet con nombres fijos; nuestro modelo
    # tiene una capa de salida propia (softmax sobre `classes`), así que el índice
    # de mayor probabilidad se busca directamente en clases.json.
    clase_idx = int(np.argmax(predicciones[0]))
    confianza = float(predicciones[0][clase_idx])
    alimento_codigo = classes[clase_idx]

    return {
        "alimento_codigo": alimento_codigo,
        "confianza_porcentaje": round(confianza * 100, 2),
    }
