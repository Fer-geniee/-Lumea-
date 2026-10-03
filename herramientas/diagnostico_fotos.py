"""
diagnostico_fotos.py  ·  ¿Qué "piensa" cada modelo de una foto?  (Lumea)

Para cada foto muestra el TOP-3 de cada modelo (regional y Food-101) y qué
habría respondido Lumea con tres reglas de decisión distintas:
  - "mayor"     : la regla vieja (gana el modelo con más confianza)
  - "cascada"   : decide el regional si su confianza >= umbral (regla nueva)
  - "regional"  : solo el modelo regional

USO (desde la carpeta Backend, con el mismo entorno de app.py):
    1. Crea carpetas con el NOMBRE DE LA CLASE REAL y mete ahí fotos nuevas:
           fotos_prueba/banano/foto1.jpg
           fotos_prueba/arepa/foto2.jpg
           fotos_prueba/pizza/foto3.jpg    <- (clase de Food-101, en inglés)
    2. python3 diagnostico_fotos.py fotos_prueba
       (o una sola foto:  python3 diagnostico_fotos.py mi_banano.jpg)

No toca la base de datos ni el servidor: solo carga los modelos (tarda ~20 s).
"""
import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import io
import os
import sys

import numpy as np

import predict  # carga los dos modelos exactamente como lo hace app.py

EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
UMBRALES_A_PROBAR = (0.3, 0.4, 0.5, 0.6, 0.7)


def top3(modelo, clases, arreglo):
    p = modelo.predict(arreglo, verbose=0)[0]
    idx = np.argsort(p)[::-1][:3]
    return [(clases[i], float(p[i])) for i in idx]


def analizar(ruta):
    from PIL import Image
    with open(ruta, "rb") as f:
        img = Image.open(io.BytesIO(f.read())).convert("RGB").resize((224, 224))
    arr = np.expand_dims(np.array(img, dtype=np.float32), 0)
    reg = top3(predict.modelo_26, predict.classes_26, arr)                        # crudo 0-255
    arr101 = predict.tf.keras.applications.mobilenet_v2.preprocess_input(arr.copy())
    f101 = top3(predict.modelo_101, predict.classes_101, arr101)                  # [-1, 1]
    return reg, f101


def decidir(reg, f101, regla, umbral=0.5):
    (c26, p26), (c101, p101) = reg[0], f101[0]
    if regla == "regional":
        return c26
    if regla == "mayor":
        return c26 if p26 >= p101 else c101
    return c26 if (p26 >= umbral or p26 >= p101) else c101   # cascada


def listar(entrada):
    """Devuelve [(ruta, clase_real o None)]."""
    if os.path.isfile(entrada):
        return [(entrada, None)]
    fotos = []
    for raiz, _, archivos in os.walk(entrada):
        real = os.path.basename(raiz) if os.path.abspath(raiz) != os.path.abspath(entrada) else None
        # Acepta carpetas como "fotos_prueba_banano": la clase es lo que va después del prefijo
        for prefijo in ("fotos_prueba_", "fotos_", "prueba_"):
            if real and real.startswith(prefijo):
                real = real[len(prefijo):]
        fotos += [(os.path.join(raiz, a), real) for a in sorted(archivos) if a.lower().endswith(EXT)]
    return fotos


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    fotos = listar(sys.argv[1])
    if not fotos:
        sys.exit("No encontré fotos.")
    resultados = []
    for ruta, real in fotos:
        reg, f101 = analizar(ruta)
        resultados.append((ruta, real, reg, f101))
        print(f"\n📷 {ruta}" + (f"   (real: {real})" if real else ""))
        print("   Regional :", " | ".join(f"{c} {p*100:4.1f}%" for c, p in reg))
        print("   Food-101 :", " | ".join(f"{c} {p*100:4.1f}%" for c, p in f101))
        print(f"   → regla vieja (mayor): {decidir(reg, f101, 'mayor')}"
              f"   · cascada {predict.UMBRAL_REGIONAL:.1f} (la de app.py): {decidir(reg, f101, 'cascada', predict.UMBRAL_REGIONAL)}"
              f"   · solo regional: {decidir(reg, f101, 'regional')}")

    con_real = [r for r in resultados if r[1]]
    if not con_real:
        return
    n = len(con_real)
    print("\n================ RESUMEN (aciertos top-1) ================")
    print(f"Fotos con clase real: {n}")
    def acc(regla, u=0.5):
        return sum(decidir(reg, f101, regla, u) == real for _, real, reg, f101 in con_real)
    print(f"  Regla vieja (gana el mayor) : {acc('mayor')}/{n}")
    for u in UMBRALES_A_PROBAR:
        print(f"  Cascada, umbral {u:.1f}        : {acc('cascada', u)}/{n}")
    print(f"  Solo regional               : {acc('regional')}/{n}")
    top3_reg = sum(real in [c for c, _ in reg] for _, real, reg, _ in con_real)
    print(f"  Regional: la clase real aparece en su TOP-3 en {top3_reg}/{n} fotos")
    print("\nElige el umbral con más aciertos y úsalo así:  LUMEA_UMBRAL_REGIONAL=<umbral> python3 app.py")
    print("Con pocas fotos, un empate o 1 foto de diferencia NO es evidencia: no sobreinterpretes.")


if __name__ == "__main__":
    main()