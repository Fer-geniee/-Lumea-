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

Fuentes, en este orden (--fuentes elige cuáles usar):
- Open Images (openimages.py): fotos de Flickr anotadas por personas,
  CC BY 2.0. Para las 8 frutas es la fuente principal: se eligen fotos en
  contexto real donde la fruta sale grande. Primero hay que construir el
  índice una vez: python3 openimages.py --indice
- Páginas web (--paginas-web ARCHIVO.json): para platos colombianos que no
  están en ningún dataset público. El archivo lista, por clase, páginas
  encontradas con un buscador. De cada página se toman las fotos
  principales. Se respeta robots.txt, se va despacio (1 petición por
  segundo por sitio) y, si un sitio bloquea o limita (401, 403, 429), NO
  se insiste: se anota en dataset_candidatos/_bloqueos.csv y se sigue con
  otros sitios. Estas fotos tienen licencia DESCONOCIDA: sirven para
  entrenar el modelo del proyecto escolar, pero no se deben publicar ni
  redistribuir (queda anotado en fuentes.csv).
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

NO se usa Google Imágenes ni otros buscadores de imágenes directamente: sus
condiciones y su robots.txt no permiten descargarlas en lote.

Filtros automáticos antes de la revisión (todo lo descartado queda en
dataset_candidatos/_registro.csv con el motivo):
- que se pueda abrir: se aceptan JPG, PNG, WebP, AVIF y HEIC, y todo se
  guarda como JPG (el formato que lee TensorFlow sin problemas); los
  archivos rotos se descartan;
- lado menor de al menos 224 px (el tamaño de entrada del modelo);
- en las frutas, fondo blanco (los bordes de la foto casi todos blancos):
  son justo las fotos de estudio tipo Fruits-360 que se quieren reemplazar;
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
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import imagehash
import numpy as np
import requests
from PIL import Image, ImageOps

import openimages
from limpiar_dataset import decidir_por_clase, distancias, leer_imagenes

try:  # fotos de iPhone (.heic)
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
FRUTAS = set(openimages.FRUTAS)
MAXIMO_BORDE_BLANCO = 0.5  # frutas: si más de la mitad del borde es blanco, es foto de estudio
BLOQUEOS = os.path.join(CANDIDATOS, "_bloqueos.csv")
LICENCIA_WEB = "desconocida: solo para entrenar el modelo, no publicar ni redistribuir"
IMAGENES_POR_PAGINA = 6
PAUSA_POR_SITIO = 1.0  # segundos entre peticiones al mismo sitio
# Bots que los sitios bloquean cuando NO quieren que su contenido se use para
# entrenar IA (Cookpad, por ejemplo, bloquea CCBot "used to create training
# datasets"). Este script arma un dataset de entrenamiento, así que si un sitio
# bloquea a cualquiera de estos, se respeta como un "no" y no se usa, aunque su
# robots.txt no nombre a Lumea.
BOTS_DE_IA = ("CCBot", "GPTBot", "ClaudeBot", "anthropic-ai", "Google-Extended")
FUENTES_DISPONIBLES = ("openimages", "web", "commons", "openverse")

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
# Páginas web (platos colombianos sin dataset público)
# --------------------------------------------------------------------------

