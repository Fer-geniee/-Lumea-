"""
revisar_candidatos.py -- Revisión humana de las fotos candidatas
(dataset_candidatos/) y paso de las aprobadas al dataset.

1) Galerías (las genera Claude o quien recolecta; no mueven nada):

    python3 revisar_candidatos.py --galerias

   Crea dataset_candidatos/<clase>/galeria.html (una página por clase) y
   dataset_candidatos/index.html (la lista de clases). Se abren con doble
   clic, sin servidor.

2) Revisar (Isabella), en cada galeria.html:
   - Las fotos van de la MÁS SOSPECHOSA a la más segura, según el modelo
     actual (puntuar_candidatas.py). Arriba está lo que más conviene mirar.
   - Clic en una foto = RECHAZADA (se pone roja). Otro clic la devuelve.
     Todo lo que no esté rojo se considera APROBADO.
   - Al final hay una sección plegada con las fotos que Claude ya marcó
     como rechazadas al mirarlas en miniatura, con el motivo. Vienen
     rojas, pero cualquiera se puede devolver con un clic.
   - El botón "Exportar rechazos" descarga rechazos_<clase>.txt (a
     Descargas). Ese archivo ES la revisión: sin él, la clase no se toca.
   - Lo marcado se recuerda en ese navegador aunque cierres la página, pero
     lo que cuenta es el archivo exportado.

3) Aplicar (Isabella, cuando quiera):

    python3 revisar_candidatos.py --aplicar                 # todas las clases con rechazos exportados
    python3 revisar_candidatos.py --aplicar --clases pera   # solo esas
    python3 revisar_candidatos.py --aplicar --reemplazar-fruits360

   Busca rechazos_<clase>.txt en dataset_candidatos/<clase>/ o en
   ~/Downloads (el más reciente). Comprueba que el archivo corresponda a
   las candidatas actuales de la clase. Entonces:
   - APROBADAS -> dataset/<clase>/ (salvo que ya haya una igual en el
     dataset) y su fuente a dataset_fuentes_web.csv (la atribución);
   - RECHAZADAS -> dataset_rechazados/<clase>/ con su fuentes.csv.
   Nada se borra nunca.
   --reemplazar-fruits360: en las frutas revisadas, además aparta las fotos
   de Fruits-360 (fondo blanco, p. ej. pear_0000.jpg) a
   dataset_removidos/fruits360/<clase>/, porque las nuevas las reemplazan.

    python3 revisar_candidatos.py --resumen                 # cómo va cada clase
"""

import argparse
import csv
import glob
import hashlib
import html
import json
import os
import random
import re
import shutil
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(BASE_DIR, "dataset")
CANDIDATOS = os.path.join(BASE_DIR, "dataset_candidatos")
RECHAZADOS = os.path.join(BASE_DIR, "dataset_rechazados")
REMOVIDOS = os.path.join(BASE_DIR, "dataset_removidos")
FUENTES_WEB = os.path.join(BASE_DIR, "dataset_fuentes_web.csv")
DESCARGAS = os.path.expanduser("~/Downloads")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")
FRUTAS = ("manzana", "banano", "fresa", "naranja", "uva", "pera", "mango", "pina")
PATRON_FRUITS360 = re.compile(r"^(apple|banana|strawberry|orange|grape|pear|mango|pineapple)(_[a-z]+)*_\d{4}\.jpg$")
NOMBRES_BONITOS = {"pina": "piña", "bunuelos": "buñuelos", "chicharron": "chicharrón", "patacon": "patacón",
                   "aromatica": "aromática", "gaseosas_bebidas_azucaradas": "gaseosas y bebidas azucaradas"}


# --------------------------------------------------------------------------
# Lectura de datos
# --------------------------------------------------------------------------

def clases_con_candidatas():
    if not os.path.isdir(CANDIDATOS):
        return []
    return sorted(c for c in os.listdir(CANDIDATOS)
                  if os.path.isdir(os.path.join(CANDIDATOS, c)) and not c.startswith(("_", ".")))


def candidatas(clase):
    return sorted(f for f in os.listdir(os.path.join(CANDIDATOS, clase)) if f.lower().endswith(".jpg"))


