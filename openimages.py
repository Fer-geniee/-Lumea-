"""
openimages.py -- Fuente Open Images (Google) para recolectar_candidatos.py.

Open Images V7 es un dataset público de ~9 millones de fotos de Flickr con
licencia CC BY 2.0 (según Open Images), anotadas por personas. Aquí se usa:

- Recuadros (bounding boxes) para las 8 frutas: dicen dónde está la fruta y
  qué tan grande sale. Se eligen fotos donde la fruta ocupa buena parte de
  la imagen, no es un dibujo (IsDepiction=0) y no hay otra de nuestras
  frutas más grande que ella.
- Etiquetas de imagen VERIFICADAS por personas (Confidence=1) para platos:
  Tamale, Humita, Pamonha y Hallaca (-> tamal: todos son masa envuelta en
  hoja, como los envueltos), Buñuelo, Chicharrón, Hornado, Fritada,
  Tostones, huevos, arroz blanco, pollo frito, pescado frito, etc.
  Para "Guinea pig" (cuy) se exige además una etiqueta de comida, porque
  casi todas las fotos son del animal vivo.

Los archivos de anotaciones son enormes (el de recuadros de entrenamiento
pesa 2,3 GB y el de etiquetas 2,7 GB), así que NO se guardan: se leen en
streaming y solo se guardan las filas de nuestras clases, en
dataset_candidatos/_openimages/ (unos pocos MB). Eso se hace una sola vez:

    python3 openimages.py --indice

Las fotos se descargan del espejo público oficial de Open Images en S3
(open-images-dataset.s3.amazonaws.com), el mismo que usa el descargador
oficial.
"""

import argparse
import csv
import os
import random
import shutil
import subprocess
import sys
import tempfile

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE_DIR, "dataset_candidatos", "_openimages")
AGENTE = "Lumea/1.0 (proyecto escolar Fedesoft, Colombia; https://github.com/Fer-geniee/-Lumea-)"

URL_BASE = "https://storage.googleapis.com/openimages"
RECUADROS = {
    "train": f"{URL_BASE}/v6/oidv6-train-annotations-bbox.csv",
    "validation": f"{URL_BASE}/v5/validation-annotations-bbox.csv",
    "test": f"{URL_BASE}/v5/test-annotations-bbox.csv",
}
ETIQUETAS = {
    "train": f"{URL_BASE}/v7/oidv7-train-annotations-human-imagelabels.csv",
    "validation": f"{URL_BASE}/v7/oidv7-val-annotations-human-imagelabels.csv",
    "test": f"{URL_BASE}/v7/oidv7-test-annotations-human-imagelabels.csv",
}
# Etiquetas automáticas (las puso un modelo de Google, con una confianza de
# 0 a 1). Para los platos colombianos casi no hay etiquetas verificadas por
# personas (0 para Tamale, Hornado, Chicharrón...), así que se usan estas,
# con confianza >= UMBRAL_MAQUINA. Se equivocan más: por eso la galería.
MAQUINA = {
    "train": f"{URL_BASE}/v7/oidv7-train-annotations-machine-imagelabels.csv",
    "validation": f"{URL_BASE}/v7/oidv7-val-annotations-machine-imagelabels.csv",
    "test": f"{URL_BASE}/v7/oidv7-test-annotations-machine-imagelabels.csv",
}
UMBRAL_MAQUINA = 0.7
INFO_IMAGENES = {  # URL original en Flickr, autor y licencia (solo el subconjunto con recuadros)
    "train": f"{URL_BASE}/2018_04/train/train-images-boxable-with-rotation.csv",
    "validation": f"{URL_BASE}/2018_04/validation/validation-images-with-rotation.csv",
    "test": f"{URL_BASE}/2018_04/test/test-images-with-rotation.csv",
}
URL_IMAGEN = "https://open-images-dataset.s3.amazonaws.com/{split}/{id}.jpg"
LICENCIA = "CC BY 2.0 (según Open Images)"

