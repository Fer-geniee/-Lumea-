"""
recolectar_candidatos.py -- Busca fotos NUEVAS, con licencia abierta, para
las clases que quedaron con pocas fotos únicas después de limpiar el
dataset, y las deja en dataset_candidatos/<clase>/ PARA REVISIÓN HUMANA.

Nunca toca dataset/. Ninguna foto entra al entrenamiento sin que una
persona la apruebe con revisar_candidatos.py.

    python3 recolectar_candidatos.py --plan             # déficit por clase, sin descargar
    python3 recolectar_candidatos.py                    # recolecta para todas las clases con déficit
    python3 recolectar_candidatos.py --clases pera uva  # solo esas clases
    python3 recolectar_candidatos.py --consultas ronda2.json --mas 60 --clases uva
                                                        # otra ronda: búsquedas NUEVAS (las viejas ya
                                                        # se agotaron) y 60 candidatas más por clase

Fuentes (solo con licencia explícita y atribución):
- Wikimedia Commons: todo lo que hay ahí tiene licencia libre (CC0, dominio
  público, CC BY, CC BY-SA...). Se usa por categoría (curada por
  voluntarios) y buscando la frase en el TÍTULO del archivo (intitle):
  la búsqueda libre traía de todo (con "fresas con crema" salían flores
  que se llaman 'Strawberries and Cream' y helados).
- Openverse (api.openverse.org, de WordPress): índice de fotos con licencia
  Creative Commons, sobre todo de Flickr. Se piden solo licencias que
  permiten modificar la imagen (by, by-sa, cc0, pdm, by-nc, by-nc-sa):
  se excluyen las "SinDerivadas"
  (ND), porque para entrenar la foto se recorta y redimensiona. Las NC
  (no comercial) se aceptan porque Lumea es un proyecto escolar, pero
  quedan marcadas en fuentes.csv por si el proyecto cambiara de uso.
  Sin cuenta, Openverse permite 200 consultas al día; el script lleva la
  cuenta y se detiene antes de pasarse. (No se usa su filtro
  category=photograph: deja fuera todo Flickr, que no trae esa etiqueta.)
  Si la cuota se acaba, volver a correr el script otro día continúa
  donde quedó: las fotos ya vistas no se vuelven a pedir.

NO se usa Google Imágenes ni bancos de fotos: sus fotos no tienen una
licencia que permita usarlas, y muchas traen marca de agua.

Filtros automáticos antes de la revisión (todo lo descartado queda en
dataset_candidatos/_registro.csv con el motivo):
- lado menor de al menos 224 px (el tamaño de entrada del modelo);
- títulos que delatan que no es una foto de comida (pintura, dibujo,
  árbol, flor, mapa, catálogo...);
- imágenes sin color (escaneos en blanco y negro, dibujos de línea): en
  la primera prueba eran casi un 10% de lo que traía Commons;
- repetidas: la misma huella (MD5, o pHash + color, igual que
  limpiar_dataset.py) que una foto del dataset (de CUALQUIER clase) o que
  otra candidata ya guardada.

Cada foto se guarda como JPEG de máximo 1024 px de lado y SIN metadatos
EXIF (pueden traer la ubicación GPS de quien tomó la foto). Su origen,
autor y licencia quedan en dataset_candidatos/<clase>/fuentes.csv; esa
atribución es obligatoria para las licencias BY.

Cuántas se buscan por clase: (objetivo - fotos únicas actuales) x margen,
porque en la revisión se descarta una parte. Por defecto objetivo 150 y
margen 1.8: en la primera prueba (pera, 207 candidatas) servía más o menos
el 60%. Para platos regionales hay pocas fotos con licencia abierta y
muchas clases no alcanzan la cantidad buscada: el script trae las que
hay y lo dice.
"""

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import imagehash
import numpy as np
import requests
from PIL import Image, ImageOps

from limpiar_dataset import decidir_por_clase, distancias, leer_imagenes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(BASE_DIR, "dataset")
CANDIDATOS = os.path.join(BASE_DIR, "dataset_candidatos")
REGISTRO = os.path.join(CANDIDATOS, "_registro.csv")
VISTOS = os.path.join(CANDIDATOS, "_vistos.json")
CUOTA_OPENVERSE = os.path.join(CANDIDATOS, "_cuota_openverse.json")

