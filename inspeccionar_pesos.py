import os
import h5py

Base_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_H5 = os.path.join(Base_dir, "modelo_lumea_comida.h5")

with h5py.File(RUTA_H5, "r") as f:
    nombres_capas_con_pesos = list(f["model_weights"].keys())

print(f"Total de capas con pesos guardados: {len(nombres_capas_con_pesos)}")
print()
print("Últimas 10 (normalmente aquí está tu capa Dense final, después de todo MobileNetV2):")
for nombre in nombres_capas_con_pesos[-10:]:
    print(" -", nombre)