class ExtractorImagenes(HTMLParser):
    """Saca de una página su título y las URLs de sus fotos: primero la
    foto "de portada" (og:image / twitter:image), después las <img> del
    CONTENIDO PRINCIPAL. Se ignoran las que están en menús, barras
    laterales, pies de página, "artículos relacionados", comentarios o
    perfiles de autor: en la primera prueba (envueltos) eran más de la
    mitad de lo descargado."""

    VACIAS = {"img", "meta", "br", "hr", "input", "source", "link", "wbr", "area", "base", "col", "embed", "param", "track"}
    # Se compara contra cada "palabra" de class/id/role, quitando los prefijos de
    # variante de Tailwind ("md:", "hover:"): en sitios con clases utilitarias,
    # buscar el texto en cualquier parte excluía la página entera.
    FUERA = re.compile(r"^(sidebar|related|relacionad|widget|footer|comment|coment|author|autor|share|social|newsletter|"
                       r"menu|nav|navbar|breadcrumb|banner|advert|ads|publicidad|popular|recomend|trending|tags)([-_].*)?$",
                       re.IGNORECASE)

    def __init__(self):
        super().__init__()
        self.titulo, self._en_titulo = "", False
        self.portada, self.imagenes = [], []
        self.pila = []  # (tag, está_dentro_de_zona_excluida, está_dentro_del_contenido)
        self.enlaces = []

    def _estado(self):
        return self.pila[-1][1:] if self.pila else (False, False)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        excluida, contenido = self._estado()
        marca = " ".join(str(a.get(k) or "") for k in ("class", "id", "role"))
        palabras = [p.split(":")[-1] for p in marca.split()]
        if tag in ("nav", "aside", "footer", "header") or any(self.FUERA.match(p) for p in palabras):
            excluida = True
        if tag == "a" and a.get("href"):
            self.enlaces.append(a["href"])
        if tag in ("article", "main") or re.search(r"entry-content|post-content|article-body|recipe|receta|contenido",
                                                  marca, re.IGNORECASE):
            contenido = True
        if tag == "title":
            self._en_titulo = True
        elif tag == "meta" and (a.get("property") or a.get("name") or "").lower() in ("og:image", "og:image:url", "twitter:image"):
            if a.get("content"):
                self.portada.append(a["content"])
        elif tag in ("img", "source") and not excluida:
            srcset = a.get("srcset") or a.get("data-srcset") or a.get("data-lazy-srcset")
            elegida = None
            if srcset:  # la versión más grande del srcset ("800w" o "2x")
                opciones = [p.strip().split() for p in srcset.split(",") if p.strip()]
                def ancho(op):
                    if len(op) < 2:
                        return 0
                    valor = op[1][:-1]
                    try:
                        return float(valor) * (1 if op[1].endswith("w") else 1000 if op[1].endswith("x") else 0)
                    except ValueError:
                        return 0
                if opciones:
                    elegida = max(opciones, key=ancho)[0]
            if not elegida and tag == "img":
                elegida = a.get("data-src") or a.get("data-lazy-src") or a.get("src")
            if elegida:
                self.imagenes.append((elegida, a, contenido))
        if tag not in self.VACIAS:
            self.pila.append((tag, excluida, contenido))

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False
        for k in range(len(self.pila) - 1, -1, -1):  # cierra hasta la etiqueta que abre (HTML mal formado)
            if self.pila[k][0] == tag:
                del self.pila[k:]
                break

    def handle_data(self, data):
        if self._en_titulo:
            self.titulo += data

    def fotos(self):
        """Portada + imágenes del contenido principal (o todas las no
        excluidas, si la página no marca su contenido)."""
        del_contenido = [(u, a) for u, a, dentro in self.imagenes if dentro]
        resto = del_contenido or [(u, a) for u, a, _ in self.imagenes]
        return [(u, {}) for u in self.portada] + resto


PATRON_NO_FOTO = re.compile(r"logo|icon|avatar|sprite|banner|emoji|gravatar|pixel|placeholder|lazy|blank|spinner|/ads?/|badge|button|flag",
                            re.IGNORECASE)


