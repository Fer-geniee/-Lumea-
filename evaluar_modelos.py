"""
evaluar_modelos.py — Evaluación formal de precisión del ensamble (para la
sección 7 de DEFENSA_TECNICA_LUMEA.md: "[completar con el número real de
la evaluación formal, no inventar]").

NO se ha corrido todavía -- prepara el código, a la espera de que Isabella
indique la ruta del conjunto de prueba. Ese conjunto debe ser un
directorio con la MISMA estructura que dataset/ (una carpeta por clase,
imágenes adentro), pero con fotos que el modelo NO haya visto en
entrenamiento -- si se evalúa con las mismas fotos de dataset/, el número
sale inflado y no sirve para nada en la sustentación.

Uso (cuando haya un conjunto de prueba):
    python3 evaluar_modelos.py --dataset /ruta/al/conjunto_de_prueba

Qué hace:
1. Carga los dos modelos EXACTAMENTE como predict.py (mismo import
   tf_keras/keras, mismo preprocesamiento asimétrico -- reutiliza
   predecir_alimento() de predict.py en vez de reimplementar la lógica,
   para que el número evaluado sea el mismo comportamiento que corre en
   producción, no una aproximación aparte que se puede desincronizar).
2. Recorre el conjunto de prueba (carpeta = clase verdadera), corre cada
   imagen por el ensamble, y compara contra la predicción.
3. Genera, en Backend/reportes_evaluacion/<fecha-hora>/:
   - resumen.txt: exactitud general, y los pares de clases más confundidos
     entre sí (las celdas más grandes fuera de la diagonal).
   - reporte_clasificacion.csv: precisión/recall/F1 por clase (sklearn
     classification_report).
   - matriz_confusion_completa.csv + .png: la matriz completa.
   - matriz_confusion_sopas.png: sub-matriz enfocada en
     ajiaco/sancocho/mondongo/sopas -- para ver exactamente qué tanto se
     confunden entre sí (la sospecha que ya se documentó).
   - matriz_confusion_dulces.png: sub-matriz enfocada en los 7 dulces +
     "dulces".

Dependencias nuevas (agregadas a requirements.txt, SOLO para evaluación,
la app en producción no las necesita): scikit-learn, matplotlib, seaborn.
"""

import argparse
import os
import sys
from datetime import datetime

# Reutiliza el ensamble real, no lo reimplementa -- ver docstring. Se importa
# ANTES que sklearn/pandas a propósito: scikit-learn inicializa su propio
# runtime de threads (OpenMP) y, si eso pasa antes de que TensorFlow inicie
# el suyo, en macOS queda un choque que deja colgada (sin usar CPU, sin
# error) la primera llamada real a modelo.predict() -- se comprobó
# directamente: con este orden invertido, una predicción de prueba tardó
# 15+ minutos sin completar; con predict.py importado primero, la misma
# predicción tomó 0.5s.
import predict

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")

# Los dos grupos de confusión conocidos (ver app.py: GRUPOS_CONFUSION).
# Si el conjunto de prueba tiene imágenes de estas clases, se genera una
# sub-matriz aparte, más fácil de leer que la matriz completa de 136 clases.
GRUPO_SOPAS = ["ajiaco", "sancocho", "mondongo", "sopas"]
GRUPO_DULCES = ["nucita", "barrilete", "quipitos", "chororamo", "supercoco", "bonbonbum", "chocolatinas", "dulces"]


def listar_imagenes_de_prueba(ruta_dataset):
    """Recorre ruta_dataset/<clase>/*.jpg y devuelve [(ruta_archivo, clase_verdadera), ...]."""
    items = []
    for nombre_clase in sorted(os.listdir(ruta_dataset)):
        ruta_clase = os.path.join(ruta_dataset, nombre_clase)
        if not os.path.isdir(ruta_clase) or nombre_clase.startswith("."):
            continue
        for raiz, _, archivos in os.walk(ruta_clase):
            for archivo in archivos:
                if archivo.lower().endswith(EXTENSIONES_IMAGEN):
                    items.append((os.path.join(raiz, archivo), nombre_clase))
    return items


def evaluar(ruta_dataset):
    items = listar_imagenes_de_prueba(ruta_dataset)
    if not items:
        print(f"No se encontraron imágenes en {ruta_dataset} (¿estructura correcta: <dataset>/<clase>/*.jpg?)")
        sys.exit(1)

    print(f"Evaluando {len(items)} imágenes de prueba...")
    verdaderas, predichas, certezas, modelos_ganadores, fallidas = [], [], [], [], []

    for i, (ruta_archivo, clase_verdadera) in enumerate(items, start=1):
        if i % 25 == 0 or i == len(items):
            print(f"  [{i}/{len(items)}]")
        try:
            with open(ruta_archivo, "rb") as f:
                img_bytes = f.read()
            resultado = predict.predecir_alimento(img_bytes)
        except Exception as e:
            fallidas.append((ruta_archivo, str(e)))
            continue

        verdaderas.append(clase_verdadera)
        predichas.append(resultado["alimento_codigo"])
        certezas.append(resultado["confianza_porcentaje"])
        modelos_ganadores.append(resultado["modelo_usado"])

    if fallidas:
        print(f"\n{len(fallidas)} imágenes fallaron al procesar (archivo corrupto/formato no soportado):")
        for ruta, error in fallidas[:10]:
            print(f"  {ruta}: {error}")

    return pd.DataFrame({
        "archivo": [item[0] for item in items if item[0] not in {f[0] for f in fallidas}],
        "clase_verdadera": verdaderas,
        "clase_predicha": predichas,
        "certeza": certezas,
        "modelo_ganador": modelos_ganadores,
    })