AGENTE = "Lumea/1.0 (proyecto escolar Fedesoft, Colombia; https://github.com/Fer-geniee/-Lumea-)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
LICENCIAS_OPENVERSE = "by,by-sa,cc0,pdm,by-nc,by-nc-sa"
ANCHO_MINIATURA_COMMONS = 960  # tamaño estándar de miniatura de Wikimedia
LADO_MINIMO = 224
LADO_MAXIMO = 1024
UMBRAL_PHASH = 5
UMBRAL_COLOR = 3
RESERVA_OPENVERSE = 3  # consultas diarias que se dejan sin usar
MAXIMO_POR_CONSULTA = 300  # resultados revisados por consulta: más allá, casi todo es ruido
TAMANO_LOTE = 24
MINIMO_PIXELES_CON_COLOR = 0.03  # menos de 3% de píxeles con color = blanco y negro

# Palabras en el título que casi siempre significan "no es una foto de un
# plato o de la fruta lista para comer". Se comparan como palabras
# completas, sin distinguir mayúsculas.
TITULOS_EXCLUIDOS = [
    "painting", "pintura", "oil on canvas", "óleo", "drawing", "dibujo", "illustration", "ilustración",
    "engraving", "grabado", "lithograph", "stamp", "sello postal", "logo", "icon", "map", "mapa",
    "diagram", "poster", "cartoon", "clipart", "herbarium", "herbario", "botanical", "seedling",
    "tree", "trees", "árbol", "arbol", "orchard", "plantation", "blossom", "flower", "flowers", "flor",
    "plant", "plants", "planta", "field", "cultivo", "museum", "museo",
    "still life", "bodegón", "statue", "estatua", "sculpture", "toy", "juguete", "sticker",
    "catalogue", "catalog", "catálogo", "book", "libro", "papers", "cards", "archief", "archive",
    "bundesarchiv", "magazine", "revista", "advertisement", "anuncio", "label", "etiqueta",
    "cultivar", "sedum", "bellis", "hamamelis", "heliconia", "dahlia", "tulip", "rosa", "lolly", "lollies",
]
PATRON_EXCLUIDO = re.compile(r"\b(" + "|".join(re.escape(p) for p in TITULOS_EXCLUIDOS) + r")\b", re.IGNORECASE)