# Frutas: clase Lumea -> id de Open Images (con recuadros).
FRUTAS = {
    "manzana": "/m/014j1m", "banano": "/m/09qck", "fresa": "/m/07fbm7", "naranja": "/m/0cyhj_",
    "uva": "/m/0388q", "pera": "/m/061_f", "mango": "/m/0fldg", "pina": "/m/0fp6w",
}
# Platos: clase Lumea -> ids de Open Images (etiquetas de imagen verificadas).
PLATOS = {
    "tamal": ["/m/0h6_1", "/m/09crqz", "/m/0dpryk", "/m/05nm7r"],  # Tamale, Humita, Pamonha, Hallaca
    "bunuelos": ["/m/091rs3"],                                     # Buñuelo
    "chicharron": ["/m/067wdb"],                                   # Chicharrón
    "hornado": ["/m/0b6fq40"],                                     # Hornado
    "frito": ["/m/0b6h2fq"],                                       # Fritada
    "patacon": ["/m/043ty0w"],                                     # Tostones
    "huevo": ["/m/01r22b", "/m/09x374", "/m/02dmw4"],              # Fried egg, Boiled egg, Scrambled eggs
    "arroz": ["/m/02vdjb", "/m/0g9vs81"],                          # White rice, Steamed rice
    "pollo_frito": ["/m/01px4b"],                                  # Fried chicken
    "pescado": ["/m/056ywg"],                                      # Fried fish
    "obleas": ["/m/0yx_tdd"],                                      # Oblea
    "pandebono": ["/m/02xgbk"],                                    # Pandebono
    "pinchos": ["/m/08fjdx", "/m/04t8p9"],                         # Anticucho, Brochette
    "cuy": ["/m/0gy7v"],                                           # Guinea pig (+ etiqueta de comida)
}
NOMBRES = {
    "/m/0h6_1": "Tamale", "/m/09crqz": "Humita", "/m/0dpryk": "Pamonha", "/m/05nm7r": "Hallaca",
    "/m/091rs3": "Buñuelo", "/m/067wdb": "Chicharrón", "/m/0b6fq40": "Hornado", "/m/0b6h2fq": "Fritada",
    "/m/043ty0w": "Tostones", "/m/01r22b": "Fried egg", "/m/09x374": "Boiled egg", "/m/02dmw4": "Scrambled eggs",
    "/m/02vdjb": "White rice", "/m/0g9vs81": "Steamed rice", "/m/01px4b": "Fried chicken", "/m/056ywg": "Fried fish",
    "/m/0yx_tdd": "Oblea", "/m/02xgbk": "Pandebono", "/m/08fjdx": "Anticucho", "/m/04t8p9": "Brochette",
    "/m/0gy7v": "Guinea pig",
}
NOMBRES.update({mid: nombre for nombre, mid in [
    ("Apple", "/m/014j1m"), ("Banana", "/m/09qck"), ("Strawberry", "/m/07fbm7"), ("Orange", "/m/0cyhj_"),
    ("Grape", "/m/0388q"), ("Pear", "/m/061_f"), ("Mango", "/m/0fldg"), ("Pineapple", "/m/0fp6w")]})
COMIDA = {"/m/02wbm", "/m/02q08p0", "/m/04scj", "/m/01ykh", "/m/0dxn2"}  # Food, Dish, Meat, Cuisine, Roasting
COMIDA_MAQUINA = {"/m/02q08p0", "/m/04scj", "/m/0dxn2"}  # sin Food ni Cuisine: están en millones de fotos
AREA_MINIMA_FRUTA = 0.08  # la fruta más grande debe ocupar al menos el 8% de la foto

sesion = requests.Session()
sesion.headers["User-Agent"] = AGENTE


