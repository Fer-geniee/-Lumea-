import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import keras
import json

Base_dir = os.path.dirname(os.path.abspath(__file__))
modelo = keras.models.load_model(
    os.path.join(Base_dir, "modelo_lumea_comida.h5"), compile=False
)

print("Forma de salida de la última capa:", modelo.output_shape)
print("-> Número de clases que este modelo realmente predice:", modelo.output_shape[-1])

try:
    with open(os.path.join(Base_dir, "clases.json"), "r", encoding="utf-8") as f:
        clases = json.load(f)
    print(f"clases.json tiene {len(clases)} clases:")
    print(clases[:10], "..." if len(clases) > 10 else "")
except FileNotFoundError:
    print("No se encontró clases.json junto al modelo.")
