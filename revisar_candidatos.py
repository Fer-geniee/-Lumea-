"""
revisar_candidatos.py -- Galería para revisar a mano las fotos candidatas
que dejó recolectar_candidatos.py en dataset_candidatos/, y (solo cuando
se pide) pasar las aprobadas a dataset/.

    python3 revisar_candidatos.py            # abre la galería en http://127.0.0.1:5055
    python3 revisar_candidatos.py --resumen  # cuántas hay aceptadas/rechazadas/pendientes
    python3 revisar_candidatos.py --aplicar  # pasa las ACEPTADAS a dataset/<clase>/

Cómo se revisa: en cada clase se ven arriba unas fotos del dataset (para
recordar cómo es la clase) y abajo todas las candidatas.
- Clic en una foto: la marca como RECHAZADA (borde rojo). Otro clic la
  vuelve ACEPTADA (borde verde).
- Botón "Aceptar todas las pendientes": marca como aceptadas las que no
  tocaste. Así solo hay que hacer clic en las malas.
- Doble clic: abre la foto en grande.
Cada clic se guarda al instante en dataset_candidatos/<clase>/decisiones.csv:
se puede cerrar y seguir otro día.

Sugerencias de rechazo (borde naranja punteado, al final de cada clase):
antes de la revisión, Claude miró todas las candidatas en miniatura y
marcó las que claramente no sirven (otro alimento, un local por fuera,
un paquete, un dibujo...), con el motivo. Están en
dataset_candidatos/<clase>/sugerencias.csv. NO están rechazadas: cuentan
como pendientes hasta que las decidas. "Aceptar todas las pendientes" no
las toca; para ellas está el botón "Rechazar las sugeridas que no tocaste".

Qué rechazar: que no sea ese alimento, que tenga varios alimentos y el de
la clase no sea el principal, dibujos o montajes, marca de agua o texto
grande encima, fotos muy oscuras o borrosas, y la misma foto que otra ya
vista (el script quita las repetidas exactas, pero no todas).

--aplicar mueve (nunca borra) cada foto aceptada a dataset/<clase>/ con el
prefijo "web_", salvo que ya haya una igual en el dataset, y agrega su
autor y licencia a dataset_fuentes_web.csv (la atribución que piden las
licencias CC BY). Las rechazadas y pendientes se quedan donde están.
"""

import argparse
import csv
import html
import os
import random
import shutil
import sys
import webbrowser
from datetime import datetime

from flask import Flask, abort, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(BASE_DIR, "dataset")
CANDIDATOS = os.path.join(BASE_DIR, "dataset_candidatos")
FUENTES_WEB = os.path.join(BASE_DIR, "dataset_fuentes_web.csv")
PUERTO = 5055
ESTADOS = ("aceptada", "rechazada")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")


# --------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------

def clases_con_candidatas():
    if not os.path.isdir(CANDIDATOS):
        return []
    return sorted(c for c in os.listdir(CANDIDATOS)
                  if os.path.isdir(os.path.join(CANDIDATOS, c)) and not c.startswith(("_", ".")))


def candidatas(clase):
    carpeta = os.path.join(CANDIDATOS, clase)
    return sorted(f for f in os.listdir(carpeta) if f.lower().endswith(".jpg"))


def fuentes(clase):
    ruta = os.path.join(CANDIDATOS, clase, "fuentes.csv")
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {fila["archivo"]: fila for fila in csv.DictReader(f)}


def leer_sugerencias(clase):
    """{archivo: motivo} de las candidatas que Claude sugiere rechazar."""
    ruta = os.path.join(CANDIDATOS, clase, "sugerencias.csv")
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {fila["archivo"]: fila["motivo"] for fila in csv.DictReader(f)}


def leer_decisiones(clase):
    ruta = os.path.join(CANDIDATOS, clase, "decisiones.csv")
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {fila["archivo"]: fila["estado"] for fila in csv.DictReader(f)}


def guardar_decisiones(clase, decisiones):
    ruta = os.path.join(CANDIDATOS, clase, "decisiones.csv")
    temporal = ruta + ".tmp"
    with open(temporal, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["archivo", "estado"])
        for archivo in sorted(decisiones):
            escritor.writerow([archivo, decisiones[archivo]])
    os.replace(temporal, ruta)  # así un corte a mitad de escritura no deja el archivo dañado


