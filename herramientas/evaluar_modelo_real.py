"""
evaluar_modelo_real.py -- Evaluación end-to-end contra la API real (POST
/predecir), no contra el modelo aislado.

Diferencia con evaluar_modelos.py (ese llama predecir_alimento() directo en
Python -- una evaluación "de laboratorio" del modelo puro): este script
prueba el sistema tal como lo usa una persona real, por HTTP, contra un
servidor Flask corriendo de verdad. Eso significa que también evalúa el
umbral de certeza del 70%, la fusión de sopas/dulces que fuerza
confirmación manual, y todo lo que vive en app.py y no solo en el modelo.

Requiere que app.py esté corriendo (python3 app.py) en la URL indicada.

Uso:
    python3 evaluar_modelo_real.py --carpeta fotos_prueba
    python3 evaluar_modelo_real.py --carpeta fotos_prueba --url http://127.0.0.1:5002

La carpeta debe tener una subcarpeta por cada código REAL de clase, por
ejemplo:
    fotos_prueba/natilla/foto1.jpg
    fotos_prueba/mazorcada/foto1.jpg
No se inventan ni se descargan fotos de prueba aquí -- las pone Isabella.

Nota sobre sopas/dulces: cuando la foto real es de ajiaco/sancocho/mondongo
o de uno de los 7 dulces, /predecir NUNCA devuelve ese código específico --
por diseño (ver GRUPOS_CONFUSION en app.py) siempre fuerza confirmación
manual con el código de agrupación visual ("sopas" o "dulces"). Contar eso
como "predicción incorrecta" en la exactitud normal sería engañoso: el
sistema está haciendo exactamente lo que se le pidió. Por eso este script
reporta DOS exactitudes:
  - "estricta": código predicho == código real, tal cual.
  - "ajustada": además cuenta como acierto cuando el sistema forzó
    confirmación manual y el código real está entre las opciones que
    ofreció (es decir, reconoció bien el grupo, aunque no haya "adivinado"
    el plato exacto -- que es justamente lo que NO debe hacer sola la IA
    en estos casos).

Nota sobre 'alimento_codigo' y 'modelo_usado' en la respuesta de
/predecir: antes de este script, esos dos campos solo salían en la
respuesta cuando success=true. Se agregaron también a las dos ramas de
seleccion_manual=true (grupo de confusión / certeza baja) en app.py,
porque sin 'alimento_codigo' ahí no hay forma de saber qué predijo
realmente el ensamble en esos casos, y sin 'modelo_usado' no se puede
hacer el análisis del punto 3 de abajo. Es un campo agregado, no se quitó
ni se cambió nada existente.

Qué hace:
1. Por cada imagen, hace POST /predecir (multipart/form-data, campo
   'file') -- sin 'email', para no ligar estas predicciones de prueba a
   ningún perfil real.
2. Calcula exactitud estricta y ajustada (ver nota arriba), total y por
   clase, y la matriz de confusión (con el código de agrupación 'sopas'/
   'dulces' como una "clase predicha" más, cuando aplica).
3. Para cada predicción INCORRECTA (estricta), usa 'modelo_usado' para
   separar el error en dos categorías, comparando contra en qué modelo
   vive la clase real (clases.json = regional, clases_101.json =
   Food-101, no se solapan):
     - "food101 ganó debiendo ganar el regional" (clase real es de las 35
       regionales, pero respondió el ensamble de 101).
     - "el regional ganó debiendo ganar food101" (clase real es de las
       101 de Food-101, pero respondió el regional).
   Esto es justo el patrón que se sospecha en sopas/dulces: puede que el
   modelo de 101 esté "robando" predicciones con más confianza en fotos
   que en realidad son platos regionales parecidos a algo de Food-101.
4. Guarda todo en Backend/reportes_evaluacion_real/<fecha-hora>/.
"""

import argparse
import json
import os
import sys
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")

# Mismos grupos que GRUPOS_CONFUSION en app.py -- duplicados aquí a
# propósito: este script evalúa la API desde afuera, como una caja negra,
# así que necesita saber por su cuenta qué código de agrupación visual
# corresponde a qué opciones reales, para poder calcular la exactitud
# "ajustada" (ver docstring). Si el día de mañana se agrega un grupo
# nuevo en app.py, hay que reflejarlo aquí también.
GRUPOS_CONFUSION = {
    "sopas": ["ajiaco", "sancocho", "mondongo"],
    "ajiaco": ["ajiaco", "sancocho", "mondongo"],
    "sancocho": ["ajiaco", "sancocho", "mondongo"],
    "mondongo": ["ajiaco", "sancocho", "mondongo"],
    "dulces": ["nucita", "barrilete", "quipitos", "chororamo", "supercoco", "bonbonbum", "chocolatinas"],
}


def cargar_universos_de_clases():
    """Devuelve (set clases regionales, set clases food101), para decidir
    'quién debió ganar' en el análisis de errores por modelo (punto 3)."""
    with open(os.path.join(BASE_DIR, "clases.json"), "r", encoding="utf-8") as f:
        regionales = set(json.load(f))
    with open(os.path.join(BASE_DIR, "clases_101.json"), "r", encoding="utf-8") as f:
        food101 = set(json.load(f))
    return regionales, food101