class Web:
    """Descarga respetuosa: robots.txt, 1 petición por segundo por sitio, y
    si un sitio bloquea o limita (401/403/429) se deja de usar y se anota."""

    def __init__(self):
        self.robots = {}
        self.bloqueados = {}
        self.ultima = {}

    def _anotar_bloqueo(self, sitio, motivo, url):
        if sitio in self.bloqueados:
            return
        self.bloqueados[sitio] = motivo
        agregar_csv(BLOQUEOS, ["fecha", "sitio", "motivo", "url"],
                    [datetime.now().isoformat(timespec="seconds"), sitio, motivo, url])
        print(f"      [bloqueo] {sitio}: {motivo} (no se insiste; se usan otros sitios)")

    def permitido(self, url):
        partes = urlparse(url)
        sitio = partes.netloc
        if sitio in self.bloqueados:
            return False
        if sitio not in self.robots:
            robots = urllib.robotparser.RobotFileParser()
            try:
                r = sesion.get(f"{partes.scheme}://{sitio}/robots.txt", timeout=20)
                if r.status_code in (401, 403):
                    robots.disallow_all = True
                elif r.status_code == 200:
                    robots.parse(r.text.splitlines())
                else:
                    robots.allow_all = True
            except requests.RequestException:
                robots.allow_all = True
            self.robots[sitio] = robots
        if not self.robots[sitio].can_fetch(AGENTE, url):
            self._anotar_bloqueo(sitio, "robots.txt no permite descargar", url)
            return False
        bots = [b for b in BOTS_DE_IA if not self.robots[sitio].can_fetch(b, url)]
        if bots:
            self._anotar_bloqueo(sitio, f"robots.txt bloquea bots que recolectan datos para IA ({', '.join(bots)})", url)
            return False
        return True

    def get(self, url):
        """GET educado. Devuelve la respuesta o None si no se puede o no se debe."""
        if not self.permitido(url):
            return None
        sitio = urlparse(url).netloc
        espera = PAUSA_POR_SITIO - (time.time() - self.ultima.get(sitio, 0))
        if espera > 0:
            time.sleep(espera)
        self.ultima[sitio] = time.time()
        try:
            r = sesion.get(url, timeout=30)
        except requests.RequestException:
            return None
        if r.status_code in (401, 403, 429):
            self._anotar_bloqueo(sitio, f"HTTP {r.status_code}", url)
            return None
        return r if r.status_code == 200 else None

    def descargar(self, candidata):
        # Se revisa el sitio de la PÁGINA (el dueño del contenido), no solo el
        # del servidor de imágenes, que casi nunca tiene robots.txt.
        if not self.permitido(candidata["url_pagina"]):
            return candidata, None, "el sitio no permite usar su contenido"
        r = self.get(candidata["url_imagen"])
        if r is None:
            return candidata, None, "no se pudo o no se debe descargar"
        return candidata, r.content, ""

    def expandir(self, paginas):
        """Una página con "seguir": "<texto>" es un LISTADO (p. ej. una búsqueda
        de Cookpad): no se toman sus fotos, sino las de las páginas a las que
        enlaza (hasta "maximo", 30 por defecto), cuya URL contiene ese texto."""
        for pagina in paginas:
            if not pagina.get("seguir"):
                yield pagina
                continue
            r = self.get(pagina["url"])
            if r is None:
                continue
            extractor = ExtractorImagenes()
            try:
                extractor.feed(r.text)
            except Exception:
                continue
            vistos = set()
            for href in extractor.enlaces:
                enlace = urljoin(pagina["url"], href).split("#")[0]
                if pagina["seguir"] in enlace and enlace not in vistos and enlace != pagina["url"]:
                    vistos.add(enlace)
                    yield {"url": enlace, "consulta": pagina.get("consulta", ""), "fotos": pagina.get("fotos_por_enlace", 2)}
                    if len(vistos) >= pagina.get("maximo", 30):
                        break

    def resultados(self, paginas):
        """paginas: lista de {"url": ..., "consulta": ...} (ver expandir())."""
        for pagina in self.expandir(paginas):
            url = pagina["url"]
            r = self.get(url)
            if r is None or "html" not in r.headers.get("Content-Type", ""):
                continue
            extractor = ExtractorImagenes()
            try:
                extractor.feed(r.text)
            except Exception:
                continue
            titulo = sin_html(extractor.titulo)[:150]
            vistas, entregadas = set(), 0
            for src, atributos in extractor.fotos():
                imagen_url = urljoin(url, src.strip())
                ruta = urlparse(imagen_url).path.lower()
                if not imagen_url.startswith("http") or imagen_url in vistas or PATRON_NO_FOTO.search(imagen_url):
                    continue
                if ruta.endswith((".svg", ".gif")):
                    continue
                ancho = int(atributos["width"]) if str(atributos.get("width", "")).isdigit() else 0
                alto = int(atributos["height"]) if str(atributos.get("height", "")).isdigit() else 0
                if (ancho and ancho < LADO_MINIMO) or (alto and alto < LADO_MINIMO):
                    continue
                vistas.add(imagen_url)
                entregadas += 1
                yield {
                    "fuente": "web",
                    "id": hashlib.md5(imagen_url.encode()).hexdigest()[:16],
                    "titulo": titulo, "ancho": ancho, "alto": alto,
                    "url_imagen": imagen_url, "url_pagina": url,
                    "autor": urlparse(url).netloc, "licencia": LICENCIA_WEB, "url_licencia": "",
                    "consulta_web": pagina.get("consulta", ""),
                }
                if entregadas >= pagina.get("fotos", IMAGENES_POR_PAGINA):
                    break


