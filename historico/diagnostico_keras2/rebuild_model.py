import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import h5py
import keras

Base_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_H5_VIEJO = os.path.join(Base_dir, "modelo_lumea_comida.h5")
RUTA_KERAS_NUEVA = os.path.join(Base_dir, "modelo_lumea_comida.keras")

Size = (224, 224)
NUM_CLASES = 26

# === Misma arquitectura de siempre (sin preprocess_input dentro del grafo) ===
data_augmentation = keras.Sequential([
    keras.layers.RandomFlip("horizontal_and_vertical"),
    keras.layers.RandomRotation(0.2),
    keras.layers.RandomZoom(0.2),
], name="sequential_3")

base_model = keras.applications.MobileNetV2(
    input_shape=Size + (3,), include_top=False, weights=None
)

input_layer = keras.layers.Input(shape=Size + (3,), name="input_layer_10")
x = data_augmentation(input_layer)
x = base_model(x, training=False)
x = keras.layers.GlobalAveragePooling2D(name="global_average_pooling2d_3")(x)
output_layer = keras.layers.Dense(NUM_CLASES, activation="softmax", name="dense_3")(x)

modelo = keras.Model(inputs=input_layer, outputs=output_layer)

# === TRASPLANTE MANUAL, capa por capa, sin usar load_weights() ===
# load_weights() con skip_mismatch=True resultó ser poco confiable para este
# modelo con submodelos anidados: aunque los NOMBRES de todas las capas
# coinciden perfecto entre el .h5 y la MobileNetV2 actual (lo confirmamos
# aparte), algunas capas quedaban sin trasplantar o con el orden interno de
# sus pesos desalineado (gamma/beta/moving_mean/moving_variance). Por eso
# aquí leemos cada dataset por SU PROPIO NOMBRE dentro del grupo de cada
# capa, y lo asignamos explícitamente en el orden que la capa actual espera
# -eliminando cualquier ambigüedad de orden o de mecanismo interno de Keras.

capas_transplantadas = []
capas_con_problema = []


def nombre_corto(peso):
    """De 'bn_Conv1/gamma:0' o 'gamma:0' extrae solo 'gamma'."""
    return peso.name.split("/")[-1].split(":")[0]


def transplantar(contenedor, grupo_h5):
    for layer in contenedor.layers:
        if layer.name not in grupo_h5:
            if layer.weights:
                capas_con_problema.append((layer.name, "no está en el .h5"))
            continue

        grupo_capa = grupo_h5[layer.name]

        # Si la capa es a su vez un contenedor (el submodelo MobileNetV2, o
        # el Sequential de aumento de datos), recorrer también sus capas
        # internas, bajando un nivel también dentro del .h5.
        if hasattr(layer, "layers") and layer.layers:
            transplantar(layer, grupo_capa)
            continue

        if not layer.weights:
            continue  # capas sin pesos (ReLU, Add, etc.) no necesitan nada

        nuevos_pesos = []
        ok = True
        for peso in layer.weights:
            clave = nombre_corto(peso)
            fuente = grupo_capa
            # Formato legacy: a veces el nombre de la capa se anida dos
            # veces (grupo_capa/nombre_capa/clave) en vez de una sola
            # (grupo_capa/clave). Probamos ambos antes de rendirnos.
            if clave not in fuente and layer.name in fuente:
                fuente = fuente[layer.name]
            if clave not in fuente:
                capas_con_problema.append((layer.name, f"falta dataset '{clave}'"))
                ok = False
                break
            nuevos_pesos.append(fuente[clave][()])

        if ok:
            layer.set_weights(nuevos_pesos)
            capas_transplantadas.append(layer.name)


with h5py.File(RUTA_H5_VIEJO, "r") as f:
    transplantar(modelo, f["model_weights"])

print(f"Capas trasplantadas exitosamente: {len(capas_transplantadas)}")
print(f"Capas con problema: {len(capas_con_problema)}")
if capas_con_problema:
    for nombre, motivo in capas_con_problema[:20]:
        print(f"  - {nombre}: {motivo}")

print("Forma de salida:", modelo.output_shape)

modelo.save(RUTA_KERAS_NUEVA)
print(f"Modelo limpio guardado en: {RUTA_KERAS_NUEVA}")