def fotos_en_dataset(clase):
    carpeta = os.path.join(DATASET, clase)
    if not os.path.isdir(carpeta):
        return []
    fotos = []
    for raiz, _, archivos in os.walk(carpeta):
        fotos += [os.path.relpath(os.path.join(raiz, a), DATASET) for a in archivos if a.lower().endswith(EXTENSIONES_IMAGEN)]
    return sorted(fotos)


def resumen():
    filas = []
    for clase in clases_con_candidatas():
        todas = candidatas(clase)
        decisiones = leer_decisiones(clase)
        aceptadas = sum(1 for a in todas if decisiones.get(a) == "aceptada")
        rechazadas = sum(1 for a in todas if decisiones.get(a) == "rechazada")
        sugeridas = set(leer_sugerencias(clase)) & set(todas)
        filas.append({
            "clase": clase, "en_dataset": len(fotos_en_dataset(clase)), "candidatas": len(todas),
            "sugeridas": len(sugeridas), "aceptadas": aceptadas, "rechazadas": rechazadas,
            "pendientes": len(todas) - aceptadas - rechazadas,
        })
    return filas


# --------------------------------------------------------------------------
# Galería (servidor local)
# --------------------------------------------------------------------------

app = Flask(__name__)

ESTILO = """
<style>
 body { font-family: system-ui, sans-serif; margin: 16px; background: #fafafa; color: #222; }
 h1 { font-size: 22px; margin: 0 0 8px; } h2 { font-size: 16px; margin: 18px 0 6px; }
 table { border-collapse: collapse; } td, th { padding: 4px 10px; border-bottom: 1px solid #ddd; text-align: right; }
 td:first-child, th:first-child { text-align: left; }
 .barra { position: sticky; top: 0; background: #fafafa; padding: 8px 0; z-index: 2; border-bottom: 1px solid #ddd; }
 .grilla { display: flex; flex-wrap: wrap; gap: 8px; }
 .foto { width: 190px; cursor: pointer; border: 5px solid #bbb; border-radius: 6px; background: #fff; }
 .foto img { width: 180px; height: 180px; object-fit: cover; display: block; margin: 0 auto; }
 .foto .pie { font-size: 10px; color: #666; padding: 2px 4px; height: 26px; overflow: hidden; }
 .foto.sugerida { border: 5px dashed #e8890c; } .foto.sugerida .pie { color: #b35f00; font-weight: 600; }
 .foto.aceptada { border: 5px solid #2e9e44; } .foto.rechazada { border: 5px solid #d0342c; opacity: .55; }
 .referencia img { width: 110px; height: 110px; object-fit: cover; border-radius: 4px; }
 button { font-size: 15px; padding: 6px 14px; margin-right: 8px; cursor: pointer; }
 .ayuda { color: #555; font-size: 13px; }
</style>
"""


@app.route("/")
def indice():
    filas = "".join(
        f"<tr><td><a href='/clase/{f['clase']}'>{f['clase']}</a></td><td>{f['en_dataset']}</td><td>{f['candidatas']}</td>"
        f"<td>{f['sugeridas']}</td><td>{f['aceptadas']}</td><td>{f['rechazadas']}</td><td><b>{f['pendientes']}</b></td>"
        f"<td>{f['en_dataset'] + f['aceptadas']}</td></tr>"
        for f in resumen()
    )
    return f"""<!doctype html><meta charset="utf-8"><title>Revisión de candidatas</title>{ESTILO}
<h1>Revisión de fotos candidatas</h1>
<p class="ayuda">Nada entra al dataset hasta correr <code>python3 revisar_candidatos.py --aplicar</code>.
"En dataset" cuenta archivos (tras la limpieza, casi todos únicos).</p>
<table><tr><th>clase</th><th>en dataset</th><th>candidatas</th><th>sugeridas para rechazar</th><th>aceptadas</th><th>rechazadas</th><th>pendientes</th><th>dataset + aceptadas</th></tr>{filas}</table>"""


