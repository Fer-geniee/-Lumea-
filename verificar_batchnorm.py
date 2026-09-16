import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import keras
import numpy as np

Base_dir = os.path.dirname(os.path.abspath(__file__))
modelo = keras.models.load_model(
    os.path.join(Base_dir, "modelo_lumea_comida.keras"), compile=False
)


def encontrar_capas_bn(contenedor):
    """Recorre capas normales Y capas anidadas (como el submodelo MobileNetV2
    dentro del modelo grande) buscando todas las BatchNormalization."""
    encontradas = []
    for layer in contenedor.layers:
        if isinstance(layer, keras.layers.BatchNormalization):
            encontradas.append(layer)
        if hasattr(layer, "layers"):
            encontradas.extend(encontrar_capas_bn(layer))
    return encontradas


capas_bn = encontrar_capas_bn(modelo)
print(f"Total de capas BatchNormalization encontradas: {len(capas_bn)}")

capas_con_varianza_negativa = []
capas_con_forma_rara = []

for layer in capas_bn:
    pesos = layer.get_weights()
    if len(pesos) < 4:
        capas_con_forma_rara.append((layer.name, len(pesos)))
        continue
    moving_variance = pesos[3]
    if (moving_variance < 0).any():
        capas_con_varianza_negativa.append(layer.name)

print(f"Capas con varianza negativa (imposible si el trasplante fue correcto): {len(capas_con_varianza_negativa)}")
if capas_con_varianza_negativa:
    print("Primeras 10:", capas_con_varianza_negativa[:10])

if capas_con_forma_rara:
    print(f"Capas BatchNorm con menos de 4 arrays de pesos (sospechoso): {len(capas_con_forma_rara)}")
    print("Primeras 10:", capas_con_forma_rara[:10])

# Revisión extra: la PRIMERA capa BatchNorm de la red (la más temprana) es la
# más importante -- si su NaN nace ahí, se explica todo lo demás.
if capas_bn:
    primera = capas_bn[0]
    print()
    print(f"Primera capa BatchNorm de la red: '{primera.name}'")
    pesos_primera = primera.get_weights()
    for i, nombre_peso in enumerate(["gamma", "beta", "moving_mean", "moving_variance"]):
        if i < len(pesos_primera):
            arr = pesos_primera[i]
            print(f"  {nombre_peso}: min={arr.min():.4f} max={arr.max():.4f} ¿NaN?={np.isnan(arr).any()}")