# Por clase: categorías de Commons (solo sus archivos directos), frases
# que deben aparecer en el TÍTULO del archivo en Commons, y búsquedas en
# Openverse, en ese orden. Se para al llegar a la cantidad buscada.
CONSULTAS = {
    "pera": {"categorias": ["Pears"], "commons": ["pears"], "openverse": ["pear fruit", "pears", "peras fruta", "ripe pears"]},
    "manzana": {"categorias": ["Apples"], "commons": ["apples"], "openverse": ["apple fruit", "red apples", "green apple fruit", "manzanas fruta"]},
    "mango": {"categorias": ["Mango", "Sliced mangoes"], "commons": ["mangoes", "mango fruit"], "openverse": ["mango fruit", "ripe mango", "mangos fruta"]},
    "naranja": {"categorias": ["Oranges"], "commons": ["oranges"], "openverse": ["orange fruit", "oranges fruit", "naranjas fruta"]},
    "fresa": {"categorias": ["Strawberries"], "commons": ["strawberries"], "openverse": ["strawberries", "strawberry fruit", "fresas fruta"]},
    "uva": {"categorias": ["Grapes"], "commons": ["grapes"], "openverse": ["grapes", "bunch of grapes", "uvas fruta"]},
    "banano": {"categorias": ["Bananas"], "commons": ["bananas"], "openverse": ["banana fruit", "bananas", "bananos"]},
    "pina": {"categorias": ["Pineapples", "Pineapple slices"], "commons": ["pineapple"], "openverse": ["pineapple fruit", "pineapple slices", "piña fruta"]},
    "aromatica": {"categorias": [], "commons": ["herbal tea", "aromática", "infusión"],
                  "openverse": ["aromatica colombiana", "herbal tea glass", "fruit tea glass", "infusion de frutas", "te de hierbas"]},
    "fresas_crema": {"categorias": ["Strawberries and cream"], "commons": ["fresas con crema"],
                     "openverse": ["fresas con crema", "strawberries and cream", "strawberries with cream"]},
    "arroz": {"categorias": ["White rice", "Cooked rice"], "commons": ["white rice", "arroz blanco", "steamed rice"],
              "openverse": ["white rice bowl", "arroz blanco", "steamed rice", "cooked white rice"]},
    "bunuelos": {"categorias": ["Buñuelos"], "commons": ["buñuelos", "buñuelo"], "openverse": ["buñuelos colombianos", "buñuelos", "bunuelos"]},
    "patacon": {"categorias": ["Tostones"], "commons": ["patacones", "patacón", "tostones"], "openverse": ["patacones", "tostones", "patacon"]},
    "chicharron": {"categorias": ["Chicharrones"], "commons": ["chicharrón", "chicharron"],
                   "openverse": ["chicharron colombiano", "chicharrón", "chicharrones", "fried pork belly"]},
    "hornado": {"categorias": ["Hornado"], "commons": ["hornado"], "openverse": ["hornado", "hornado ecuatoriano", "hornado pastuso"]},
    "frito": {"categorias": ["Fritada"], "commons": ["fritada", "frito pastuso"], "openverse": ["frito pastuso", "fritada", "fritada ecuatoriana"]},
    "natilla": {"categorias": ["Natillas"], "commons": ["natilla"], "openverse": ["natilla colombiana", "natilla navideña", "natilla"]},
    "llapingachos": {"categorias": ["Llapingachos"], "commons": ["llapingacho"], "openverse": ["llapingachos", "llapingacho"]},
    "bandeja_paisa": {"categorias": ["Bandeja paisa"], "commons": ["bandeja paisa"], "openverse": ["bandeja paisa"]},
    "pollo_frito": {"categorias": ["Fried chicken"], "commons": ["fried chicken", "pollo frito"], "openverse": ["fried chicken", "pollo frito", "fried chicken plate"]},
    "huevo": {"categorias": ["Fried eggs", "Boiled eggs", "Scrambled eggs"], "commons": ["fried egg", "huevo frito", "boiled egg"],
              "openverse": ["fried egg", "boiled eggs", "scrambled eggs", "huevos pericos"]},
    "mazorcada": {"categorias": [], "commons": ["mazorcada", "desgranado"], "openverse": ["mazorcada", "desgranado colombiano", "maiz desgranado"]},
    "cuy": {"categorias": ["Cuy-based food", "Cuy meat"], "commons": ["cuy asado", "cuy chactado", "roasted guinea pig"],
            "openverse": ["cuy asado", "roasted guinea pig", "cuy"]},
    "almuerzos": {"categorias": [], "commons": ["almuerzo colombiano", "corrientazo", "almuerzo ejecutivo"],
                  "openverse": ["almuerzo colombiano", "corrientazo", "almuerzo corriente", "almuerzo ejecutivo"]},
    "pescado": {"categorias": ["Fried fish"], "commons": ["pescado frito", "fried fish", "mojarra frita"],
                "openverse": ["pescado frito", "fried fish plate", "mojarra frita"]},
    "obleas": {"categorias": ["Obleas"], "commons": ["obleas", "oblea"], "openverse": ["obleas colombianas", "oblea arequipe", "obleas"]},
    "gaseosas_bebidas_azucaradas": {"categorias": [], "commons": ["soft drink", "gaseosa"], "openverse": ["gaseosa", "soda bottle", "soft drink glass"]},
    "pandebono": {"categorias": ["Pan de bono"], "commons": ["pandebono", "pan de bono"], "openverse": ["pandebono", "pan de bono"]},
    "pinchos": {"categorias": [], "commons": ["pincho de carne"], "openverse": ["pincho de carne", "chuzo colombiano", "carne en pincho"]},
}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

sesion = requests.Session()
sesion.headers["User-Agent"] = AGENTE


def leer_json(ruta, por_defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return por_defecto


def escribir_json(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)


def agregar_csv(ruta, encabezado, fila):
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if nuevo:
            escritor.writerow(encabezado)
        escritor.writerow(fila)


def registrar(clase, fuente, identificador, motivo, detalle=""):
    agregar_csv(REGISTRO, ["fecha", "clase", "fuente", "id", "motivo", "detalle"],
                [datetime.now().isoformat(timespec="seconds"), clase, fuente, identificador, motivo, detalle])


def sin_html(texto):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto or ""))).strip()


