import requests

# Cambia esto por la ruta de CUALQUIER imagen de comida en tu computador.
# No necesita estar en la carpeta del proyecto ni tener un nombre especial.
RUTA_IMAGEN = "/Users/isabfero.o./Python_proyects/Lumea/Backend/prueba.jpeg"

URL = "http://127.0.0.1:5001/predecir"


def probar_prediccion():
    # User-Agent explícito: si un firewall/software de seguridad está
    # bloqueando específicamente el User-Agent por defecto de la librería
    # requests ("python-requests/x.x"), identificarnos como curl lo evita.
    headers = {"User-Agent": "curl/8.7.1"}
    with open(RUTA_IMAGEN, "rb") as f:
        archivos = {"file": f}
        respuesta = requests.post(URL, files=archivos, headers=headers)

    print("Código de estado HTTP:", respuesta.status_code)
    print("Respuesta JSON:")
    print(respuesta.json())


def probar_historial():
    respuesta = requests.get("http://127.0.0.1:5001/historial")
    print("Código de estado HTTP:", respuesta.status_code)
    print(respuesta.json())


def probar_alimentos():
    respuesta = requests.get("http://127.0.0.1:5001/alimentos")
    print("Código de estado HTTP:", respuesta.status_code)
    print(respuesta.json())


if __name__ == "__main__":
    print("=== Probando /predecir ===")
    probar_prediccion()
    print("\n=== Probando /historial ===")
    probar_historial()
    print("\n=== Probando /alimentos ===")
    probar_alimentos()