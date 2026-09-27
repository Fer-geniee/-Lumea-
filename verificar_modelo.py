"""
verificar_modelo.py -- Revisa un modelo Food-101 (.keras) ANTES de ponerlo
en lugar de modelo_lumea101.keras. No modifica nada.

    python3 verificar_modelo.py                              # revisa modelo_lumea101.keras
    python3 verificar_modelo.py ~/Downloads/modelo_nuevo.keras
    python3 verificar_modelo.py nuevo.keras --imagenes a.jpg b.jpg c.jpg

Comprueba:
1. Que carga con `keras` (Keras 3), igual que predict.py.
2. Entrada 224x224x3 y salida de 101 clases.
3. Que clases_101.json tiene 101 clases (mismo orden que la salida).
4. Si el modelo trae capas de preprocesamiento dentro (Rescaling,
   Normalization, truediv...). predict.py le aplica preprocess_input de
   MobileNetV2 A MANO, así que si el modelo también lo trae, la imagen se
   preprocesa DOS veces. Las capas de aumento de datos (RandomFlip,
   RandomRotation...) están bien: solo actúan al entrenar.
5. Que predice clases distintas para 3 imágenes distintas. Si todas dan la
   misma clase, casi siempre es doble preprocesamiento.

Sale con código 0 si todo está bien y 1 si algo falla.
"""

import os

# Igual que app.py: debe ir antes de importar tensorflow/keras. Así
# tf.keras.applications es el mismo que usa predict.py.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import argparse
import json
import sys

import keras
import numpy as np
import tensorflow as tf
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGENES_POR_DEFECTO = [
    os.path.join(BASE_DIR, "prueba.jpeg"),
    os.path.join(BASE_DIR, "dataset", "sopas", "02934.jpg"),
    os.path.join(BASE_DIR, "dataset", "banano"),  # una carpeta: se toma su primera foto
]
CAPAS_DE_PREPROCESAMIENTO = ("Rescaling", "Normalization", "TrueDivide", "Subtract", "TFOpLambda", "Lambda")
PALABRAS_DE_PREPROCESAMIENTO = ("truediv", "subtract", "rescal", "normaliz", "preprocess")
CAPAS_DE_AUMENTO = ("RandomFlip", "RandomRotation", "RandomZoom", "RandomContrast", "RandomTranslation",
                    "RandomBrightness", "RandomCrop")

resultados = []


def revisar(nombre, ok, detalle=""):
    resultados.append(ok)
    print(f"[{'OK' if ok else 'FALLA'}] {nombre}" + (f" -- {detalle}" if detalle else ""))


def todas_las_capas(modelo):
    """Capas del modelo, incluidas las de submodelos (p. ej. MobileNetV2 adentro)."""
    for capa in modelo.layers:
        yield capa
        if hasattr(capa, "layers"):
            yield from todas_las_capas(capa)


def cargar_imagen(ruta):
    """Igual que predict.py (predecir_alimento): RGB, 224x224, float32 y
    preprocess_input de MobileNetV2 (lleva los píxeles de 0..255 a -1..1)."""
    if os.path.isdir(ruta):
        ruta = os.path.join(ruta, sorted(f for f in os.listdir(ruta) if f.lower().endswith((".jpg", ".jpeg", ".png")))[0])
    imagen = Image.open(ruta).convert("RGB").resize((224, 224))
    arreglo = np.expand_dims(np.array(imagen, dtype=np.float32), axis=0)
    return ruta, tf.keras.applications.mobilenet_v2.preprocess_input(arreglo)


def main():
    parser = argparse.ArgumentParser(description="Revisa un modelo Food-101 antes de reemplazarlo.")
    parser.add_argument("modelo", nargs="?", default=os.path.join(BASE_DIR, "modelo_lumea101.keras"))
    parser.add_argument("--clases", default=os.path.join(BASE_DIR, "clases_101.json"))
    parser.add_argument("--imagenes", nargs=3, default=IMAGENES_POR_DEFECTO, metavar="IMAGEN")
    args = parser.parse_args()

    print(f"Modelo: {args.modelo}\n")

    # 1. Carga
    try:
        modelo = keras.models.load_model(args.modelo, compile=False)
        revisar("carga con keras (Keras 3), como en predict.py", True)
    except Exception as error:
        revisar("carga con keras (Keras 3), como en predict.py", False, str(error)[:300])
        print("\nNo se pudo cargar: el resto de las pruebas no se puede hacer.")
        sys.exit(1)

    # 2. Forma de entrada y de salida
    entrada = tuple(modelo.input_shape)
    salida = tuple(modelo.output_shape)
    revisar("entrada 224x224x3", entrada[1:] == (224, 224, 3), f"input_shape={entrada}")
    revisar("salida de 101 clases", salida[-1] == 101, f"output_shape={salida}")

    # 3. clases_101.json
    with open(args.clases, encoding="utf-8") as f:
        clases = json.load(f)
    revisar("clases_101.json tiene 101 clases y coincide con la salida", len(clases) == 101 == salida[-1],
            f"{len(clases)} clases en el archivo")

    # 4. Capas de preprocesamiento o de aumento dentro del modelo
    capas = list(todas_las_capas(modelo))
    sospechosas = [
        f"{c.name} ({type(c).__name__})" for c in capas
        if type(c).__name__ in CAPAS_DE_PREPROCESAMIENTO or any(p in c.name.lower() for p in PALABRAS_DE_PREPROCESAMIENTO)
    ]
    aumento = [f"{c.name} ({type(c).__name__})" for c in capas if type(c).__name__ in CAPAS_DE_AUMENTO]
    revisar("sin preprocesamiento dentro del modelo (predict.py ya aplica preprocess_input)", not sospechosas,
            ", ".join(sospechosas) if sospechosas else "")
    print(f"     Capas de aumento de datos: {', '.join(aumento) if aumento else 'ninguna'} "
          "(normal: no actúan al predecir)")

    # 5. Predicciones distintas para imágenes distintas
    faltan = [ruta for ruta in args.imagenes if not os.path.exists(ruta)]
    if faltan:
        revisar("las 3 imágenes de prueba existen", False,
                f"no encontré {', '.join(faltan)}; pasa otras con --imagenes a.jpg b.jpg c.jpg")
        print(f"\n{resultados.count(True)}/{len(resultados)} comprobaciones OK.")
        sys.exit(1)
    predichas = []
    for ruta in args.imagenes:
        ruta_real, arreglo = cargar_imagen(ruta)
        probabilidades = modelo.predict(arreglo, verbose=0)[0]
        indice = int(np.argmax(probabilidades))
        predichas.append(indice)
        suma = float(np.sum(probabilidades))
        print(f"     {os.path.relpath(ruta_real, BASE_DIR)} -> {clases[indice]} ({probabilidades[indice] * 100:.1f}%), "
              f"suma de probabilidades {suma:.3f}")
    revisar("predice clases distintas para 3 imágenes distintas", len(set(predichas)) > 1,
            "todas dieron la misma clase: revisa si la imagen se preprocesa dos veces" if len(set(predichas)) == 1 else "")

    fallas = resultados.count(False)
    print(f"\n{len(resultados) - fallas}/{len(resultados)} comprobaciones OK.")
    if fallas:
        print("NO reemplaces modelo_lumea101.keras con este archivo todavía.")
    else:
        print("Se puede reemplazar: ver los pasos en REPORTE_SESION.md.")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