def unicas_por_clase():
    """Fotos únicas actuales de cada clase (lo que quedaría tras limpiar)."""
    imagenes, _ = leer_imagenes(DATASET)
    por_clase = {}
    for imagen in imagenes:
        por_clase.setdefault(imagen["clase"], []).append(imagen)
    unicas = {c: len(lista) - len(decidir_por_clase(lista, UMBRAL_PHASH, UMBRAL_COLOR)) for c, lista in por_clase.items()}
    return imagenes, unicas


def cuantas_buscar(unicas, objetivo, margen):
    return max(0, math.ceil((objetivo - unicas) * margen)) if unicas < objetivo else 0


# --------------------------------------------------------------------------
# Huellas: para no guardar repetidas
# --------------------------------------------------------------------------

class Huellas:
    """MD5, pHash y colorhash de todo lo ya visto (dataset + candidatas)."""

    def __init__(self):
        self.md5 = {}  # md5 -> de dónde es
        self.phash = []
        self.color = []
        self.origen = []

    def agregar(self, md5, phash, color, origen):
        self.md5.setdefault(md5, origen)
        self.phash.append(phash)
        self.color.append(color)
        self.origen.append(origen)

    def repetida_de(self, md5, phash, color):
        if md5 in self.md5:
            return f"copia exacta de {self.md5[md5]}"
        if not self.phash:
            return None
        d_forma = distancias(phash, np.array(self.phash, dtype=np.uint64))
        d_color = distancias(color, np.array(self.color, dtype=np.uint64))
        indices = np.nonzero((d_forma <= UMBRAL_PHASH) & (d_color <= UMBRAL_COLOR))[0]
        return self.origen[int(indices[0])] if len(indices) else None


def huellas_de(imagen_rgb, contenido):
    return (
        hashlib.md5(contenido).hexdigest(),
        int(str(imagehash.phash(imagen_rgb)), 16),
        int(str(imagehash.colorhash(imagen_rgb, binbits=3)), 16),
    )


# --------------------------------------------------------------------------
# Fuentes
# --------------------------------------------------------------------------

def commons_consulta(parametros):
    parametros = {"action": "query", "format": "json", "maxlag": 5, **parametros}
    for intento in range(4):
        r = sesion.get(COMMONS_API, params=parametros, timeout=60)
        if r.status_code == 200 and "error" not in r.json():
            return r.json()
        time.sleep(5 * (intento + 1))
    r.raise_for_status()
    return r.json()


def commons_resultados(generador):
    """Recorre páginas de un generador de Commons y devuelve fotos con su
    licencia, autor y URL de miniatura."""
    continuar = {}
    while True:
        datos = commons_consulta({
            **generador, **continuar,
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": ANCHO_MINIATURA_COMMONS,
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|ImageDescription",
        })
        for pagina in (datos.get("query", {}).get("pages") or {}).values():
            info = (pagina.get("imageinfo") or [{}])[0]
            if info.get("mime") != "image/jpeg":  # en Commons, los PNG casi siempre son dibujos o esquemas
                continue
            meta = info.get("extmetadata", {})
            yield {
                "fuente": "commons",
                "id": str(pagina["pageid"]),
                "titulo": pagina["title"].removeprefix("File:"),
                "ancho": info.get("width", 0),
                "alto": info.get("height", 0),
                "url_imagen": info.get("thumburl") or info.get("url"),
                "url_pagina": info.get("descriptionurl", ""),
                "autor": sin_html(meta.get("Artist", {}).get("value", "")),
                "licencia": meta.get("LicenseShortName", {}).get("value", ""),
                "url_licencia": meta.get("LicenseUrl", {}).get("value", ""),
            }
        if "continue" not in datos:
            return
        continuar = datos["continue"]


def commons_categoria(categoria):
    return commons_resultados({"generator": "categorymembers", "gcmtitle": "Category:" + categoria,
                               "gcmtype": "file", "gcmlimit": 50})


def commons_busqueda(consulta):
    return commons_resultados({"generator": "search", "gsrsearch": f'intitle:"{consulta}" filetype:bitmap',
                               "gsrnamespace": 6, "gsrlimit": 50})


