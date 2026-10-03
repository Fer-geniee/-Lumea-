import os
import h5py
import numpy as np

Base_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_H5 = os.path.join(Base_dir, "modelo_lumea_comida.h5")

total_arrays = 0
arrays_con_problema = []


def revisar(nombre, objeto):
    global total_arrays
    if isinstance(objeto, h5py.Dataset):
        total_arrays += 1
        datos = objeto[()]
        if not np.issubdtype(datos.dtype, np.number):
            return
        tiene_nan = np.isnan(datos).any()
        tiene_inf = np.isinf(datos).any()
        if tiene_nan or tiene_inf:
            arrays_con_problema.append((nombre, datos.shape, tiene_nan, tiene_inf))


with h5py.File(RUTA_H5, "r") as f:
    f["model_weights"].visititems(revisar)

print(f"Total de arrays de pesos revisados: {total_arrays}")
print(f"Arrays con NaN o Inf: {len(arrays_con_problema)}")
print()
if arrays_con_problema:
    print("Detalle (primeros 20):")
    for nombre, forma, nan, inf in arrays_con_problema[:20]:
        print(f" - {nombre} | forma={forma} | NaN={nan} | Inf={inf}")
else:
    print("Ningún array de pesos en el .h5 original tiene NaN ni Inf.")
    print("=> El archivo original está limpio. El problema se introdujo en el trasplante (reconstruir_modelo.py).")