def huella_del_conjunto(archivos):
    """Identifica el conjunto exacto de candidatas: si cambia (se agregan o
    quitan fotos), un archivo de rechazos viejo ya no corresponde."""
    return hashlib.md5("\n".join(sorted(archivos)).encode()).hexdigest()[:12]


def leer_csv_por_archivo(clase, nombre):
    ruta = os.path.join(CANDIDATOS, clase, nombre)
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {fila["archivo"]: fila for fila in csv.DictReader(f)}


def fotos_en_dataset(clase):
    carpeta = os.path.join(DATASET, clase)
    fotos = []
    for raiz, _, archivos in os.walk(carpeta):
        fotos += [os.path.relpath(os.path.join(raiz, a), DATASET) for a in archivos if a.lower().endswith(EXTENSIONES_IMAGEN)]
    return sorted(fotos)


def buscar_rechazos(clase):
    """Ruta del rechazos_<clase>.txt más reciente, o None."""
    opciones = glob.glob(os.path.join(CANDIDATOS, clase, f"rechazos_{clase}*.txt"))
    opciones += glob.glob(os.path.join(DESCARGAS, f"rechazos_{clase}*.txt"))
    # "rechazos_pera (1).txt" es una segunda exportación de la misma clase; "rechazos_pera_x.txt" no.
    opciones = [o for o in opciones if re.fullmatch(rf"rechazos_{re.escape(clase)}( \(\d+\))?\.txt", os.path.basename(o))]
    return max(opciones, key=os.path.getmtime) if opciones else None


def leer_rechazos(ruta):
    """Devuelve (encabezado: dict, rechazadas: set)."""
    encabezado, rechazadas = {}, set()
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea.startswith("#"):
                if ":" in linea:
                    clave, valor = linea[1:].split(":", 1)
                    encabezado[clave.strip()] = valor.strip()
            elif linea:
                rechazadas.add(linea)
    return encabezado, rechazadas


# --------------------------------------------------------------------------
# Galerías HTML (estáticas, se abren con doble clic)
# --------------------------------------------------------------------------

ESTILO = """
<style>
 :root { color-scheme: light; }
 body { font-family: system-ui, -apple-system, sans-serif; margin: 0 16px 40px; background: #f6f6f4; color: #222; }
 h1 { font-size: 24px; margin: 14px 0 4px; } h2 { font-size: 17px; margin: 22px 0 8px; }
 .barra { position: sticky; top: 0; z-index: 5; background: #f6f6f4; padding: 10px 0; border-bottom: 1px solid #ccc;
          display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
 .barra b { font-size: 15px; }
 button { font-size: 15px; padding: 7px 14px; cursor: pointer; border-radius: 6px; border: 1px solid #888; background: #fff; }
 button.principal { background: #1f6f3f; color: #fff; border-color: #1f6f3f; }
 .ayuda { color: #555; font-size: 13px; max-width: 900px; }
 .grilla { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
 .foto { background: #fff; border: 5px solid #fff; border-radius: 8px; cursor: pointer; position: relative;
         box-shadow: 0 1px 3px rgba(0,0,0,.15); }
 .foto img { width: 100%; height: 250px; object-fit: cover; display: block; border-radius: 4px; }
 .foto .pie { font-size: 12px; color: #444; padding: 5px 4px 3px; line-height: 1.35; }
 .foto .pie .sospecha { font-weight: 600; }
 .foto.rechazada { border-color: #d0342c; }
 .foto.rechazada img { opacity: .35; }
 .foto.rechazada::after { content: "RECHAZADA"; position: absolute; top: 12px; left: 12px; background: #d0342c; color: #fff;
                          font-weight: 700; font-size: 12px; padding: 3px 7px; border-radius: 4px; }
 .referencia { display: flex; gap: 6px; flex-wrap: wrap; }
 .referencia img { width: 120px; height: 120px; object-fit: cover; border-radius: 4px; }
 details { margin-top: 26px; } summary { font-size: 17px; font-weight: 600; cursor: pointer; }
 table { border-collapse: collapse; background: #fff; } td, th { padding: 6px 12px; border-bottom: 1px solid #ddd; text-align: right; }
 td:first-child, th:first-child { text-align: left; }
 a { color: #1f5f9f; }
 @media (max-width: 600px) { .grilla { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); } .foto img { height: 160px; } }
</style>
"""