class Openverse:
    """Consultas a Openverse sin cuenta: 20 por minuto y 200 por día. La
    cuota que queda se guarda en disco para que otra corrida el mismo día
    no se pase."""

    def __init__(self):
        estado = leer_json(CUOTA_OPENVERSE, {})
        hoy = datetime.now().strftime("%Y-%m-%d")
        self.disponibles = estado.get("disponibles", 200) if estado.get("fecha") == hoy else 200
        self.hoy = hoy
        self.ultima = 0.0

    def guardar(self):
        escribir_json(CUOTA_OPENVERSE, {"fecha": self.hoy, "disponibles": self.disponibles})

    def buscar(self, consulta, pagina):
        if self.disponibles <= RESERVA_OPENVERSE:
            return None
        espera = 3.2 - (time.time() - self.ultima)  # como mucho ~19 por minuto
        if espera > 0:
            time.sleep(espera)
        self.ultima = time.time()
        r = sesion.get(OPENVERSE_API, params={
            "q": consulta, "page": pagina, "page_size": 20, "license": LICENCIAS_OPENVERSE,
            "excluded_source": "wikimedia", "mature": "false",
        }, timeout=60)
        # Se cuenta aquí además de leer el encabezado: en la prueba, el
        # encabezado de cuota diaria no bajaba de una consulta a otra.
        restante = r.headers.get("x-ratelimit-available-anon_sustained")
        self.disponibles -= 1
        if restante is not None:
            self.disponibles = min(self.disponibles, int(restante))
        self.guardar()
        if r.status_code == 429:
            self.disponibles = 0
            self.guardar()
            return None
        if r.status_code != 200:
            return []
        return r.json().get("results", [])

    def resultados(self, consulta, paginas):
        for pagina in range(1, paginas + 1):
            resultados = self.buscar(consulta, pagina)
            if not resultados:
                return
            for r in resultados:
                if r.get("filetype") not in (None, "jpg", "jpeg", "png"):
                    continue
                licencia = f"CC {r['license'].upper()} {r.get('license_version') or ''}".strip()
                if r["license"] in ("cc0", "pdm"):
                    licencia = r["license"].upper()
                yield {
                    "fuente": "openverse-" + (r.get("source") or "otro"),
                    "id": r["id"],
                    "titulo": r.get("title") or "",
                    "ancho": r.get("width") or 0,
                    "alto": r.get("height") or 0,
                    "url_imagen": r["url"],
                    "url_pagina": r.get("foreign_landing_url") or "",
                    "autor": r.get("creator") or "",
                    "licencia": licencia,
                    "url_licencia": r.get("license_url") or "",
                }


# --------------------------------------------------------------------------
# Descarga y guardado
# --------------------------------------------------------------------------

def descargar(candidata):
    """Devuelve (candidata, contenido o None, error)."""
    try:
        r = sesion.get(candidata["url_imagen"], timeout=60)
        if r.status_code != 200:
            return candidata, None, f"HTTP {r.status_code}"
        return candidata, r.content, ""
    except requests.RequestException as e:
        return candidata, None, type(e).__name__


def fraccion_con_color(imagen_rgb):
    """Fracción de píxeles con saturación > 15%. En un escaneo en blanco y
    negro o un dibujo de línea es casi 0; en una foto de comida, aunque
    sea arroz blanco en plato blanco, el fondo o la mesa tienen color."""
    pequena = imagen_rgb.resize((64, 64))
    saturacion = np.asarray(pequena.convert("HSV"))[:, :, 1]
    return float((saturacion > 38).mean())


def preparar(contenido):
    """Abre, gira según EXIF, pasa a RGB, reduce a LADO_MAXIMO y vuelve a
    codificar sin metadatos. Devuelve (imagen, bytes_jpeg) o lanza error."""
    with Image.open(io.BytesIO(contenido)) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
    if min(im.size) < LADO_MINIMO:
        raise ValueError(f"muy pequeña ({im.size[0]}x{im.size[1]})")
    if fraccion_con_color(im) < MINIMO_PIXELES_CON_COLOR:
        raise ValueError("sin color (blanco y negro o dibujo)")
    im.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
    salida = io.BytesIO()
    im.save(salida, "JPEG", quality=92)
    return im, salida.getvalue()


def nombre_archivo(candidata):
    base = re.sub(r"[^a-z0-9]+", "-", candidata["fuente"].lower())
    return f"{base}_{candidata['id'][:12]}.jpg"


