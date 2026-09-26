"""
limpiar_dataset.py -- Encuentra fotos repetidas en dataset/ antes de entrenar.

Por qué existe: el dataset tenía miles de copias exactas (37,6% el 23 sep
2026) y, como ia_comida.py reparte las fotos al azar entre entrenamiento
y validación, muchas fotos de validación tenían su gemela en
entrenamiento. Eso infla la exactitud (ver DEFENSA_TECNICA_LUMEA.md,
sección 6, "La fuga de datos").

Busca dos tipos de repetición, siempre dentro de la misma clase:
1. Duplicados exactos: el mismo archivo byte por byte (hash MD5 del
   contenido), aunque tenga otro nombre (p. ej. "Chicharrón copy 2.jpg").
2. Casi-duplicados: la misma foto redimensionada, recomprimida, o dos
   fotogramas casi iguales de un video (las frutas de Fruits-360 son eso:
   una fruta girando). Se detectan con un hash perceptual (pHash): una
   "huella" de 64 bits de cómo se ve la imagen en tamaño pequeño. Dos
   fotos parecidas tienen huellas con pocos bits distintos (distancia de
   Hamming). --umbral es el máximo de bits distintos para considerarlas
   la misma foto.

   El pHash trabaja en escala de grises, y con un objeto pequeño sobre
   fondo blanco la huella queda dominada por el fondo: en la primera
   prueba marcó como "casi iguales" una botella de Coca-Cola y una de
   Postobón rosada, y un mango y una manzana verde. Por eso además se
   exige que el COLOR sea parecido (colorhash: distribución de tonos,
   --umbral-color). En la calibración (26 sep 2026), todos los falsos
   positivos tenían distancia de color 6-7 y los casi-duplicados reales
   0-4; el valor por defecto (3) prefiere no apartar ninguna foto
   distinta aunque se escapen unos pocos casi-duplicados.

Cuál se queda y cuál se aparta: se recorren las fotos de cada clase
empezando por la de mayor resolución (y, entre iguales, la que NO se
llama "copy"/"copia"). Una foto se aparta solo si se parece a una que YA
se decidió conservar. Así no hay "encadenamiento": en un video de una
fruta girando, el fotograma 1 se parece al 2, el 2 al 3, etc., pero el 1
no se parece al 30 -- con encadenamiento se perdería todo el video menos
una foto; con este método se conservan los fotogramas que de verdad son
distintos.

Modos:
    python3 limpiar_dataset.py                      # --reporte (por defecto): no mueve nada
    python3 limpiar_dataset.py --umbral 4           # otro umbral
    python3 limpiar_dataset.py --aplicar            # mueve (nunca borra)

--aplicar mueve cada foto apartada a dataset_removidos/<clase>/...,
AL LADO de dataset/ (no adentro: si quedara adentro, Keras la tomaría
como una clase más) y escribe un manifiesto CSV con origen y destino de
cada archivo, para poder deshacerlo.

Además reporta (sin mover nunca nada de eso):
- Casi-duplicados ENTRE clases distintas: la misma foto en dos clases
  suele ser una foto mal etiquetada. Hay que revisarla a mano.
- Archivos que no se pudieron abrir como imagen.
- Clases que quedarían con menos de --minimo fotos únicas.
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime

import imagehash
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")
UMBRALES_SENSIBILIDAD = [0, 2, 4, 6, 8, 10]
PATRON_COPIA = re.compile(r"\bcopy\b|\bcopia\b|\(\d+\)", re.IGNORECASE)


def leer_imagenes(ruta_dataset):
    """Devuelve (imagenes, ilegibles). Cada imagen es un dict con su clase
    (la carpeta de primer nivel, que es la etiqueta de entrenamiento),
    ruta relativa, MD5, pHash y colorhash (enteros de 64 y 42 bits) y
    área en píxeles."""
    imagenes, ilegibles = [], []
    clases = sorted(
        c for c in os.listdir(ruta_dataset)
        if os.path.isdir(os.path.join(ruta_dataset, c)) and not c.startswith(".")
    )
    for clase in clases:
        for raiz, _, archivos in os.walk(os.path.join(ruta_dataset, clase)):
            for archivo in sorted(archivos):
                if not archivo.lower().endswith(EXTENSIONES_IMAGEN):
                    continue
                ruta = os.path.join(raiz, archivo)
                relativa = os.path.relpath(ruta, ruta_dataset)
                try:
                    with open(ruta, "rb") as f:
                        contenido = f.read()
                    with Image.open(ruta) as im:
                        im.load()
                        ancho, alto = im.size
                        rgb = im.convert("RGB")
                        phash = int(str(imagehash.phash(rgb)), 16)
                        color = int(str(imagehash.colorhash(rgb, binbits=3)), 16)
                except Exception as e:
                    ilegibles.append((relativa, str(e)))
                    continue
                imagenes.append({
                    "clase": clase,
                    "relativa": relativa,
                    "md5": hashlib.md5(contenido).hexdigest(),
                    "phash": phash,
                    "color": color,
                    "area": ancho * alto,
                })
    return imagenes, ilegibles


def distancias(hash_objetivo, hashes):
    """Bits distintos (distancia de Hamming) entre un pHash y una lista de pHash."""
    if len(hashes) == 0:
        return np.array([], dtype=np.int64)
    return np.bitwise_count(np.uint64(hash_objetivo) ^ hashes).astype(np.int64)


def orden_de_preferencia(imagen):
    """Primero la de mayor resolución; entre iguales, la que no es "copy";
    después el nombre más corto (suele ser el original)."""
    nombre = os.path.basename(imagen["relativa"])
    return (-imagen["area"], bool(PATRON_COPIA.search(nombre)), len(nombre), imagen["relativa"])


def parecidas(imagen, candidatas_phash, candidatas_color, umbral, umbral_color):
    """Índices de las candidatas que se parecen a `imagen` en forma (pHash)
    Y en color, más sus distancias de pHash."""
    d_forma = distancias(imagen["phash"], candidatas_phash)
    d_color = distancias(imagen["color"], candidatas_color)
    return np.nonzero((d_forma <= umbral) & (d_color <= umbral_color))[0], d_forma


def decidir_por_clase(imagenes_clase, umbral, umbral_color):
    """Aplica el método sin encadenamiento a una clase. Devuelve la lista
    de movimientos propuestos: (imagen, tipo, gemela_conservada, distancia)."""
    conservadas, hashes_conservados, colores_conservados = [], [], []
    # md5 de TODA foto ya procesada -> la foto conservada que la representa.
    # Incluye las apartadas: si A se aparta por parecerse a K, una copia
    # exacta de A también es "exacto" (con gemela K), no "casi".
    md5_vistos = {}
    movimientos = []
    for imagen in sorted(imagenes_clase, key=orden_de_preferencia):
        if imagen["md5"] in md5_vistos:
            movimientos.append((imagen, "exacto", md5_vistos[imagen["md5"]], 0))
            continue
        indices, d_forma = parecidas(
            imagen,
            np.array(hashes_conservados, dtype=np.uint64),
            np.array(colores_conservados, dtype=np.uint64),
            umbral, umbral_color,
        )
        if len(indices):
            indice = int(indices[d_forma[indices].argmin()])
            movimientos.append((imagen, "casi", conservadas[indice], int(d_forma[indice])))
            md5_vistos[imagen["md5"]] = conservadas[indice]
            continue
        conservadas.append(imagen)
        hashes_conservados.append(imagen["phash"])
        colores_conservados.append(imagen["color"])
        md5_vistos[imagen["md5"]] = imagen
    return movimientos


def agrupar_por_clase(imagenes):
    por_clase = {}
    for imagen in imagenes:
        por_clase.setdefault(imagen["clase"], []).append(imagen)
    return por_clase


def pares_entre_clases(imagenes, umbral, umbral_color):
    """Pares de fotos casi iguales (o idénticas) que están en clases distintas."""
    hashes = np.array([im["phash"] for im in imagenes], dtype=np.uint64)
    colores = np.array([im["color"] for im in imagenes], dtype=np.uint64)
    clases = np.array([im["clase"] for im in imagenes])
    pares = []
    for i, imagen in enumerate(imagenes):
        indices, d_forma = parecidas(imagen, hashes[i + 1:], colores[i + 1:], umbral, umbral_color)
        for j in indices:
            if clases[i + 1 + j] != imagen["clase"]:
                otra = imagenes[i + 1 + j]
                pares.append((imagen["relativa"], otra["relativa"], int(d_forma[j])))
    return sorted(pares, key=lambda p: p[2])


def escribir_csv(ruta, encabezado, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(encabezado)
        escritor.writerows(filas)


def generar_reporte(ruta_dataset, imagenes, ilegibles, umbral, umbral_color, minimo):
    por_clase = agrupar_por_clase(imagenes)
    movimientos = {clase: decidir_por_clase(lista, umbral, umbral_color) for clase, lista in por_clase.items()}
    entre_clases = pares_entre_clases(imagenes, umbral, umbral_color)

    carpeta = os.path.join(BASE_DIR, "reportes_limpieza", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(carpeta, exist_ok=True)

    lineas = [
        f"Reporte de limpieza -- {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Dataset: {os.path.abspath(ruta_dataset)}",
        f"Umbral pHash: {umbral} bits de 64   |   Umbral color: {umbral_color}   |   Mínimo por clase: {minimo}",
        "",
        f"{'clase':30s} {'antes':>6s} {'exactos':>8s} {'casi':>6s} {'después':>8s}",
        "-" * 62,
    ]
    total_antes = total_exactos = total_casi = 0
    clases_bajo_minimo = []
    for clase in sorted(por_clase):
        antes = len(por_clase[clase])
        exactos = sum(1 for m in movimientos[clase] if m[1] == "exacto")
        casi = sum(1 for m in movimientos[clase] if m[1] == "casi")
        despues = antes - exactos - casi
        marca = "  <-- MENOS DE %d" % minimo if despues < minimo else ""
        if despues < minimo:
            clases_bajo_minimo.append((clase, despues))
        lineas.append(f"{clase:30s} {antes:6d} {exactos:8d} {casi:6d} {despues:8d}{marca}")
        total_antes += antes
        total_exactos += exactos
        total_casi += casi
    total_despues = total_antes - total_exactos - total_casi
    lineas += [
        "-" * 62,
        f"{'TOTAL':30s} {total_antes:6d} {total_exactos:8d} {total_casi:6d} {total_despues:8d}",
        "",
        f"Se apartarían {total_exactos + total_casi} fotos ({(total_exactos + total_casi) / total_antes:.1%}): "
        f"{total_exactos} duplicados exactos + {total_casi} casi-duplicados.",
        f"Clases que quedarían con menos de {minimo}: "
        + (", ".join(f"{c} ({n})" for c, n in clases_bajo_minimo) if clases_bajo_minimo else "ninguna"),
        "",
        f"Sensibilidad al umbral pHash, con umbral de color {umbral_color} "
        "(cuántas fotos se apartarían en total, exactas incluidas):",
    ]
    filas_sensibilidad = []
    for u in UMBRALES_SENSIBILIDAD:
        propuestas = {c: decidir_por_clase(lista, u, umbral_color) for c, lista in por_clase.items()}
        n = sum(len(m) for m in propuestas.values())
        bajo = [c for c, lista in por_clase.items() if len(lista) - len(propuestas[c]) < minimo]
        filas_sensibilidad.append((u, n, len(bajo), " ".join(sorted(bajo))))
        lineas.append(f"  umbral {u:2d}: {n:5d} fotos ({n / total_antes:5.1%})   clases bajo {minimo}: {len(bajo)}")
    lineas += [
        "",
        f"Pares casi iguales ENTRE clases distintas (posibles fotos mal etiquetadas, "
        f"NO se mueven, revisar a mano): {len(entre_clases)}",
    ]
    for a, b, d in entre_clases[:15]:
        lineas.append(f"  [{d}] {a}  <->  {b}")
    if len(entre_clases) > 15:
        lineas.append(f"  ... ({len(entre_clases) - 15} más en entre_clases.csv)")
    lineas += ["", f"Archivos que no se pudieron abrir como imagen: {len(ilegibles)}"]
    for relativa, error in ilegibles[:10]:
        lineas.append(f"  {relativa}: {error}")
    lineas += ["", f"Detalle archivo por archivo: {carpeta}"]

    escribir_csv(
        os.path.join(carpeta, "movimientos_propuestos.csv"),
        ["clase", "archivo_a_apartar", "tipo", "gemela_que_se_conserva", "distancia_bits"],
        [
            (clase, im["relativa"], tipo, gemela["relativa"], d)
            for clase in sorted(movimientos)
            for im, tipo, gemela, d in movimientos[clase]
        ],
    )
    escribir_csv(os.path.join(carpeta, "entre_clases.csv"), ["archivo_1", "archivo_2", "distancia_bits"], entre_clases)
    escribir_csv(os.path.join(carpeta, "sensibilidad.csv"),
                 ["umbral", "fotos_a_apartar", "clases_bajo_minimo", "cuales"], filas_sensibilidad)
    escribir_csv(os.path.join(carpeta, "ilegibles.csv"), ["archivo", "error"], ilegibles)

    texto = "\n".join(lineas)
    with open(os.path.join(carpeta, "resumen.txt"), "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(texto)
    return movimientos


def aplicar(ruta_dataset, movimientos):
    """Mueve (nunca borra) cada foto apartada a dataset_removidos/, al lado
    de dataset/, conservando la ruta relativa, y escribe un manifiesto."""
    ruta_dataset = os.path.abspath(ruta_dataset)
    destino_base = os.path.join(os.path.dirname(ruta_dataset), "dataset_removidos")
    if destino_base.startswith(ruta_dataset + os.sep):
        sys.exit("dataset_removidos no puede quedar dentro del dataset.")

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    filas = []
    for clase in sorted(movimientos):
        for imagen, tipo, gemela, d in movimientos[clase]:
            origen = os.path.join(ruta_dataset, imagen["relativa"])
            destino = os.path.join(destino_base, imagen["relativa"])
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            if os.path.exists(destino):
                raiz, ext = os.path.splitext(destino)
                destino = f"{raiz}__{marca}{ext}"
            shutil.move(origen, destino)
            filas.append((origen, destino, tipo, os.path.join(ruta_dataset, gemela["relativa"]), d))

    manifiesto = os.path.join(destino_base, f"manifiesto_{marca}.csv")
    escribir_csv(manifiesto, ["origen", "destino", "tipo", "gemela_conservada", "distancia_bits"], filas)
    print(f"\nMovidas {len(filas)} fotos a {destino_base}")
    print(f"Manifiesto (para deshacer): {manifiesto}")


def main():
    parser = argparse.ArgumentParser(description="Encuentra y aparta fotos repetidas del dataset.")
    parser.add_argument("--dataset", default=os.path.join(BASE_DIR, "dataset"), help="Carpeta del dataset (por defecto Backend/dataset)")
    parser.add_argument("--umbral", type=int, default=5, help="Máximo de bits distintos de pHash para considerar dos fotos casi iguales (0-64, por defecto 5)")
    parser.add_argument("--umbral-color", type=int, default=3, help="Máximo de bits distintos de colorhash; además de la forma, el color debe parecerse (por defecto 3)")
    parser.add_argument("--minimo", type=int, default=100, help="Marca las clases que queden con menos fotos únicas que esto (por defecto 100)")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--reporte", action="store_true", help="Solo muestra qué se movería (modo por defecto)")
    modo.add_argument("--aplicar", action="store_true", help="Mueve las fotos apartadas a dataset_removidos/ (nunca borra)")
    args = parser.parse_args()

    if not os.path.isdir(args.dataset):
        sys.exit(f"No existe la carpeta: {args.dataset}")

    print("Leyendo imágenes y calculando huellas (puede tardar un par de minutos)...\n")
    imagenes, ilegibles = leer_imagenes(args.dataset)
    movimientos = generar_reporte(args.dataset, imagenes, ilegibles, args.umbral, args.umbral_color, args.minimo)

    if args.aplicar:
        aplicar(args.dataset, movimientos)
    else:
        print("\nModo reporte: no se movió ningún archivo. Para aplicar: --aplicar")


if __name__ == "__main__":
    main()