def generar_galeria(clase):
    carpeta = os.path.join(CANDIDATOS, clase)
    archivos = candidatas(clase)
    fuentes = leer_csv_por_archivo(clase, "fuentes.csv")
    puntajes = leer_csv_por_archivo(clase, "puntajes.csv")
    sugerencias = {a: f["motivo"] for a, f in leer_csv_por_archivo(clase, "sugerencias.csv").items()}
    huella = huella_del_conjunto(archivos)

    def prob(archivo):
        p = puntajes.get(archivo, {}).get("prob_clase")
        return float(p) if p else None

    normales = [a for a in archivos if a not in sugerencias]
    sugeridas = [a for a in archivos if a in sugerencias]
    # Más sospechosa primero; las que no tienen puntaje, al final.
    normales.sort(key=lambda a: (prob(a) is None, prob(a) if prob(a) is not None else 0, a))
    sugeridas.sort(key=lambda a: (sugerencias[a], a))

    def tarjeta(archivo, prerechazada):
        info = fuentes.get(archivo, {})
        p = puntajes.get(archivo, {})
        partes = []
        if p.get("prob_clase"):
            texto = f"El modelo: {float(p['prob_clase']):.0%} {clase}"
            if p.get("clase_predicha") and p["clase_predicha"] != clase:
                texto += f" (cree que es {p['clase_predicha']}, {float(p['prob_predicha']):.0%})"
            partes.append(f"<span class='sospecha'>{html.escape(texto)}</span>")
        if archivo in sugerencias:
            partes.append(f"Claude: {html.escape(sugerencias[archivo])}")
        partes.append(html.escape(f"{info.get('fuente', '')} · {info.get('licencia', '')}"))
        titulo = html.escape(f"{archivo} | {info.get('titulo', '')} | {info.get('url_pagina', '')}", quote=True)
        return (f"<div class='foto{' rechazada' if prerechazada else ''}' data-archivo='{html.escape(archivo, quote=True)}' "
                f"data-sugerida='{1 if prerechazada else 0}' title='{titulo}'>"
                f"<img loading='lazy' src='{html.escape(archivo, quote=True)}'><div class='pie'>{'<br>'.join(partes)}</div></div>")

    referencia = fotos_en_dataset(clase)
    if clase in FRUTAS:  # mostrar las que NO son de Fruits-360, si hay
        reales = [r for r in referencia if not PATRON_FRUITS360.match(os.path.basename(r))]
        referencia = reales or referencia
    random.Random(0).shuffle(referencia)
    refs = "".join(f"<img loading='lazy' src='../../dataset/{html.escape(r, quote=True)}'>" for r in referencia[:10])
    nombre = NOMBRES_BONITOS.get(clase, clase.replace("_", " "))
    datos_js = json.dumps({"clase": clase, "huella": huella, "total": len(archivos)})

    pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisar {html.escape(nombre)}</title>{ESTILO}</head><body>
<div class="barra">
  <a href="../index.html">&larr; todas las clases</a>
  <b id="contador"></b>
  <button class="principal" onclick="exportar()">Exportar rechazos</button>
  <span class="ayuda">Clic en una foto = rechazarla. Lo que no esté rojo queda aprobado. Doble clic = ver grande.</span>