WEB = Web()


# --------------------------------------------------------------------------
# Descarga y guardado
# --------------------------------------------------------------------------

def descargar(candidata):
    """Devuelve (candidata, contenido o None, error)."""
    if candidata["fuente"] == "web":
        return WEB.descargar(candidata)
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


def fraccion_borde_blanco(imagen_rgb):
    """Fracción del borde de la foto (franja de ~8%) que es blanco o casi
    blanco y sin color. Las fotos de estudio (Fruits-360, catálogos) dan
    casi 1; una fruta en una mesa, un mercado o una mano da poco."""
    a = np.asarray(imagen_rgb.resize((128, 128))).astype(int)
    borde = np.concatenate([a[:10].reshape(-1, 3), a[-10:].reshape(-1, 3),
                            a[:, :10].reshape(-1, 3), a[:, -10:].reshape(-1, 3)])
    blanco = (borde.min(axis=1) > 215) & (borde.max(axis=1) - borde.min(axis=1) < 25)
    return float(blanco.mean())


def preparar(contenido, clase=None):
    """Abre (JPG, PNG, WebP, AVIF, HEIC...), gira según EXIF, pasa a RGB,
    aplica los filtros, reduce a LADO_MAXIMO y vuelve a codificar como JPG
    sin metadatos. Devuelve (imagen, bytes_jpeg) o lanza error."""
    with Image.open(io.BytesIO(contenido)) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
    if min(im.size) < LADO_MINIMO:
        raise ValueError(f"muy pequeña ({im.size[0]}x{im.size[1]})")
    if fraccion_con_color(im) < MINIMO_PIXELES_CON_COLOR:
        raise ValueError("sin color (blanco y negro o dibujo)")
    if clase in FRUTAS and fraccion_borde_blanco(im) > MAXIMO_BORDE_BLANCO:
        raise ValueError("fondo blanco (foto de estudio)")
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
    # Las páginas web se piden de a una (para no cargar un sitio pequeño);
    # Open Images, Commons y Flickr aguantan 4 a la vez.
    en_paralelo = 1 if any(c["fuente"] == "web" for c in lote) else 4
    with ThreadPoolExecutor(max_workers=en_paralelo) as grupo:
        for candidata, contenido, error in grupo.map(descargar, lote):
            if guardadas >= cuantas:
                break
            if contenido is None:
                registrar(clase, candidata["fuente"], candidata["id"], "error_descarga", error)
                continue
            try:
                imagen, jpeg = preparar(contenido, clase)
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


