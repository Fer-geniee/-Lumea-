import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import tf_keras as keras 
import json
Base_dir = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(Base_dir, "clases.json"), "r", encoding="utf-8") as f:
        clases = json.load(f)
    print(f"clases.json tiene {len(clases)} clases:")
    print(clases[:10], "..." if len(clases) > 10 else "")
except FileNotFoundError:
    print("No se encontró clases.json junto al modelo.")


class InputLayerCompatible(keras.layers.InputLayer):
    @classmethod
    def from_config(cls, config):
        print("El código abrió en InputLayerCompatible.from_config()")
        config["batch_input_shape"] = config.pop("batch_shape") 
        return super().from_config(config) 
        pass
class RandomFlipCompatible(keras.layers.RandomFlip):
    @classmethod
    def from_config(cls, config):
        print("El código abrió en RandomFlipCompatible.from_config()")
        valor = config.pop("data_format", None)  
        return super().from_config(config) 
        pass

modelo = keras.models.load_model( # Aquí está el error, pero, ¿cómo lo soluciono? 
    os.path.join(Base_dir, "modelo_lumea_comida.h5"),
    compile=False,
)
print ("El código corre sin errores, el modelo se cargó correctamente.")