def _lineas_prefiltradas(url, textos):
    """curl | grep -F: deja pasar solo las líneas que contienen alguno de los
    textos (más el encabezado). Para el archivo de 7 GB, leerlo línea por línea
    en Python tardaba unas 6 horas; así tarda lo que tarda la descarga."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("ImageID,\n" + "\n".join(textos) + "\n")
        patrones = f.name
    curl = subprocess.Popen(["curl", "-s", "-A", AGENTE, url], stdout=subprocess.PIPE)
    grep = subprocess.Popen(["grep", "-F", "-f", patrones], stdin=curl.stdout, stdout=subprocess.PIPE, text=True)
    curl.stdout.close()
    try:
        for linea in grep.stdout:
            yield linea.rstrip("\n")
    finally:
        grep.wait(); curl.wait(); os.remove(patrones)
        if curl.returncode != 0:
            raise RuntimeError(f"curl falló ({curl.returncode}) bajando {url}")


def _filtrar_en_streaming(url, conservar, salida, prefiltro=None):
    """Lee un CSV remoto línea por línea y guarda solo las filas donde
    conservar(fila) es verdadero. Devuelve cuántas guardó. `prefiltro`
    (textos fijos) acelera mucho los archivos gigantes, si hay curl y grep."""
    guardadas = 0
    temporal = salida + ".parcial"
    usar_grep = prefiltro and shutil.which("curl") and shutil.which("grep")
    with sesion.get(url, stream=True, timeout=120) if not usar_grep else _Nada() as r, \
            open(temporal, "w", newline="", encoding="utf-8") as f:
        if usar_grep:
            lineas = _lineas_prefiltradas(url, prefiltro)
        else:
            r.raise_for_status()
            # Trozos de 1 MB: con el valor por defecto (512 bytes) leer 2 GB tarda más de una hora.
            lineas = (l.decode("utf-8") for l in r.iter_lines(chunk_size=1 << 20) if l)
        lector = csv.reader(lineas)
        encabezado = next(lector)
        escritor = csv.writer(f)
        escritor.writerow(encabezado)
        indices = {nombre: i for i, nombre in enumerate(encabezado)}
        for fila in lector:
            if conservar(fila, indices):
                escritor.writerow(fila)
                guardadas += 1
    os.replace(temporal, salida)  # solo existe completo: si se corta, se vuelve a bajar
    return guardadas


class _Nada:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def construir_indice():
    """Filtra cada archivo remoto una sola vez: si el filtrado ya existe
    (completo), no se vuelve a bajar."""
    os.makedirs(CACHE, exist_ok=True)
    mids_frutas = set(FRUTAS.values())
    mids_platos = {m for lista in PLATOS.values() for m in lista}
    tareas = []
    for split in ("validation", "test", "train"):
        tareas.append((f"recuadros_{split}.csv", RECUADROS[split],
                       lambda fila, i: fila[i["LabelName"]] in mids_frutas, None))
        tareas.append((f"etiquetas_{split}.csv", ETIQUETAS[split],
                       lambda fila, i: fila[i["Confidence"]] == "1"
                       and (fila[i["LabelName"]] in mids_platos or fila[i["LabelName"]] in COMIDA), None))
        mids_maquina = sorted(mids_platos | COMIDA_MAQUINA)
        tareas.append((f"maquina_{split}.csv", MAQUINA[split],
                       lambda fila, i: (fila[i["LabelName"]] in mids_platos or fila[i["LabelName"]] in COMIDA_MAQUINA)
                       and float(fila[i["Confidence"]] or 0) >= UMBRAL_MAQUINA,
                       [f",{m}," for m in mids_maquina]))
    for nombre, url, conservar, prefiltro in tareas:
        salida = os.path.join(CACHE, nombre)
        if os.path.exists(salida):
            print(f"{nombre}: ya estaba")
            continue
        print(f"{nombre}: filtrando {url} ...", flush=True)
        print(f"   {_filtrar_en_streaming(url, conservar, salida, prefiltro)} filas", flush=True)
    print("Índice listo en", CACHE)


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        yield from csv.DictReader(f)


def candidatas_frutas():
    """{clase: [(split, image_id, area_maxima, nombre_etiqueta), ...]} ordenadas
    de mayor a menor área de la fruta."""
    clase_de = {mid: clase for clase, mid in FRUTAS.items()}
    por_imagen = {}  # (split, id) -> {mid: area máxima}
    for split in RECUADROS:
        ruta = os.path.join(CACHE, f"recuadros_{split}.csv")
        if not os.path.exists(ruta):
            continue
        for fila in _leer(ruta):
            if fila.get("IsDepiction") == "1":
                continue
            area = (float(fila["XMax"]) - float(fila["XMin"])) * (float(fila["YMax"]) - float(fila["YMin"]))
            areas = por_imagen.setdefault((split, fila["ImageID"]), {})
            areas[fila["LabelName"]] = max(areas.get(fila["LabelName"], 0.0), area)
    resultado = {clase: [] for clase in FRUTAS}
    for (split, image_id), areas in por_imagen.items():
        mid, area = max(areas.items(), key=lambda par: par[1])  # la fruta más grande de la foto
        if area >= AREA_MINIMA_FRUTA:
            resultado[clase_de[mid]].append((split, image_id, area, NOMBRES[mid]))
    for lista in resultado.values():
        lista.sort(key=lambda c: -c[2])
    return resultado


def candidatas_platos():
    """{clase: [(split, image_id, None, nombre_etiqueta), ...]} en orden aleatorio fijo."""
    etiquetas = {}  # (split, id) -> set(mid)
    for split in ETIQUETAS:
        for nombre in (f"etiquetas_{split}.csv", f"maquina_{split}.csv"):  # verificadas + automáticas
            ruta = os.path.join(CACHE, nombre)
            if not os.path.exists(ruta):
                continue
            for fila in _leer(ruta):
                etiquetas.setdefault((split, fila["ImageID"]), set()).add(fila["LabelName"])
    resultado = {clase: [] for clase in PLATOS}
    for (split, image_id), mids in etiquetas.items():
        for clase, mids_clase in PLATOS.items():
            encontrados = [m for m in mids_clase if m in mids]
            if not encontrados:
                continue
            if clase == "cuy" and not (mids & (COMIDA | COMIDA_MAQUINA)):
                continue
            resultado[clase].append((split, image_id, None, NOMBRES[encontrados[0]]))
    aleatorio = random.Random(26)
    for lista in resultado.values():
        lista.sort()
        aleatorio.shuffle(lista)
    return resultado


def resultados_para(clase, maximo):
    """Generador en el formato de recolectar_candidatos.py."""
    if clase in FRUTAS:
        lista = candidatas_frutas()[clase]
    elif clase in PLATOS:
        lista = candidatas_platos()[clase]
    else:
        return
    for split, image_id, area, etiqueta in lista[:maximo]:
        detalle = f"{etiqueta}, fruta ocupa {area:.0%} de la foto" if area else f"marcada como {etiqueta}"
        yield {
            "fuente": "openimages",
            "id": image_id,
            "titulo": f"Open Images {split} {image_id}: {detalle}",
            "ancho": 0, "alto": 0,
            "url_imagen": URL_IMAGEN.format(split=split, id=image_id),
            "url_pagina": f"https://storage.googleapis.com/openimages/web/visualizer/index.html?set={split}&id={image_id}",
            "autor": "",
            "licencia": LICENCIA,
            "url_licencia": "https://creativecommons.org/licenses/by/2.0/",
        }


def main():
    parser = argparse.ArgumentParser(description="Índice de Open Images para recolectar_candidatos.py")
    parser.add_argument("--indice", action="store_true", help="Descarga en streaming y filtra las anotaciones (una vez)")
    parser.add_argument("--resumen", action="store_true", help="Cuántas candidatas hay por clase en el índice")
    args = parser.parse_args()
    if args.indice:
        construir_indice()
    if args.resumen or not args.indice:
        for nombre, datos in (("frutas", candidatas_frutas()), ("platos", candidatas_platos())):
            for clase, lista in sorted(datos.items()):
                print(f"{nombre:7s} {clase:14s} {len(lista):6d}")


if __name__ == "__main__":
    sys.exit(main())