def recolectar_clase(clase, cuantas, huellas, vistos, openverse, paginas_openverse,
                     fuentes=FUENTES_DISPONIBLES, paginas_web=None):
    carpeta = os.path.join(CANDIDATOS, clase)
    os.makedirs(carpeta, exist_ok=True)
    fuentes_csv = os.path.join(carpeta, "fuentes.csv")
    ya = sum(1 for f in os.listdir(carpeta) if f.endswith(".jpg"))
    if ya >= cuantas:
        print(f"  {clase}: ya tiene {ya} candidatas (se buscaban {cuantas})")
        return ya
    config = CONSULTAS.get(clase, {"categorias": [], "commons": [], "openverse": []})

    # (nombre, generador, máximo de resultados a mirar)
    generadores = []
    if "openimages" in fuentes and (clase in openimages.FRUTAS or clase in openimages.PLATOS):
        generadores.append(("openimages", openimages.resultados_para(clase, 5000), None))
    if "web" in fuentes and paginas_web and paginas_web.get(clase):
        generadores.append(("web", WEB.resultados(paginas_web[clase]), None))
    if "commons" in fuentes:
        generadores += [(f"commons categoría '{c}'", commons_categoria(c), MAXIMO_POR_CONSULTA) for c in config["categorias"]]
        generadores += [(f"commons búsqueda '{q}'", commons_busqueda(q), MAXIMO_POR_CONSULTA) for q in config["commons"]]
    if "openverse" in fuentes:
        generadores += [(f"openverse '{q}'", openverse.resultados(q, paginas_openverse), MAXIMO_POR_CONSULTA)
                        for q in config["openverse"]]
    if not generadores:
        print(f"  {clase}: ninguna fuente tiene búsquedas para esta clase; se salta")
        return ya

    guardadas = ya
    for consulta, generador, maximo in generadores:
        revisadas = 0
        lote = []
        for candidata in generador:
            revisadas += 1
            if maximo and revisadas > maximo:
                break
            clave = f"{candidata['fuente']}:{candidata['id']}"
            if clave in vistos:
                continue
            vistos[clave] = clase
            # El filtro de títulos es para títulos escritos por personas (Commons,
            # Flickr). Los de web y Open Images los arma este script.
            if candidata["fuente"] not in ("web", "openimages") and PATRON_EXCLUIDO.search(candidata["titulo"]):
                registrar(clase, candidata["fuente"], candidata["id"], "titulo_excluido", candidata["titulo"][:120])
                continue
            if candidata["ancho"] and candidata["alto"] and min(candidata["ancho"], candidata["alto"]) < LADO_MINIMO:
                registrar(clase, candidata["fuente"], candidata["id"], "pequena", f"{candidata['ancho']}x{candidata['alto']}")
                continue
            consulta_web = candidata.pop("consulta_web", "")
            candidata["consulta"] = f"web: {consulta_web}" if consulta_web else consulta
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
        print(f"  {clase}: solo se encontraron {guardadas} de {cuantas} con estas fuentes y búsquedas")
    return guardadas


def refiltrar(clases):
    """Pasa los filtros actuales (tamaño, color, fondo blanco en frutas) a
    candidatas que se bajaron antes de que existieran. Las que no pasan se
    MUEVEN a dataset_candidatos/_descartadas/<clase>/ (no se borran)."""
    for clase in clases:
        carpeta = os.path.join(CANDIDATOS, clase)
        if not os.path.isdir(carpeta):
            continue
        movidas = 0
        for archivo in sorted(a for a in os.listdir(carpeta) if a.endswith(".jpg")):
            ruta = os.path.join(carpeta, archivo)
            with open(ruta, "rb") as f:
                contenido = f.read()
            try:
                preparar(contenido, clase)
            except Exception as e:
                destino = os.path.join(CANDIDATOS, "_descartadas", clase)
                os.makedirs(destino, exist_ok=True)
                os.replace(ruta, os.path.join(destino, archivo))
                registrar(clase, "refiltro", archivo, "descartada_al_refiltrar", str(e)[:120])
                movidas += 1
        print(f"  {clase}: {movidas} candidatas no pasan los filtros actuales -> _descartadas/{clase}/")


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
    parser.add_argument("--fuentes", default=",".join(FUENTES_DISPONIBLES),
                        help="Fuentes a usar, separadas por coma: " + ", ".join(FUENTES_DISPONIBLES))
    parser.add_argument("--refiltrar", action="store_true",
                        help="Solo pasa los filtros actuales a las candidatas que ya existen (no descarga nada)")
    parser.add_argument("--paginas-web", metavar="ARCHIVO.json",
                        help='Páginas por clase para la fuente web: {"clase": [{"url": ..., "consulta": ...}, ...]}')
    args = parser.parse_args()
    fuentes = tuple(f.strip() for f in args.fuentes.split(",") if f.strip())
    desconocidas_f = set(fuentes) - set(FUENTES_DISPONIBLES)
    if desconocidas_f:
        sys.exit(f"Fuentes desconocidas: {sorted(desconocidas_f)}")
    paginas_web = leer_json(args.paginas_web, {}) if args.paginas_web else {}
    if args.refiltrar:
        refiltrar(args.clases or sorted(c for c in os.listdir(CANDIDATOS)
                                        if os.path.isdir(os.path.join(CANDIDATOS, c)) and not c.startswith("_")))
        return
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
        recolectar_clase(clase, cuantas, huellas, vistos, openverse, args.paginas_openverse, fuentes, paginas_web)

    print(f"\nListo. Consultas de Openverse que quedan hoy: {openverse.disponibles}")
    print("Revisar con: python3 revisar_candidatos.py")


if __name__ == "__main__":
    main()