@app.route("/clase/<clase>")
def galeria(clase):
    if clase not in clases_con_candidatas():
        abort(404)
    decisiones = leer_decisiones(clase)
    sugerencias = leer_sugerencias(clase)
    datos = fuentes(clase)
    referencia = fotos_en_dataset(clase)
    random.Random(0).shuffle(referencia)
    tarjetas, tarjetas_sugeridas = [], []
    for archivo in candidatas(clase):
        info = datos.get(archivo, {})
        estado = decisiones.get(archivo, "")
        motivo = sugerencias.get(archivo)
        if motivo:
            pie = html.escape(f"Claude sugiere rechazar: {motivo}")
        else:
            pie = html.escape(f"{info.get('licencia', '')} · {info.get('titulo', '')}")
        titulo = html.escape(f"{info.get('titulo', '')} | {info.get('autor', '')} | {info.get('consulta', '')}", quote=True)
        tarjeta = (
            f"<div class='foto {'sugerida' if motivo else ''} {estado}' data-archivo='{html.escape(archivo, quote=True)}' title='{titulo}'>"
            f"<img loading='lazy' src='/candidata/{clase}/{archivo}'><div class='pie'>{pie}</div></div>"
        )
        (tarjetas_sugeridas if motivo else tarjetas).append(tarjeta)
    refs = "".join(f"<img loading='lazy' src='/dataset/{html.escape(r)}'>" for r in referencia[:10])
    clases = clases_con_candidatas()
    siguiente = clases[(clases.index(clase) + 1) % len(clases)]
    return f"""<!doctype html><meta charset="utf-8"><title>{clase}</title>{ESTILO}
<div class="barra"><a href="/">&larr; todas las clases</a> &nbsp;
<b id="contador"></b> &nbsp;
<button onclick="aceptarPendientes()">Aceptar todas las pendientes</button>
<button onclick="rechazarSugeridas()">Rechazar las sugeridas que no tocaste</button>
<a href="/clase/{siguiente}">siguiente clase: {siguiente} &rarr;</a>
<div class="ayuda">Clic = rechazar (rojo) / aceptar (verde). Doble clic = ver en grande. Se guarda solo.</div></div>
<h1>{clase}</h1>
<h2>Así se ve la clase en el dataset</h2><div class="referencia">{refs}</div>
<h2>Candidatas ({len(tarjetas)})</h2><div class="grilla">{''.join(tarjetas)}</div>
<h2>Claude sugiere rechazar estas ({len(tarjetas_sugeridas)}) &mdash; revísalas: un clic las acepta o rechaza como a las demás</h2>
<div class="grilla">{''.join(tarjetas_sugeridas)}</div>
<script>
const clase = {clase!r};
function contar() {{
  const t = document.querySelectorAll('.foto').length;
  const a = document.querySelectorAll('.foto.aceptada').length;
  const r = document.querySelectorAll('.foto.rechazada').length;
  document.getElementById('contador').textContent = `${{a}} aceptadas · ${{r}} rechazadas · ${{t - a - r}} pendientes`;
}}
async function guardar(cambios) {{
  const resp = await fetch('/decision', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{clase, cambios}})}});
  if (!resp.ok) alert('No se pudo guardar. ¿Sigue corriendo revisar_candidatos.py?');
}}
function marcar(div, estado) {{
  div.classList.remove('aceptada', 'rechazada'); div.classList.add(estado);
}}
document.querySelectorAll('.foto').forEach(div => {{
  div.addEventListener('click', () => {{
    const estado = div.classList.contains('rechazada') ? 'aceptada' : 'rechazada';
    marcar(div, estado); contar(); guardar({{[div.dataset.archivo]: estado}});
  }});
  div.addEventListener('dblclick', () => window.open(div.querySelector('img').src));
}});
function aceptarPendientes() {{
  const cambios = {{}};
  document.querySelectorAll('.foto:not(.aceptada):not(.rechazada):not(.sugerida)').forEach(div => {{
    marcar(div, 'aceptada'); cambios[div.dataset.archivo] = 'aceptada';
  }});
  contar(); if (Object.keys(cambios).length) guardar(cambios);
}}
function rechazarSugeridas() {{
  const cambios = {{}};
  document.querySelectorAll('.foto.sugerida:not(.aceptada):not(.rechazada)').forEach(div => {{
    marcar(div, 'rechazada'); cambios[div.dataset.archivo] = 'rechazada';
  }});
  contar(); if (Object.keys(cambios).length) guardar(cambios);
}}
contar();
</script>"""


@app.route("/candidata/<clase>/<archivo>")
def imagen_candidata(clase, archivo):
    return send_from_directory(os.path.join(CANDIDATOS, clase), archivo)


@app.route("/dataset/<path:relativa>")
def imagen_dataset(relativa):
    return send_from_directory(DATASET, relativa)


