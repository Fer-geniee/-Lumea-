import requests

# Cambia esto por la ruta de CUALQUIER imagen de comida en tu computador.
# No necesita estar en la carpeta del proyecto ni tener un nombre especial.
RUTA_IMAGEN = "/Users/isabfero.o./Downloads/prueba.jpeg"

BASE_URL = "http://127.0.0.1:5002"

# Correo reservado para pruebas: todo lo que este script guarda (perfil,
# estado de ánimo, historial, puntos) queda ligado a él, para poder
# identificarlo y borrarlo después sin tocar datos de usuarios reales.
EMAIL_PRUEBA = "__test_api__@lumea.test"

# User-Agent explícito: si un firewall/software de seguridad está
# bloqueando específicamente el User-Agent por defecto de la librería
# requests ("python-requests/x.x"), identificarnos como curl lo evita.
HEADERS = {"User-Agent": "curl/8.7.1"}

resultados = []


def verificar(nombre, respuesta, esperado=200):
    ok = respuesta.status_code == esperado
    resultados.append((nombre, ok))
    print(f"[{'OK' if ok else 'FALLA'}] {nombre} -> HTTP {respuesta.status_code}")
    try:
        print("   ", respuesta.json())
    except ValueError:
        print("    (respuesta no es JSON)", respuesta.text[:200])
    return respuesta


def probar_perfil():
    verificar("POST /perfil", requests.post(f"{BASE_URL}/perfil", headers=HEADERS, json={
        "nombre": "Prueba test_api", "email": EMAIL_PRUEBA, "edad": 15, "genero": "otro",
        "peso": 55.0, "altura": 160, "objetivo": "comer_balanceado",
    }))
    verificar("GET /perfil", requests.get(f"{BASE_URL}/perfil", headers=HEADERS, params={"email": EMAIL_PRUEBA}))


def probar_estado_animo():
    verificar("POST /estado-animo", requests.post(
        f"{BASE_URL}/estado-animo", headers=HEADERS, json={"email": EMAIL_PRUEBA, "estado": "bien"},
    ))
    verificar("GET /estado-animo", requests.get(f"{BASE_URL}/estado-animo", headers=HEADERS, params={"email": EMAIL_PRUEBA}))


def probar_prediccion():
    with open(RUTA_IMAGEN, "rb") as f:
        verificar("POST /predecir", requests.post(
            f"{BASE_URL}/predecir", headers=HEADERS, files={"file": f}, data={"email": EMAIL_PRUEBA},
        ))


def probar_confirmar_alimento():
    verificar("POST /confirmar-alimento", requests.post(
        f"{BASE_URL}/confirmar-alimento", headers=HEADERS, json={"alimento_codigo": "banano", "email": EMAIL_PRUEBA},
    ))
    # Los códigos de agrupación visual nunca deben aceptarse (ver GRUPOS_CONFUSION en app.py)
    verificar("POST /confirmar-alimento con 'sopas' (debe rechazar)", requests.post(
        f"{BASE_URL}/confirmar-alimento", headers=HEADERS, json={"alimento_codigo": "sopas", "email": EMAIL_PRUEBA},
    ), esperado=400)


def probar_historial():
    verificar("GET /historial", requests.get(f"{BASE_URL}/historial", headers=HEADERS, params={"email": EMAIL_PRUEBA}))


def probar_alimentos():
    respuesta = requests.get(f"{BASE_URL}/alimentos", headers=HEADERS)
    ok = respuesta.status_code == 200
    resultados.append(("GET /alimentos", ok))
    # La lista completa es larga (141+ alimentos): solo se muestra el conteo.
    cuerpo = respuesta.json() if ok else {}
    print(f"[{'OK' if ok else 'FALLA'}] GET /alimentos -> HTTP {respuesta.status_code}, claves: {list(cuerpo.keys())}")


if __name__ == "__main__":
    probar_perfil()
    probar_estado_animo()
    probar_prediccion()
    probar_confirmar_alimento()
    probar_historial()
    probar_alimentos()

    fallas = [nombre for nombre, ok in resultados if not ok]
    print(f"\n{len(resultados) - len(fallas)}/{len(resultados)} pruebas OK.")
    if fallas:
        print("Fallaron:", ", ".join(fallas))
    print(f"\nNota: los datos de prueba quedan ligados a {EMAIL_PRUEBA} en MySQL -- bórralos si no los quieres.")