def procesar_lote(clase, lote, carpeta, fuentes_csv, huellas, guardadas, cuantas):
    """Descarga el lote en paralelo (4 a la vez) y guarda las que pasan los
    filtros, hasta llegar a `cuantas`. Devuelve el nuevo total guardado."""
    with ThreadPoolExecutor(max_workers=4) as grupo:
        for candidata, contenido, error in grupo.map(descargar, lote):
            if guardadas >= cuantas:
                break
            if contenido is None:
                registrar(clase, candidata["fuente"], candidata["id"], "error_descarga", error)
                continue
            try:
                imagen, jpeg = preparar(contenido)
            except Exception as e:
                registrar(clase, candidata["fuente"], candidata["id"], "descartada_al_abrir", str(e)[:120])
                continue
            md5_original = hashlib.md5(contenido).hexdigest()
            md5, phash, color = huellas_de(imagen, jpeg)
            repetida = huellas.repetida_de(md5_original, phash, color)
            if repetida:
                registrar(clase, candidata["fuente"], candidata["id"], "repetida", repetida)
                continue
            archivo = nombre_archivo(candidata)
            with open(os.path.join(carpeta, archivo), "wb") as f:
                f.write(jpeg)
            huellas.agregar(md5, phash, color, f"candidata {clase}/{archivo}")
            huellas.md5.setdefault(md5_original, f"candidata {clase}/{archivo}")
            agregar_csv(fuentes_csv, ENCABEZADO_FUENTES, [
                archivo, candidata["fuente"], candidata["id"], candidata["titulo"], candidata["autor"],
                candidata["licencia"], candidata["url_licencia"], candidata["url_pagina"],
                candidata["url_imagen"], candidata["consulta"], candidata["ancho"], candidata["alto"],
                datetime.now().isoformat(timespec="seconds"),
            ])
            guardadas += 1
    return guardadas


ENCABEZADO_FUENTES = ["archivo", "fuente", "id", "titulo", "autor", "licencia", "url_licencia",
                      "url_pagina", "url_imagen", "consulta", "ancho_original", "alto_original", "fecha"]


def recolectar_clase(clase, cuantas, huellas, vistos, openverse, paginas_openverse):
    carpeta = os.path.join(CANDIDATOS, clase)
    os.makedirs(carpeta, exist_ok=True)
    fuentes_csv = os.path.join(carpeta, "fuentes.csv")
    ya = sum(1 for f in os.listdir(carpeta) if f.endswith(".jpg"))
    if ya >= cuantas:
        print(f"  {clase}: ya tiene {ya} candidatas (se buscaban {cuantas})")
        return ya
    config = CONSULTAS.get(clase)
    if not config:
        print(f"  {clase}: sin consultas definidas en CONSULTAS; se salta")
        return ya

    generadores = [(f"commons categoría '{c}'", commons_categoria(c)) for c in config["categorias"]]
    generadores += [(f"commons búsqueda '{q}'", commons_busqueda(q)) for q in config["commons"]]
    generadores += [(f"openverse '{q}'", openverse.resultados(q, paginas_openverse)) for q in config["openverse"]]

    guardadas = ya
    for consulta, generador in generadores:
        revisadas = 0
        lote = []
        for candidata in generador:
            revisadas += 1
            if revisadas > MAXIMO_POR_CONSULTA:
                break
            clave = f"{candidata['fuente']}:{candidata['id']}"
            if clave in vistos:
                continue
            vistos[clave] = clase
            if PATRON_EXCLUIDO.search(candidata["titulo"]):
                registrar(clase, candidata["fuente"], candidata["id"], "titulo_excluido", candidata["titulo"][:120])
                continue
            if candidata["ancho"] and candidata["alto"] and min(candidata["ancho"], candidata["alto"]) < LADO_MINIMO:
                registrar(clase, candidata["fuente"], candidata["id"], "pequena", f"{candidata['ancho']}x{candidata['alto']}")
                continue
            candidata["consulta"] = consulta
            lote.append(candidata)
            if len(lote) >= TAMANO_LOTE:
                guardadas = procesar_lote(clase, lote, carpeta, fuentes_csv, huellas, guardadas, cuantas)
                lote = []
                if guardadas >= cuantas:
                    break
        if lote and guardadas < cuantas:
            guardadas = procesar_lote(clase, lote, carpeta, fuentes_csv, huellas, guardadas, cuantas)
        escribir_json(VISTOS, vistos)
        print(f"    {consulta}: {guardadas}/{cuantas}")
        if guardadas >= cuantas:
            break
    if guardadas < cuantas:
        print(f"  {clase}: solo se encontraron {guardadas} de {cuantas} (no hay más fotos con licencia abierta en estas búsquedas)")
    return guardadas