@app.route("/decision", methods=["POST"])
def decision():
    datos = request.get_json(silent=True) or {}
    clase = datos.get("clase")
    cambios = datos.get("cambios") or {}
    if clase not in clases_con_candidatas():
        return jsonify({"error": "clase desconocida"}), 400
    validas = set(candidatas(clase))
    decisiones = leer_decisiones(clase)
    for archivo, estado in cambios.items():
        if archivo in validas and estado in ESTADOS:
            decisiones[archivo] = estado
    guardar_decisiones(clase, decisiones)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# --aplicar
# --------------------------------------------------------------------------

def aplicar():
    # Import aquí: numpy/imagehash solo hacen falta para aplicar.
    from recolectar_candidatos import Huellas, huellas_de
    from limpiar_dataset import leer_imagenes
    from PIL import Image

    print("Leyendo huellas del dataset para no meter repetidas...")
    imagenes, _ = leer_imagenes(DATASET)
    huellas = Huellas()
    for imagen in imagenes:
        huellas.agregar(imagen["md5"], imagen["phash"], imagen["color"], f"dataset {imagen['relativa']}")

    nuevo = not os.path.exists(FUENTES_WEB)
    movidas = omitidas = 0
    with open(FUENTES_WEB, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if nuevo:
            escritor.writerow(["archivo_en_dataset", "fuente", "titulo", "autor", "licencia", "url_licencia", "url_pagina", "fecha"])
        for clase in clases_con_candidatas():
            decisiones = leer_decisiones(clase)
            datos = fuentes(clase)
            for archivo in candidatas(clase):
                if decisiones.get(archivo) != "aceptada":
                    continue
                origen = os.path.join(CANDIDATOS, clase, archivo)
                with open(origen, "rb") as g:
                    contenido = g.read()
                with Image.open(origen) as im:
                    huella = huellas_de(im.convert("RGB"), contenido)
                repetida = huellas.repetida_de(*huella)
                if repetida:
                    print(f"  se omite {clase}/{archivo}: igual a {repetida}")
                    omitidas += 1
                    continue
                destino_relativo = os.path.join(clase, "web_" + archivo)
                os.makedirs(os.path.join(DATASET, clase), exist_ok=True)
                shutil.move(origen, os.path.join(DATASET, destino_relativo))
                huellas.agregar(*huella, f"dataset {destino_relativo}")
                info = datos.get(archivo, {})
                escritor.writerow([destino_relativo, info.get("fuente", ""), info.get("titulo", ""), info.get("autor", ""),
                                   info.get("licencia", ""), info.get("url_licencia", ""), info.get("url_pagina", ""),
                                   datetime.now().isoformat(timespec="seconds")])
                movidas += 1
    print(f"\nPasadas a dataset/: {movidas}. Omitidas por repetidas: {omitidas}.")
    print(f"Atribución (autor y licencia de cada foto): {FUENTES_WEB}")


def main():
    parser = argparse.ArgumentParser(description="Revisa las fotos candidatas y pasa las aprobadas al dataset.")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--resumen", action="store_true", help="Muestra el avance de la revisión y sale")
    modo.add_argument("--aplicar", action="store_true", help="Mueve las ACEPTADAS a dataset/<clase>/ (nunca borra)")
    args = parser.parse_args()

    if not clases_con_candidatas():
        sys.exit("No hay candidatas. Primero: python3 recolectar_candidatos.py")
    if args.resumen:
        total = {"candidatas": 0, "sugeridas": 0, "aceptadas": 0, "rechazadas": 0, "pendientes": 0}
        print(f"{'clase':30s} {'dataset':>8s} {'candid.':>8s} {'suger.':>7s} {'acept.':>7s} {'rechaz.':>8s} {'pend.':>6s}")
        for f in resumen():
            print(f"{f['clase']:30s} {f['en_dataset']:8d} {f['candidatas']:8d} {f['sugeridas']:7d} {f['aceptadas']:7d} "
                  f"{f['rechazadas']:8d} {f['pendientes']:6d}")
            for k in total:
                total[k] += f[k]
        print(f"{'TOTAL':30s} {'':8s} {total['candidatas']:8d} {total['sugeridas']:7d} {total['aceptadas']:7d} "
              f"{total['rechazadas']:8d} {total['pendientes']:6d}")
        return
    if args.aplicar:
        aplicar()
        return

    url = f"http://127.0.0.1:{PUERTO}/"
    print(f"Galería en {url}  (Ctrl+C para cerrar; las decisiones ya quedan guardadas)")
    webbrowser.open(url)
    app.run(host="127.0.0.1", port=PUERTO, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