</div>
<h1>{html.escape(nombre)}</h1>
<p class="ayuda">{len(archivos)} candidatas. Ordenadas de la más sospechosa a la más segura según el modelo actual
(ojo: en las frutas el modelo aprendió con fondo blanco, así que puede dudar de fotos buenas).
Rechaza: otro alimento, varios alimentos donde este no es el principal, dibujos o montajes,
texto o marca de agua grande, fotos oscuras o borrosas, o casi iguales a otra.</p>
<h2>Así se ve la clase en el dataset</h2><div class="referencia">{refs}</div>
<h2>Candidatas ({len(normales)})</h2>
<div class="grilla">{''.join(tarjeta(a, False) for a in normales)}</div>
<details{' open' if not normales else ''}><summary>Claude ya marcó estas {len(sugeridas)} como rechazadas (clic para abrir y revisar)</summary>
<p class="ayuda">Las miró en miniatura y anotó el motivo. Vienen en rojo; si alguna sirve, un clic la devuelve.</p>
<div class="grilla">{''.join(tarjeta(a, True) for a in sugeridas)}</div>
</details>
<script>
const DATOS = {datos_js};
const LLAVE = "lumea_revision_" + DATOS.clase + "_" + DATOS.huella;
function guardarLocal() {{
  try {{
    const estado = {{}};
    document.querySelectorAll('.foto').forEach(d => estado[d.dataset.archivo] = d.classList.contains('rechazada'));
    localStorage.setItem(LLAVE, JSON.stringify(estado));
  }} catch (e) {{}}
}}
function restaurarLocal() {{
  try {{
    const estado = JSON.parse(localStorage.getItem(LLAVE) || "null");
    if (!estado) return;
    document.querySelectorAll('.foto').forEach(d => {{
      if (d.dataset.archivo in estado) d.classList.toggle('rechazada', estado[d.dataset.archivo]);
    }});
  }} catch (e) {{}}
}}
function contar() {{
  const r = document.querySelectorAll('.foto.rechazada').length;
  document.getElementById('contador').textContent = `${{DATOS.total - r}} aprobadas · ${{r}} rechazadas`;
}}
document.querySelectorAll('.foto').forEach(d => {{
  d.addEventListener('click', () => {{ d.classList.toggle('rechazada'); contar(); guardarLocal(); }});
  d.addEventListener('dblclick', () => window.open(d.querySelector('img').src));
}});
function exportar() {{
  const rechazadas = [...document.querySelectorAll('.foto.rechazada')].map(d => d.dataset.archivo);
  const lineas = ["# clase: " + DATOS.clase, "# conjunto: " + DATOS.huella, "# candidatas: " + DATOS.total,
                  "# rechazadas: " + rechazadas.length, "# exportado: " + new Date().toISOString(), ...rechazadas];
  const blob = new Blob([lineas.join("\\n") + "\\n"], {{type: "text/plain"}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = "rechazos_" + DATOS.clase + ".txt";
  document.body.appendChild(a); a.click(); a.remove();
  alert("Listo: rechazos_" + DATOS.clase + ".txt quedó en Descargas (" + rechazadas.length + " rechazadas, "
        + (DATOS.total - rechazadas.length) + " aprobadas). Para pasarlas al dataset: python3 revisar_candidatos.py --aplicar");
}}
restaurarLocal(); contar();
</script>
</body></html>
"""
    with open(os.path.join(carpeta, "galeria.html"), "w", encoding="utf-8") as f:
        f.write(pagina)
    return len(archivos), len(sugeridas)


def generar_indice(filas):
    cuerpo = "".join(
        f"<tr><td><a href='{c}/galeria.html'>{html.escape(NOMBRES_BONITOS.get(c, c.replace('_', ' ')))}</a></td>"
        f"<td>{en_ds}</td><td>{total}</td><td>{sug}</td><td>{total - sug}</td><td>{estado}</td></tr>"
        for c, en_ds, total, sug, estado in filas
    )
    pagina = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Revisión de candidatas</title>{ESTILO}</head><body>
<h1>Revisión de fotos candidatas</h1>
<p class="ayuda">Abre una clase, rechaza con un clic lo que no sirve y pulsa "Exportar rechazos". Nada entra al dataset
hasta correr <code>python3 revisar_candidatos.py --aplicar</code>.</p>
<table><tr><th>clase</th><th>fotos en dataset</th><th>candidatas</th><th>Claude ya marcó</th><th>por revisar</th><th>estado</th></tr>
{cuerpo}</table></body></html>
"""
    with open(os.path.join(CANDIDATOS, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)


def galerias(clases):
    for clase in clases:
        total, sug = generar_galeria(clase)
        print(f"  {clase}: {total} candidatas ({sug} ya marcadas por Claude) -> dataset_candidatos/{clase}/galeria.html")
    filas = []
    for clase in clases_con_candidatas():  # el índice siempre lista todas
        archivos = candidatas(clase)
        sug = len(set(leer_csv_por_archivo(clase, "sugerencias.csv")) & set(archivos))
        listas = os.path.exists(os.path.join(CANDIDATOS, clase, "galeria.html"))
        estado = "rechazos exportados" if buscar_rechazos(clase) else ("lista para revisar" if listas else "en preparación")
        filas.append((clase, len(fotos_en_dataset(clase)), len(archivos), sug, estado))
    generar_indice(filas)
    print(f"Índice: {os.path.join(CANDIDATOS, 'index.html')}")


# --------------------------------------------------------------------------
# --aplicar
# --------------------------------------------------------------------------

def mover(origen, carpeta_destino, nombre):
    os.makedirs(carpeta_destino, exist_ok=True)
    destino = os.path.join(carpeta_destino, nombre)
    base, ext = os.path.splitext(destino)
    n = 1
    while os.path.exists(destino):
        destino = f"{base}__{n}{ext}"
        n += 1
    shutil.move(origen, destino)
    return destino


def aplicar(clases, reemplazar_fruits360, forzar):
    from PIL import Image
    from limpiar_dataset import leer_imagenes
    from recolectar_candidatos import Huellas, huellas_de

    listas = {}
    for clase in clases:
        ruta = buscar_rechazos(clase)
        if not ruta:
            continue
        encabezado, rechazadas = leer_rechazos(ruta)
        archivos = candidatas(clase)
        if encabezado.get("clase") != clase:
            print(f"  {clase}: {ruta} dice clase '{encabezado.get('clase')}'; se salta")
            continue
        if encabezado.get("conjunto") != huella_del_conjunto(archivos) and not forzar:
            print(f"  {clase}: las candidatas cambiaron después de exportar {os.path.basename(ruta)} "
                  f"(había {encabezado.get('candidatas')}, hay {len(archivos)}). Revisa de nuevo la galería "
                  f"o usa --forzar (las fotos nuevas contarían como aprobadas).")
            continue
        listas[clase] = (ruta, rechazadas & set(archivos), archivos)
    if not listas:
        print("No hay clases con rechazos exportados (rechazos_<clase>.txt en Descargas o en dataset_candidatos/<clase>/).")
        return

    print("Leyendo huellas del dataset para no meter repetidas...")
    imagenes, _ = leer_imagenes(DATASET)
    huellas = Huellas()
    for imagen in imagenes:
        huellas.agregar(imagen["md5"], imagen["phash"], imagen["color"], f"dataset {imagen['relativa']}")

    nuevo = not os.path.exists(FUENTES_WEB)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(FUENTES_WEB, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if nuevo:
            escritor.writerow(["archivo_en_dataset", "fuente", "id", "titulo", "autor", "licencia", "url_licencia",
                               "url_pagina", "url_imagen", "fecha"])
        for clase, (ruta, rechazadas, archivos) in listas.items():
            fuentes = leer_csv_por_archivo(clase, "fuentes.csv")
            carpeta = os.path.join(CANDIDATOS, clase)
            movidas = omitidas = 0
            for archivo in archivos:
                origen = os.path.join(carpeta, archivo)
                if archivo in rechazadas:
                    mover(origen, os.path.join(RECHAZADOS, clase), archivo)
                    continue
                with open(origen, "rb") as g:
                    contenido = g.read()
                with Image.open(origen) as im:
                    huella = huellas_de(im.convert("RGB"), contenido)
                repetida = huellas.repetida_de(*huella)
                if repetida:
                    mover(origen, os.path.join(RECHAZADOS, clase), archivo)
                    omitidas += 1
                    continue
                destino = mover(origen, os.path.join(DATASET, clase), archivo)
                relativa = os.path.relpath(destino, DATASET)
                huellas.agregar(*huella, f"dataset {relativa}")
                info = fuentes.get(archivo, {})
                escritor.writerow([relativa, info.get("fuente", ""), info.get("id", ""), info.get("titulo", ""),
                                   info.get("autor", ""), info.get("licencia", ""), info.get("url_licencia", ""),
                                   info.get("url_pagina", ""), info.get("url_imagen", ""),
                                   datetime.now().isoformat(timespec="seconds")])
                movidas += 1
            # Registro de la revisión: copia del archivo de rechazos y de las fuentes, junto a los rechazados.
            os.makedirs(os.path.join(RECHAZADOS, clase), exist_ok=True)
            shutil.copy(ruta, os.path.join(RECHAZADOS, clase, f"rechazos_{clase}_{marca}.txt"))
            # El archivo usado se renombra para que una segunda corrida no lo vuelva a aplicar.
            os.replace(ruta, os.path.join(os.path.dirname(ruta), f"rechazos_{clase}_aplicado_{marca}.txt"))
            if os.path.exists(os.path.join(carpeta, "fuentes.csv")):
                shutil.copy(os.path.join(carpeta, "fuentes.csv"), os.path.join(RECHAZADOS, clase, f"fuentes_{marca}.csv"))
            print(f"  {clase}: {movidas} aprobadas -> dataset/{clase}/; {len(rechazadas)} rechazadas y "
                  f"{omitidas} repetidas del dataset -> dataset_rechazados/{clase}/")

    if reemplazar_fruits360:
        filas = []
        for clase in listas:
            if clase not in FRUTAS:
                continue
            for relativa in fotos_en_dataset(clase):
                if PATRON_FRUITS360.match(os.path.basename(relativa)):
                    destino = mover(os.path.join(DATASET, relativa), os.path.join(REMOVIDOS, "fruits360", clase),
                                    os.path.basename(relativa))
                    filas.append((os.path.join(DATASET, relativa), destino))
            print(f"  {clase}: fotos de Fruits-360 apartadas -> dataset_removidos/fruits360/{clase}/")
        if filas:
            manifiesto = os.path.join(REMOVIDOS, "fruits360", f"manifiesto_{marca}.csv")
            with open(manifiesto, "w", newline="", encoding="utf-8") as f:
                escritor = csv.writer(f)
                escritor.writerow(["origen", "destino"])
                escritor.writerows(filas)
            print(f"  {len(filas)} fotos de Fruits-360 apartadas (manifiesto para deshacer: {manifiesto})")

    print(f"\nAtribución de las fotos nuevas: {FUENTES_WEB}")
    print("Siguiente paso: python3 limpiar_dataset.py  (reporte, para confirmar que no quedaron repetidas)")


def resumen(clases):
    print(f"{'clase':30s} {'dataset':>8s} {'candidatas':>11s} {'Claude marcó':>13s}  revisión")
    for clase in clases:
        sug = len(set(leer_csv_por_archivo(clase, "sugerencias.csv")) & set(candidatas(clase)))
        ruta = buscar_rechazos(clase)
        estado = f"exportada ({os.path.basename(ruta)})" if ruta else "sin revisar"
        print(f"{clase:30s} {len(fotos_en_dataset(clase)):8d} {len(candidatas(clase)):11d} {sug:13d}  {estado}")


def main():
    parser = argparse.ArgumentParser(description="Revisión de candidatas y paso al dataset.")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--galerias", action="store_true", help="Genera galeria.html por clase e index.html")
    modo.add_argument("--aplicar", action="store_true", help="Mueve aprobadas al dataset y rechazadas a dataset_rechazados/")
    modo.add_argument("--resumen", action="store_true", help="Estado de la revisión por clase")
    parser.add_argument("--clases", nargs="*", help="Solo estas clases")
    parser.add_argument("--reemplazar-fruits360", action="store_true",
                        help="Con --aplicar: aparta las fotos de Fruits-360 de las frutas revisadas")
    parser.add_argument("--forzar", action="store_true",
                        help="Con --aplicar: usa el archivo de rechazos aunque las candidatas hayan cambiado")
    args = parser.parse_args()

    todas = clases_con_candidatas()
    if not todas:
        sys.exit("No hay candidatas. Primero: python3 recolectar_candidatos.py")
    clases = args.clases or todas
    desconocidas = [c for c in clases if c not in todas]
    if desconocidas:
        sys.exit("Sin candidatas: " + ", ".join(desconocidas))
    if args.galerias:
        galerias(clases)
    elif args.aplicar:
        aplicar(clases, args.reemplazar_fruits360, args.forzar)
    else:
        resumen(clases)


if __name__ == "__main__":
    main()
