import os
import h5py

Base_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_H5 = os.path.join(Base_dir, "modelo_lumea_comida.h5")


def explorar(grupo, prefijo=""):
    for key in grupo.keys():
        item = grupo[key]
        if isinstance(item, h5py.Group):
            attrs = dict(item.attrs)
            print(f"{prefijo}[GRUPO] {key}  (attrs: {list(attrs.keys())})")
            if "weight_names" in attrs:
                print(f"{prefijo}    weight_names = {attrs['weight_names']}")
            explorar(item, prefijo + "    ")
        else:
            print(f"{prefijo}[DATASET] {key}  forma={item.shape}")


with h5py.File(RUTA_H5, "r") as f:
    print("=== Estructura completa de 'bn_Conv1' ===")
    explorar(f["model_weights"]["mobilenetv2_1.00_224"]["bn_Conv1"])

    print()
    print("=== Estructura completa de 'block_8_depthwise_BN' ===")
    explorar(f["model_weights"]["mobilenetv2_1.00_224"]["block_8_depthwise_BN"])