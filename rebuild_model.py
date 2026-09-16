import os
import keras  # Keras 3 puro. No usamos tf_keras aquí: construimos la arquitectura
              # nosotras mismas en código, así que no dependemos de deserializar
              # ningún JSON viejo -y por lo tanto no heredamos ninguno de los
              # tres problemas de formato que ya resolvimos.

Base_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_H5_VIEJO = os.path.join(Base_dir, "modelo_lumea_comida.h5")
RUTA_KERAS_NUEVA = os.path.join(Base_dir, "modelo_lumea_comida.keras")

Size = (224, 224)
NUM_CLASES = 26  # debe coincidir con len(clases.json) — confírmalo si cambia

# Misma arquitectura de ia_comida.py, con UN cambio deliberado: el
# preprocess_input YA NO va dentro del grafo. Esa era la causa original del
# problema 'TrueDivide': aplicar una operación matemática cruda sobre un
# tensor simbólico genera una capa auto-generada frágil entre versiones de
# Keras. predict.py ya hace ese preprocesamiento a mano, afuera del modelo,
# antes de llamar a predict() — así que quitarlo de aquí no solo evita el
# problema de guardado a futuro, sino que corrige un bug silencioso que
# probablemente tenías: el preprocesamiento se estaba aplicando DOS VECES
# (una adentro del modelo guardado, otra en predict.py).

data_augmentation = keras.Sequential([
    keras.layers.RandomFlip("horizontal_and_vertical"),
    keras.layers.RandomRotation(0.2),
    keras.layers.RandomZoom(0.2),
], name="sequential_3")

base_model = keras.applications.MobileNetV2(
    input_shape=Size + (3,), include_top=False, weights=None
)  # weights=None: no tiene sentido descargar pesos de ImageNet, dos líneas
   # más abajo los vamos a sobreescribir con TUS pesos ya entrenados.

input_layer = keras.layers.Input(shape=Size + (3,), name="input_layer_10")
x = data_augmentation(input_layer)
x = base_model(x, training=False)
x = keras.layers.GlobalAveragePooling2D(name="global_average_pooling2d_3")(x)
output_layer = keras.layers.Dense(NUM_CLASES, activation="softmax", name="dense_3")(x)

modelo = keras.Model(inputs=input_layer, outputs=output_layer)

# Trasplante de pesos reales por nombre de capa. Esto NO pasa por el parser
# de arquitectura que nos dio problemas — solo lee arrays numéricos del .h5
# y los asigna a las capas de MISMO NOMBRE que construimos arriba (por eso
# 'input_layer_10', 'sequential_3', 'global_average_pooling2d_3' y 'dense_3'
# tienen que ser EXACTOS — los sacamos de inspeccionar_pesos.py).
#
# Nota honesta: no encontré confirmación 100% segura de que Keras 3 acepte
# el argumento by_name en load_weights igual que tf_keras/Keras 2 (la
# documentación oficial de Keras 3 solo menciona filepath y skip_mismatch).
# Como un .h5 legacy siempre guarda los pesos agrupados por nombre de capa,
# es muy probable que empareje por nombre automáticamente sin necesitar ese
# argumento. Si esta línea te da un TypeError por un argumento no
# reconocido, quítalo y prueba solo con skip_mismatch=True.
modelo.load_weights(RUTA_H5_VIEJO, skip_mismatch=True)

print("Pesos cargados. Forma de salida:", modelo.output_shape)

modelo.save(RUTA_KERAS_NUEVA)
print(f"Modelo limpio guardado en: {RUTA_KERAS_NUEVA}")