"""
resumen_prueba_campo.py  ·  Mide tu modelo con FOTOS NUEVAS (prueba de campo)

QUÉ HACE
    Lee un CSV donde tú anotas, foto por foto, qué era el plato de verdad y qué
    respondió Lumea, y calcula las métricas que un jurado puede creerte:
      1. Exactitud global con su intervalo de confianza de 95 % (Wilson).
      2. Exactitud por plato (¿cuáles son tus platos fuertes para la demo?).
      3. Exactitud según qué modelo ganó (regional vs food101).
      4. Calibración: ¿la "certeza" que muestra la app significa algo?
      5. "Daño": cuántas veces la app GUARDÓ AUTOMÁTICAMENTE (certeza >= 70)
         un alimento equivocado.
      6. Las confusiones más frecuentes.

CÓMO SE USA
    1. Toma >= 30 fotos NUEVAS (que NO estén en el dataset), con la cámara del
       Mac y con la luz de la feria. Pasa cada una por la app.
    2. Anota en prueba_campo.csv (una fila por foto):
           foto,real,predicho,confianza,modelo_usado
           foto01.jpg,ajiaco,ajiaco,82.3,regional_26
           foto02.jpg,arepa,empanada,64.0,food101
       * `real` y `predicho` = el CÓDIGO del alimento (alimento_codigo).
       * `confianza` = el número de "certeza" (0-100).
       * `modelo_usado` = campo de la respuesta JSON (si no lo ves, déjalo vacío).
    3. Ejecuta:   python3 resumen_prueba_campo.py prueba_campo.csv

ADVERTENCIA HONESTA
    Con pocas fotos el intervalo es ANCHO (con 40 fotos y ~80 % de acierto mide ~ +-12 puntos).
    Dilo así. Un intervalo ancho y honesto vale más que una cifra bonita.
"""
import csv
import math
import sys
from collections import Counter, defaultdict

UMBRAL_GUARDADO = 70.0     # el mismo umbral de app.py
Z95 = 1.96


def wilson(k, n, z=Z95):
    """Intervalo de Wilson para una proporción (mejor que la aproximación normal con n pequeño)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    mitad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centro - mitad), min(1.0, centro + mitad))


def pct(x):
    return f"{100 * x:5.1f} %"


def main(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if (r.get("real") or "").strip()]
    if not filas:
        sys.exit("El CSV no tiene filas con la columna 'real' rellena.")

    for r in filas:
        r["real"] = r["real"].strip().lower()
        r["predicho"] = (r.get("predicho") or "").strip().lower()
        r["ok"] = r["real"] == r["predicho"]
        try:
            r["conf"] = float(r.get("confianza") or "nan")
        except ValueError:
            r["conf"] = float("nan")
        r["modelo"] = (r.get("modelo_usado") or "sin dato").strip()

    n = len(filas)
    k = sum(r["ok"] for r in filas)
    lo, hi = wilson(k, n)
    print(f"\n=== 1. EXACTITUD GLOBAL ===\n{k}/{n} = {pct(k / n)}   IC95 (Wilson): [{pct(lo)}, {pct(hi)}]")
    if n < 30:
        print("   ⚠ Menos de 30 fotos: el intervalo es muy ancho; toma más fotos.")

    print("\n=== 2. POR PLATO (real) ===")
    por_real = defaultdict(lambda: [0, 0])
    for r in filas:
        por_real[r["real"]][1] += 1
        por_real[r["real"]][0] += r["ok"]
    for plato, (a, t) in sorted(por_real.items(), key=lambda kv: (-kv[1][0] / kv[1][1], kv[0])):
        marca = "  <- candidato fuerte para la demo" if t >= 3 and a / t >= 0.8 else ("  <- débil" if a / t < 0.5 else "")
        print(f"  {plato:<28} {a}/{t}  {pct(a / t)}{marca}")

    print("\n=== 3. POR MODELO GANADOR ===")
    por_mod = defaultdict(lambda: [0, 0])
    for r in filas:
        por_mod[r["modelo"]][1] += 1
        por_mod[r["modelo"]][0] += r["ok"]
    for m, (a, t) in por_mod.items():
        print(f"  {m:<14} {a}/{t}  {pct(a / t)}")
    print("  (Si un modelo gana seguido y acierta poco, sus confianzas no son comparables: ver guía §9.2)")

    print("\n=== 4. CALIBRACIÓN: ¿la certeza mostrada significa algo? ===")
    bandas = [(0, 50), (50, 70), (70, 85), (85, 95), (95, 100.01)]
    for a, b in bandas:
        sel = [r for r in filas if a <= r["conf"] < b]
        if sel:
            acc = sum(r["ok"] for r in sel) / len(sel)
            print(f"  certeza {a:>3.0f}-{min(b, 100):>3.0f} %   n={len(sel):>3}   acierto real {pct(acc)}")
    print("  Una app bien calibrada acierta ~ igual que la certeza que declara.")

    print("\n=== 5. DAÑO: guardados automáticamente pero EQUIVOCADOS (certeza >= 70) ===")
    guardados = [r for r in filas if r["conf"] >= UMBRAL_GUARDADO]
    malos = [r for r in guardados if not r["ok"]]
    print(f"  {len(malos)} de {len(guardados)} guardados automáticamente estaban mal"
          + (f"  ({pct(len(malos) / len(guardados))})" if guardados else ""))
    for r in malos:
        print(f"    {r.get('foto', '?')}: real={r['real']}  app={r['predicho']} ({r['conf']:.0f} %, {r['modelo']})")

    print("\n=== 6. CONFUSIONES MÁS FRECUENTES (real -> app) ===")
    conf = Counter((r["real"], r["predicho"]) for r in filas if not r["ok"])
    for (real, pred), c in conf.most_common(8):
        print(f"  {real:<24} -> {pred:<24} x{c}")
    if not conf:
        print("  Ninguna: ¡pero comprueba que tus fotos sean realmente nuevas y variadas!")
    print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 resumen_prueba_campo.py prueba_campo.csv")
    main(sys.argv[1])