def listar_imagenes_de_prueba(ruta_carpeta):
    items = []
    for nombre_clase in sorted(os.listdir(ruta_carpeta)):
        ruta_clase = os.path.join(ruta_carpeta, nombre_clase)
        if not os.path.isdir(ruta_clase) or nombre_clase.startswith("."):
            continue
        for raiz, _, archivos in os.walk(ruta_clase):
            for archivo in archivos:
                if archivo.lower().endswith(EXTENSIONES_IMAGEN):
                    items.append((os.path.join(raiz, archivo), nombre_clase))
    return items


def consultar_prediccion(url_base, ruta_archivo):
    """Manda la imagen a POST /predecir y devuelve (alimento_codigo,
    modelo_usado, certeza, seleccion_manual) o levanta una excepción."""
    with open(ruta_archivo, "rb") as f:
        nombre_archivo = os.path.basename(ruta_archivo)
        resp = requests.post(
            f"{url_base}/predecir",
            files={"file": (nombre_archivo, f, "image/jpeg")},
            timeout=60,
        )
    resp.raise_for_status()
    cuerpo = resp.json()
    if "error" in cuerpo:
        raise RuntimeError(cuerpo["error"])
    return {
        "alimento_codigo": cuerpo.get("alimento_codigo"),
        "modelo_usado": cuerpo.get("modelo_usado"),
        "certeza": cuerpo.get("certeza"),
        "seleccion_manual": bool(cuerpo.get("seleccion_manual", False)),
    }


def evaluar(url_base, ruta_carpeta):
    items = listar_imagenes_de_prueba(ruta_carpeta)
    if not items:
        print(f"No se encontraron imágenes en {ruta_carpeta} (¿estructura correcta: <carpeta>/<clase>/*.jpg?)")
        sys.exit(1)

    print(f"Evaluando {len(items)} imágenes contra {url_base}/predecir...")
    resultados, fallidas = [], []

    for i, (ruta_archivo, clase_verdadera) in enumerate(items, start=1):
        if i % 10 == 0 or i == len(items):
            print(f"  [{i}/{len(items)}]")
        try:
            prediccion = consultar_prediccion(url_base, ruta_archivo)
        except Exception as e:
            fallidas.append((ruta_archivo, str(e)))
            continue

        if not prediccion["alimento_codigo"]:
            fallidas.append((ruta_archivo, "La respuesta de /predecir no trajo 'alimento_codigo'."))
            continue

        resultados.append({
            "archivo": ruta_archivo,
            "clase_verdadera": clase_verdadera,
            "clase_predicha": prediccion["alimento_codigo"],
            "certeza": prediccion["certeza"],
            "modelo_usado": prediccion["modelo_usado"],
            "seleccion_manual": prediccion["seleccion_manual"],
        })

    if fallidas:
        print(f"\n{len(fallidas)} imágenes fallaron (revisa que app.py esté corriendo en {url_base}):")
        for ruta, error in fallidas[:10]:
            print(f"  {ruta}: {error}")

    return resultados


def es_acierto_ajustado(fila):
    """True si acertó, contando como acierto también el caso de
    confirmación manual forzada donde la clase real estaba entre las
    opciones ofrecidas -- ver docstring, sección 'ajustada'."""
    if fila["clase_predicha"] == fila["clase_verdadera"]:
        return True
    if fila["seleccion_manual"] and fila["clase_predicha"] in GRUPOS_CONFUSION:
        return fila["clase_verdadera"] in GRUPOS_CONFUSION[fila["clase_predicha"]]
    return False