def main():
    parser = argparse.ArgumentParser(description="Recolecta fotos candidatas con licencia abierta para revisión.")
    parser.add_argument("--clases", nargs="*", help="Solo estas clases (por defecto: todas las que tienen déficit)")
    parser.add_argument("--objetivo", type=int, default=150, help="Fotos únicas deseadas por clase (por defecto 150)")
    parser.add_argument("--margen", type=float, default=1.8, help="Candidatas por cada foto que falta (por defecto 1.8)")
    parser.add_argument("--paginas-openverse", type=int, default=4, help="Páginas de 20 resultados por búsqueda en Openverse")
    parser.add_argument("--plan", action="store_true", help="Solo muestra el déficit y cuántas se buscarían")
    parser.add_argument("--consultas", metavar="ARCHIVO.json",
                        help="Reemplaza las búsquedas de las clases que aparecen en el archivo (mismo formato que CONSULTAS). "
                             "Para una segunda ronda: repetir las búsquedas viejas solo gasta cuota, porque ya se vieron")
    parser.add_argument("--mas", type=int, metavar="N",
                        help="Busca N candidatas nuevas por clase además de las que ya hay (ignora --objetivo y --margen)")
    args = parser.parse_args()
    if args.consultas:
        with open(args.consultas, encoding="utf-8") as f:
            CONSULTAS.update(json.load(f))

    print("Calculando fotos únicas por clase y huellas del dataset...")
    imagenes, unicas = unicas_por_clase()
    clases = args.clases or sorted((c for c in unicas if unicas[c] < args.objetivo), key=lambda c: unicas[c])
    desconocidas = [c for c in clases if c not in unicas]
    if desconocidas:
        sys.exit("Clases que no existen en dataset/: " + ", ".join(desconocidas))

    print(f"\n{'clase':30s} {'únicas':>7s} {'faltan':>7s} {'buscar':>7s}")
    for clase in clases:
        buscar = cuantas_buscar(unicas[clase], args.objetivo, args.margen)
        print(f"{clase:30s} {unicas[clase]:7d} {max(0, args.objetivo - unicas[clase]):7d} {buscar:7d}")
    if args.plan:
        return

    os.makedirs(CANDIDATOS, exist_ok=True)
    huellas = Huellas()
    for imagen in imagenes:
        huellas.agregar(imagen["md5"], imagen["phash"], imagen["color"], f"dataset {imagen['relativa']}")
    # Candidatas de corridas anteriores (de todas las clases).
    for clase in sorted(os.listdir(CANDIDATOS)):
        carpeta = os.path.join(CANDIDATOS, clase)
        if not os.path.isdir(carpeta):
            continue
        for archivo in os.listdir(carpeta):
            if archivo.endswith(".jpg"):
                with open(os.path.join(carpeta, archivo), "rb") as f:
                    contenido = f.read()
                with Image.open(io.BytesIO(contenido)) as im:
                    huellas.agregar(*huellas_de(im.convert("RGB"), contenido), f"candidata {clase}/{archivo}")
    vistos = leer_json(VISTOS, {})
    openverse = Openverse()

    for clase in clases:
        cuantas = cuantas_buscar(unicas[clase], args.objetivo, args.margen)
        if args.mas:
            carpeta = os.path.join(CANDIDATOS, clase)
            ya = sum(1 for f in os.listdir(carpeta) if f.endswith(".jpg")) if os.path.isdir(carpeta) else 0
            cuantas = ya + args.mas
        if cuantas == 0:
            continue
        print(f"\n{clase} (buscar {cuantas}; consultas de Openverse que quedan hoy: {openverse.disponibles})")
        recolectar_clase(clase, cuantas, huellas, vistos, openverse, args.paginas_openverse)

    print(f"\nListo. Consultas de Openverse que quedan hoy: {openverse.disponibles}")
    print("Revisar con: python3 revisar_candidatos.py")


if __name__ == "__main__":
    main()
