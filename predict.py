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
Model_path = os.path.join(Base_dir, "modelo_lumea_comida.keras")
class_path = os.path.join(Base_dir, "clases.json")

modelo = keras.models.load_model(Model_path, compile=False)

with open(class_path, "r", encoding="utf-8") as f:
    classes = json.load(f)

print(f"Modelo cargado. {len(classes)} clases disponibles.")


def predecir_alimento(image_bytes: bytes):
    """Recibe los bytes crudos de una imagen y devuelve la clase predicha."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = image.resize((224, 224))

    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)
    print("=== DIAGNÓSTICO ===")
    print("¿NaN en la imagen ANTES de preprocesar?", np.isnan(image_array).any())
    print("Rango de píxeles ANTES de preprocesar: min =", image_array.min(), "max =", image_array.max())

    image_array = tf.keras.applications.mobilenet_v2.preprocess_input(image_array)
    print("¿NaN en la imagen DESPUÉS de preprocesar?", np.isnan(image_array).any())
    print("Rango de píxeles DESPUÉS de preprocesar: min =", image_array.min(), "max =", image_array.max())

    predicciones = modelo.predict(image_array, verbose=0)
    print("Vector de predicciones completo:", predicciones[0])
    print("¿Cuántos NaN hay en las predicciones?", np.isnan(predicciones[0]).sum(), "de", len(predicciones[0]))
    print("=== FIN DIAGNÓSTICO ===")

    clase_idx = int(np.argmax(predicciones[0]))
    confianza = float(predicciones[0][clase_idx])
    alimento_codigo = classes[clase_idx]

    return {
        "alimento_codigo": alimento_codigo,
        "confianza_porcentaje": round(confianza * 100, 2),
    }