def generar_reporte(df, carpeta_salida):
    os.makedirs(carpeta_salida, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")  # sin ventana -- solo guardar a archivo
    import matplotlib.pyplot as plt
    import seaborn as sns

    clases = sorted(set(df["clase_verdadera"]) | set(df["clase_predicha"]))
    exactitud = (df["clase_verdadera"] == df["clase_predicha"]).mean()

    # --- reporte de clasificación (precisión/recall/F1 por clase) ---
    reporte = classification_report(
        df["clase_verdadera"], df["clase_predicha"], labels=clases, zero_division=0, output_dict=True,
    )
    pd.DataFrame(reporte).transpose().to_csv(os.path.join(carpeta_salida, "reporte_clasificacion.csv"))

    # --- matriz de confusión completa ---
    matriz = confusion_matrix(df["clase_verdadera"], df["clase_predicha"], labels=clases)
    matriz_df = pd.DataFrame(matriz, index=clases, columns=clases)
    matriz_df.to_csv(os.path.join(carpeta_salida, "matriz_confusion_completa.csv"))

    fig, ax = plt.subplots(figsize=(max(12, len(clases) * 0.35), max(10, len(clases) * 0.35)))
    sns.heatmap(matriz_df, annot=False, cmap="Greens", ax=ax, cbar=True)
    ax.set_xlabel("Predicho")
    ax.set_ylabel("Verdadero")
    ax.set_title(f"Matriz de confusión completa ({len(clases)} clases) -- exactitud general: {exactitud:.1%}")
    plt.xticks(rotation=90, fontsize=6)
    plt.yticks(rotation=0, fontsize=6)
    plt.tight_layout()
    fig.savefig(os.path.join(carpeta_salida, "matriz_confusion_completa.png"), dpi=150)
    plt.close(fig)

    # --- sub-matrices enfocadas: sopas y dulces ---
    for nombre_grupo, codigos_grupo in [("sopas", GRUPO_SOPAS), ("dulces", GRUPO_DULCES)]:
        presentes = [c for c in codigos_grupo if c in clases]
        if len(presentes) < 2:
            continue
        sub_matriz = matriz_df.loc[
            [c for c in presentes if c in matriz_df.index],
            [c for c in presentes if c in matriz_df.columns],
        ]
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(sub_matriz, annot=True, fmt="d", cmap="Oranges", ax=ax, cbar=False)
        ax.set_xlabel("Predicho")
        ax.set_ylabel("Verdadero")
        ax.set_title(f"Confusión dentro del grupo '{nombre_grupo}'")
        plt.tight_layout()
        fig.savefig(os.path.join(carpeta_salida, f"matriz_confusion_{nombre_grupo}.png"), dpi=150)
        plt.close(fig)

    # --- pares más confundidos (fuera de la diagonal) ---
    pares_confundidos = []
    for i, clase_real in enumerate(clases):
        for j, clase_predicha in enumerate(clases):
            if i != j and matriz[i][j] > 0:
                pares_confundidos.append((clase_real, clase_predicha, int(matriz[i][j])))
    pares_confundidos.sort(key=lambda x: -x[2])

    resumen = [
        f"Evaluación del ensamble Lumea -- {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Imágenes evaluadas: {len(df)}",
        f"Exactitud general (ensamble): {exactitud:.2%}",
        "",
        "Top 15 pares de clases más confundidas entre sí (real -> predicho: cantidad):",
    ]
    for clase_real, clase_predicha, cantidad in pares_confundidos[:15]:
        resumen.append(f"  {clase_real} -> {clase_predicha}: {cantidad}")

    texto_resumen = "\n".join(resumen)
    with open(os.path.join(carpeta_salida, "resumen.txt"), "w", encoding="utf-8") as f:
        f.write(texto_resumen + "\n")

    print("\n" + texto_resumen)
    print(f"\nReporte completo guardado en: {carpeta_salida}")


def main():
    parser = argparse.ArgumentParser(description="Evalúa el ensamble Lumea contra un conjunto de prueba.")
    parser.add_argument("--dataset", required=True, help="Carpeta con la estructura <clase>/*.jpg (imágenes NO usadas en entrenamiento)")
    args = parser.parse_args()

    if not os.path.isdir(args.dataset):
        print(f"No existe la carpeta: {args.dataset}")
        sys.exit(1)

    df = evaluar(args.dataset)
    if df.empty:
        print("No se pudo evaluar ninguna imagen.")
        sys.exit(1)

    carpeta_salida = os.path.join(BASE_DIR, "reportes_evaluacion", datetime.now().strftime("%Y%m%d_%H%M%S"))
    generar_reporte(df, carpeta_salida)


if __name__ == "__main__":
    main()