def generar_reporte(resultados, carpeta_salida):
    os.makedirs(carpeta_salida, exist_ok=True)
    regionales, food101 = cargar_universos_de_clases()

    total = len(resultados)
    aciertos_estrictos = sum(1 for r in resultados if r["clase_predicha"] == r["clase_verdadera"])
    aciertos_ajustados = sum(1 for r in resultados if es_acierto_ajustado(r))

    # --- exactitud por clase (estricta) ---
    por_clase = {}
    for r in resultados:
        clave = r["clase_verdadera"]
        por_clase.setdefault(clave, {"total": 0, "aciertos_estrictos": 0, "aciertos_ajustados": 0})
        por_clase[clave]["total"] += 1
        if r["clase_predicha"] == r["clase_verdadera"]:
            por_clase[clave]["aciertos_estrictos"] += 1
        if es_acierto_ajustado(r):
            por_clase[clave]["aciertos_ajustados"] += 1

    with open(os.path.join(carpeta_salida, "exactitud_por_clase.csv"), "w", encoding="utf-8") as f:
        f.write("clase_verdadera,total,exactitud_estricta,exactitud_ajustada\n")
        for clase, datos in sorted(por_clase.items()):
            f.write(
                f"{clase},{datos['total']},"
                f"{datos['aciertos_estrictos'] / datos['total']:.2%},"
                f"{datos['aciertos_ajustados'] / datos['total']:.2%}\n"
            )

    # --- matriz de confusión (real -> predicho, incluye 'sopas'/'dulces' como predicción) ---
    clases_reales = sorted(set(r["clase_verdadera"] for r in resultados))
    clases_predichas = sorted(set(r["clase_predicha"] for r in resultados))
    matriz = {cr: {cp: 0 for cp in clases_predichas} for cr in clases_reales}
    for r in resultados:
        matriz[r["clase_verdadera"]][r["clase_predicha"]] += 1

    with open(os.path.join(carpeta_salida, "matriz_confusion.csv"), "w", encoding="utf-8") as f:
        f.write("real\\predicho," + ",".join(clases_predichas) + "\n")
        for cr in clases_reales:
            f.write(cr + "," + ",".join(str(matriz[cr][cp]) for cp in clases_predichas) + "\n")

    # --- análisis del punto 3: errores por modelo ganador (solo sobre incorrectas estrictas) ---
    incorrectas = [r for r in resultados if r["clase_predicha"] != r["clase_verdadera"]]
    food101_debio_perder = []  # clase real es regional, pero ganó food101
    regional_debio_perder = []  # clase real es food101, pero ganó el regional
    sin_clasificar = []  # clase real no está en ninguno de los 2 universos conocidos (o modelo_usado ausente)

    for r in incorrectas:
        clase_real = r["clase_verdadera"]
        modelo = r["modelo_usado"]
        if clase_real in regionales and modelo == "food101":
            food101_debio_perder.append(r)
        elif clase_real in food101 and modelo == "regional_26":
            regional_debio_perder.append(r)
        else:
            sin_clasificar.append(r)

    # --- resumen.txt ---
    resumen = [
        f"Evaluación real (vía POST /predecir) -- {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Imágenes evaluadas: {total}",
        "",
        f"Exactitud estricta (código predicho == código real): {aciertos_estrictos / total:.2%}" if total else "Sin datos.",
        f"Exactitud ajustada (cuenta acierto cuando forzó confirmación manual y el real",
        f"estaba entre las opciones ofrecidas): {aciertos_ajustados / total:.2%}" if total else "",
        "",
        f"Predicciones incorrectas (estrictas): {len(incorrectas)}",
        f"  - De esas, clase real era REGIONAL pero ganó el modelo food101"
        f" (error del ensamble, no del modelo regional): {len(food101_debio_perder)}",
        f"  - De esas, clase real era de FOOD-101 pero ganó el modelo regional"
        f" (error del ensamble, no del modelo food101): {len(regional_debio_perder)}",
        f"  - Incorrectas sin clasificar en lo anterior (ambos modelos coinciden en",
        f"    el universo equivocado, o falta 'modelo_usado'): {len(sin_clasificar)}",
        "",
    ]

    if food101_debio_perder:
        resumen.append("Casos donde food101 ganó debiendo ganar el regional (real -> predicho):")
        for r in food101_debio_perder[:20]:
            resumen.append(f"  {r['clase_verdadera']} -> {r['clase_predicha']} (certeza {r['certeza']}%)")
        resumen.append("")

    if regional_debio_perder:
        resumen.append("Casos donde el regional ganó debiendo ganar food101 (real -> predicho):")
        for r in regional_debio_perder[:20]:
            resumen.append(f"  {r['clase_verdadera']} -> {r['clase_predicha']} (certeza {r['certeza']}%)")
        resumen.append("")

    texto_resumen = "\n".join(resumen)
    with open(os.path.join(carpeta_salida, "resumen.txt"), "w", encoding="utf-8") as f:
        f.write(texto_resumen + "\n")

    print("\n" + texto_resumen)
    print(f"Reporte completo guardado en: {carpeta_salida}")


def main():
    parser = argparse.ArgumentParser(description="Evalúa Lumea end-to-end contra la API real (POST /predecir).")
    parser.add_argument("--carpeta", required=True, help="Carpeta con la estructura <clase_real>/*.jpg")
    parser.add_argument("--url", default="http://127.0.0.1:5002", help="URL base de la API (default: http://127.0.0.1:5002)")
    args = parser.parse_args()

    if not os.path.isdir(args.carpeta):
        print(f"No existe la carpeta: {args.carpeta}")
        sys.exit(1)

    try:
        requests.get(args.url, timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"No se pudo conectar a {args.url} -- ¿está corriendo 'python3 app.py'?")
        sys.exit(1)
    except requests.exceptions.RequestException:
        pass  # cualquier respuesta (incluso error) confirma que el server está vivo

    resultados = evaluar(args.url, args.carpeta)
    if not resultados:
        print("No se pudo evaluar ninguna imagen.")
        sys.exit(1)

    carpeta_salida = os.path.join(BASE_DIR, "reportes_evaluacion_real", datetime.now().strftime("%Y%m%d_%H%M%S"))
    generar_reporte(resultados, carpeta_salida)


if __name__ == "__main__":
    main()
