import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import h5py
import keras

Base_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_H5 = os.path.join(Base_dir, "modelo_lumea_comida.h5")

# === Nombres que existen DENTRO del .h5 original, bajo el submodelo MobileNetV2 ===
with h5py.File(RUTA_H5, "r") as f:
    grupo_mobilenet = f["model_weights"]["mobilenetv2_1.00_224"]
    nombres_en_h5 = set(grupo_mobilenet.keys())

# === Nombres que genera una MobileNetV2 fresca en tu Keras actual ===
base_model = keras.applications.MobileNetV2(
    input_shape=(224, 224, 3), include_top=False, weights=None
)
nombres_en_keras_actual = set(layer.name for layer in base_model.layers)

# === Comparación ===
solo_en_h5 = nombres_en_h5 - nombres_en_keras_actual
solo_en_keras = nombres_en_keras_actual - nombres_en_h5
en_ambos = nombres_en_h5 & nombres_en_keras_actual

print(f"Nombres en el .h5 original: {len(nombres_en_h5)}")
print(f"Nombres en la MobileNetV2 actual: {len(nombres_en_keras_actual)}")
print(f"Coinciden en ambos: {len(en_ambos)}")
print()
print(f"Solo están en el .h5 (Keras actual no los tiene con ese nombre): {len(solo_en_h5)}")
if solo_en_h5:
    print(sorted(solo_en_h5)[:15])
print()
print(f"Solo están en la MobileNetV2 actual (el .h5 no los tiene con ese nombre): {len(solo_en_keras)}")
if solo_en_keras:
    print(sorted(solo_en_keras)[:15])

print()
print("Específicamente, sobre las dos capas problemáticas:")
for nombre in ["block_8_depthwise_BN", "block_9_expand_BN", "bn_Conv1"]:
    print(f"  '{nombre}' -> ¿está en el .h5? {nombre in nombres_en_h5} | ¿está en Keras actual? {nombre in nombres_en_keras_actual}")