import requests

# Cambia esto por la ruta de CUALQUIER imagen de comida en tu computador.
# No necesita estar en la carpeta del proyecto ni tener un nombre especial.
RUTA_IMAGEN = "/Users/isabfero.o./Python_proyects/Lumea/Backend/prueba .jpg"
URL = "http://127.0.0.1:5000/predecir"


def probar_prediccion():
    with open(RUTA_IMAGEN, "rb") as f:
        archivos = {"file": f}
        respuesta = requests.post(URL, files=archivos)

    print("Código de estado HTTP:", respuesta.status_code)
    print("Respuesta JSON:")
    print(respuesta.json())


def probar_historial():
    respuesta = requests.get("http://127.0.0.1:5000/historial")
    print("Código de estado HTTP:", respuesta.status_code)
    print(respuesta.json())


def probar_alimentos():
    respuesta = requests.get("http://127.0.0.1:5000/alimentos")
    print("Código de estado HTTP:", respuesta.status_code)
    print(respuesta.json())


if __name__ == "__main__":
    print("=== Probando /predecir ===")
    probar_prediccion()
    print("\n=== Probando /historial ===")
    probar_historial()
    print("\n=== Probando /alimentos ===")
    probar_alimentos()