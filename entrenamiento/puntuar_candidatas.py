"""
puntuar_candidatas.py -- Le pregunta al modelo actual qué tanto se parece
cada foto candidata a su clase, para ordenar la galería de revisión de la
MÁS SOSPECHOSA a la más segura.

    python3 puntuar_candidatas.py                  # todas las clases de dataset_candidatos/
    python3 puntuar_candidatas.py --clases pera    # solo esas

Usa el modelo regional (35 clases, modelo_lumea_comida.keras) tal como lo
carga predict.py (sin modificar predict.py): la imagen se reduce a 224x224
y se le pasa cruda, igual que en /predecir. Para cada foto guarda en
dataset_candidatos/<clase>/puntajes.csv:

- prob_clase: probabilidad que el modelo le da a la clase de la carpeta
  (0 = "no se parece nada", 1 = "seguro que es esto");
- clase_predicha y prob_predicha: lo que el modelo cree que es.

OJO al leer los puntajes: es el MISMO modelo que se quiere mejorar, así que
se equivoca justo donde el dataset es flojo. En las frutas, por ejemplo,
aprendió con fotos sobre fondo blanco (Fruits-360), así que una pera real
en una mesa puede sacar puntaje bajo aunque sea una pera perfecta. El
puntaje sirve para ORDENAR (lo raro primero), no para decidir: la que
decide es la persona que revisa.

Las fotos ya puntuadas no se vuelven a calcular (se reconoce el archivo por
nombre y tamaño).
"""
import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import csv
import os
import sys

import numpy as np
from PIL import Image

import predict  # carga los modelos (tarda unos segundos)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATOS = os.path.join(BASE_DIR, "dataset_candidatos")
LOTE = 32


def cargar(ruta):
    with Image.open(ruta) as im:
        return np.asarray(im.convert("RGB").resize((224, 224)), dtype=np.float32)


def puntuar_clase(clase):
    carpeta = os.path.join(CANDIDATOS, clase)
    ruta_csv = os.path.join(carpeta, "puntajes.csv")
    if clase not in predict.classes_26:
        print(f"  {clase}: no es una clase del modelo regional; se salta")
        return
    indice = predict.classes_26.index(clase)
    previos = {}
    if os.path.exists(ruta_csv):
        with open(ruta_csv, encoding="utf-8") as f:
            previos = {(fila["archivo"], fila["bytes"]): fila for fila in csv.DictReader(f)}
    archivos = sorted(a for a in os.listdir(carpeta) if a.endswith(".jpg"))
    filas, pendientes = [], []
    for archivo in archivos:
        clave = (archivo, str(os.path.getsize(os.path.join(carpeta, archivo))))
        if clave in previos:
            filas.append(previos[clave])
        else:
            pendientes.append(archivo)
    for inicio in range(0, len(pendientes), LOTE):
        grupo = pendientes[inicio:inicio + LOTE]
        lote = np.stack([cargar(os.path.join(carpeta, a)) for a in grupo])
        probabilidades = predict.modelo_26.predict(lote, verbose=0)
        for archivo, p in zip(grupo, probabilidades):
            mejor = int(np.argmax(p))
            filas.append({
                "archivo": archivo,
                "bytes": str(os.path.getsize(os.path.join(carpeta, archivo))),
                "prob_clase": f"{float(p[indice]):.4f}",
                "clase_predicha": predict.classes_26[mejor],
                "prob_predicha": f"{float(p[mejor]):.4f}",
            })
    filas.sort(key=lambda f: f["archivo"])
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["archivo", "bytes", "prob_clase", "clase_predicha", "prob_predicha"])
        escritor.writeheader()
        escritor.writerows(filas)
    acierta = sum(1 for f in filas if f["clase_predicha"] == clase)
    print(f"  {clase}: {len(filas)} fotos ({len(pendientes)} nuevas); el modelo reconoce la clase en {acierta}")


def main():
    parser = argparse.ArgumentParser(description="Puntúa las candidatas con el modelo actual.")
    parser.add_argument("--clases", nargs="*", help="Solo estas clases")
    args = parser.parse_args()
    clases = args.clases or sorted(
        c for c in os.listdir(CANDIDATOS)
        if os.path.isdir(os.path.join(CANDIDATOS, c)) and not c.startswith(("_", "."))
    )
    for clase in clases:
        if not os.path.isdir(os.path.join(CANDIDATOS, clase)):
            sys.exit(f"No existe dataset_candidatos/{clase}/")
        puntuar_clase(clase)


if __name__ == "__main__":
    main()
